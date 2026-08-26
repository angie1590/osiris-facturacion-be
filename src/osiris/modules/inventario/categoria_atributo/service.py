# src/osiris/modules/inventario/categoria_atributo/service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import Boolean, Date, Integer, Numeric, String, cast, func, insert as sa_insert, literal
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from sqlmodel import select

from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import ProductoCategoria
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoValor
from .models import CategoriaAtributoCreate, CategoriaAtributoUpdate


class CategoriaAtributoService:
    @staticmethod
    def _is_empty_default(value: Optional[str]) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    @staticmethod
    def _build_safe_default(tipo_dato: Optional[TipoDato]) -> Optional[str]:
        if tipo_dato is None:
            return None
        if tipo_dato == TipoDato.STRING:
            return "N/A"
        if tipo_dato == TipoDato.INTEGER:
            return "0"
        if tipo_dato == TipoDato.DECIMAL:
            return "0.00"
        if tipo_dato == TipoDato.BOOLEAN:
            return "false"
        if tipo_dato == TipoDato.DATE:
            return date.today().isoformat()
        return None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in {"true", "1", "t", "yes", "y"}:
            return True
        if normalized in {"false", "0", "f", "no", "n"}:
            return False
        raise ValueError("Valor booleano inválido")

    @staticmethod
    def _normalize_tipo_dato(tipo_dato: Optional[object]) -> Optional[str]:
        if tipo_dato is None:
            return None
        if hasattr(tipo_dato, "value"):
            return str(tipo_dato.value).lower()
        return str(tipo_dato).lower()

    def _cast_default_by_tipo(self, valor_default: str, tipo_dato: Optional[object]):
        tipo_normalizado = self._normalize_tipo_dato(tipo_dato)
        if tipo_normalizado is None:
            raise HTTPException(status_code=400, detail="No se pudo determinar el tipo de dato del atributo")

        try:
            if tipo_normalizado == TipoDato.STRING.value:
                return str(valor_default), tipo_normalizado
            if tipo_normalizado == TipoDato.INTEGER.value:
                return int(str(valor_default).strip()), tipo_normalizado
            if tipo_normalizado == TipoDato.DECIMAL.value:
                return Decimal(str(valor_default).strip()), tipo_normalizado
            if tipo_normalizado == TipoDato.BOOLEAN.value:
                return self._parse_bool(str(valor_default)), tipo_normalizado
            if tipo_normalizado == TipoDato.DATE.value:
                return date.fromisoformat(str(valor_default).strip()), tipo_normalizado
        except (ValueError, TypeError, InvalidOperation):
            raise HTTPException(
                status_code=400,
                detail="El valor_default no coincide con el tipo de dato del atributo",
            ) from None

        raise HTTPException(status_code=400, detail="Tipo de dato del atributo no soportado")

    def _ejecutar_backfill_atributo(
        self,
        session: Session,
        categoria_atributo: CategoriaAtributo,
        tipo_dato: Optional[object],
    ) -> None:
        """
        Backfill masivo (sin loops Python):
        - productos de categoría origen y descendientes via CTE recursivo
        - INSERT ... SELECT tipado
        - ON CONFLICT DO NOTHING por (producto_id, atributo_id)
        """
        if not isinstance(session, Session):
            return
        if categoria_atributo.obligatorio is not True:
            return
        if self._is_empty_default(categoria_atributo.valor_default):
            return

        valor_tipado, tipo_normalizado = self._cast_default_by_tipo(categoria_atributo.valor_default, tipo_dato)

        categorias_cte = (
            select(Categoria.id.label("categoria_id"))
            .where(Categoria.id == categoria_atributo.categoria_id)
            .cte(name="categoria_descendientes", recursive=True)
        )
        categorias_cte = categorias_cte.union_all(
            select(Categoria.id.label("categoria_id"))
            .where(Categoria.parent_id == categorias_cte.c.categoria_id)
        )

        productos_afectados = (
            select(ProductoCategoria.producto_id.label("producto_id"))
            .join(categorias_cte, ProductoCategoria.categoria_id == categorias_cte.c.categoria_id)
            .distinct()
            .subquery()
        )

        valor_string_expr = literal(None, type_=String())
        valor_integer_expr = literal(None, type_=Integer())
        valor_decimal_expr = literal(None, type_=Numeric(18, 6))
        valor_boolean_expr = literal(None, type_=Boolean())
        valor_date_expr = literal(None, type_=Date())

        if tipo_normalizado == TipoDato.STRING.value:
            valor_string_expr = literal(valor_tipado, type_=String())
        elif tipo_normalizado == TipoDato.INTEGER.value:
            valor_integer_expr = literal(valor_tipado, type_=Integer())
        elif tipo_normalizado == TipoDato.DECIMAL.value:
            valor_decimal_expr = literal(valor_tipado, type_=Numeric(18, 6))
        elif tipo_normalizado == TipoDato.BOOLEAN.value:
            valor_boolean_expr = literal(valor_tipado, type_=Boolean())
        elif tipo_normalizado == TipoDato.DATE.value:
            valor_date_expr = literal(valor_tipado, type_=Date())

        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

        if dialect_name == "postgresql":
            insert_stmt = pg_insert(ProductoAtributoValor.__table__)
            id_expr = cast(
                func.md5(
                    func.concat(
                        cast(productos_afectados.c.producto_id, String()),
                        literal(str(categoria_atributo.atributo_id)),
                    )
                ),
                PGUUID(as_uuid=True),
            )
        elif dialect_name == "sqlite":
            insert_stmt = sqlite_insert(ProductoAtributoValor.__table__).prefix_with("OR IGNORE")
            id_expr = func.lower(func.hex(func.randomblob(16)))
        else:
            insert_stmt = sa_insert(ProductoAtributoValor.__table__)
            id_expr = cast(
                func.md5(
                    func.concat(
                        cast(productos_afectados.c.producto_id, String()),
                        literal(str(categoria_atributo.atributo_id)),
                    )
                ),
                String(),
            )

        select_stmt = select(
            id_expr.label("id"),
            productos_afectados.c.producto_id.label("producto_id"),
            literal(categoria_atributo.atributo_id).label("atributo_id"),
            valor_string_expr.label("valor_string"),
            valor_integer_expr.label("valor_integer"),
            valor_decimal_expr.label("valor_decimal"),
            valor_boolean_expr.label("valor_boolean"),
            valor_date_expr.label("valor_date"),
        )

        stmt = insert_stmt.from_select(
            [
                "id",
                "producto_id",
                "atributo_id",
                "valor_string",
                "valor_integer",
                "valor_decimal",
                "valor_boolean",
                "valor_date",
            ],
            select_stmt,
        )

        if dialect_name == "postgresql" and hasattr(stmt, "on_conflict_do_nothing"):
            stmt = stmt.on_conflict_do_nothing(index_elements=["producto_id", "atributo_id"])

        session.exec(stmt)
        session.flush()

    def list_paginated(self, session: Session, skip: int = 0, limit: int = 50, categoria_id: Optional[UUID] = None) -> list[CategoriaAtributo]:
        query = select(CategoriaAtributo).where(CategoriaAtributo.activo.is_(True))
        if categoria_id:
            query = query.where(CategoriaAtributo.categoria_id == categoria_id)
        query = query.offset(skip).limit(limit)
        return list(session.exec(query))

    def get(self, session: Session, id: UUID) -> Optional[CategoriaAtributo]:
        return session.get(CategoriaAtributo, id)

    def create(self, session: Session, dto: CategoriaAtributoCreate, usuario_auditoria: Optional[str] = None) -> CategoriaAtributo:
        atributo_master: Optional[Atributo] = None
        valor_default = dto.valor_default
        if dto.obligatorio is True and self._is_empty_default(valor_default):
            atributo_master = session.get(Atributo, dto.atributo_id)
            valor_default = self._build_safe_default(getattr(atributo_master, "tipo_dato", None))
        elif dto.obligatorio is True:
            atributo_master = session.get(Atributo, dto.atributo_id)

        entity = CategoriaAtributo(
            categoria_id=dto.categoria_id,
            atributo_id=dto.atributo_id,
            orden=dto.orden,
            obligatorio=dto.obligatorio,
            valor_default=valor_default,
            usuario_auditoria=usuario_auditoria or "api",
            activo=True,
        )
        session.add(entity)
        if entity.obligatorio is True and not self._is_empty_default(entity.valor_default):
            self._ejecutar_backfill_atributo(
                session,
                entity,
                getattr(atributo_master, "tipo_dato", None),
            )
        session.commit()
        session.refresh(entity)
        return entity

    def update(self, session: Session, id: UUID, dto: CategoriaAtributoUpdate, usuario_auditoria: Optional[str] = None) -> Optional[CategoriaAtributo]:
        entity = session.get(CategoriaAtributo, id)
        if not entity:
            return None

        obligatorio_anterior = entity.obligatorio is True
        atributo_master: Optional[Atributo] = None

        if dto.orden is not None:
            entity.orden = dto.orden
        if dto.obligatorio is not None:
            entity.obligatorio = dto.obligatorio

        if dto.valor_default is not None:
            valor_default = dto.valor_default
        else:
            valor_default = entity.valor_default

        if dto.obligatorio is True and self._is_empty_default(valor_default):
            atributo_master = session.get(Atributo, entity.atributo_id)
            valor_default = self._build_safe_default(getattr(atributo_master, "tipo_dato", None))

        if dto.valor_default is not None or dto.obligatorio is True:
            entity.valor_default = valor_default

        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        if (not obligatorio_anterior) and entity.obligatorio is True and not self._is_empty_default(entity.valor_default):
            if atributo_master is None:
                atributo_master = session.get(Atributo, entity.atributo_id)
            self._ejecutar_backfill_atributo(
                session,
                entity,
                getattr(atributo_master, "tipo_dato", None),
            )
        session.commit()
        session.refresh(entity)
        return entity

    def delete(self, session: Session, id: UUID, usuario_auditoria: Optional[str] = None) -> bool:
        entity = session.get(CategoriaAtributo, id)
        if not entity:
            return False
        entity.activo = False
        entity.usuario_auditoria = usuario_auditoria or entity.usuario_auditoria
        session.add(entity)
        session.commit()
        return True
