from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, literal, update
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from osiris.domain.service import BaseService
from osiris.modules.inventario.atributo.entity import Atributo
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from .entity import Categoria
from .repository import CategoriaRepository


class CategoriaService(BaseService):
    repo = CategoriaRepository()

    # Validar parent_id contra la misma tabla
    fk_models = {
        "parent_id": Categoria,
    }

    def validate_create(self, data: dict, session: Session) -> None:
        """Reglas de negocio para create:
        - parent_id es opcional; una categoría puede ser padre y al mismo tiempo hija
        """
        # parent_id is optional; if provided, validate the FK exists and is active
        if "parent_id" in data and data.get("parent_id"):
            # _check_fk_active_and_exists conoce fk_models y validará parent_id
            self._check_fk_active_and_exists(session, data)

    def _aplicar_regla_b3_migracion(self, session: Session, parent_id: UUID) -> None:
        """
        Regla B3:
        Si la categoría padre (hoy hoja) ya tiene productos asociados y va a recibir hijos,
        crear/reusar subcategoría "General" y migrar allí esos productos en la misma transacción.
        """
        from osiris.modules.inventario.producto.entity import ProductoCategoria

        parent = session.exec(
            select(Categoria)
            .where(Categoria.id == parent_id)
            .with_for_update()
        ).first()
        if not parent:
            return

        has_productos = session.exec(
            select(ProductoCategoria.producto_id)
            .where(ProductoCategoria.categoria_id == parent_id)
            .limit(1)
        ).first()
        if not has_productos:
            return

        general = session.exec(
            select(Categoria)
            .where(Categoria.parent_id == parent_id)
            .where(func.lower(Categoria.nombre) == "general")
            .with_for_update()
        ).first()

        if general is None:
            general = Categoria(
                nombre="General",
                es_padre=False,
                parent_id=parent_id,
                usuario_auditoria=getattr(parent, "usuario_auditoria", None),
            )
            session.add(general)
            session.flush()

        session.exec(
            update(ProductoCategoria)
            .where(ProductoCategoria.categoria_id == parent_id)
            .values(categoria_id=general.id)
        )
        session.flush()

        parent.es_padre = True
        session.add(parent)
        session.flush()

    def create(self, session: Session, data: dict, *, commit: bool = True):
        """
        Override de create para inyectar la Regla B3 dentro de una única transacción.
        """
        try:
            data = self._ensure_dict(data)
            self.validate_create(data, session)
            self._check_fk_active_and_exists(session, data)

            parent_id = data.get("parent_id")
            if parent_id:
                self._aplicar_regla_b3_migracion(session, parent_id)

            obj = self.repo.create(session, data)
            self.on_created(obj, session)
            if commit:
                session.commit()
                session.refresh(obj)
            return obj
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def _detect_cycle(self, session: Session, current_id: UUID, target_parent_id: UUID, visited: set = None) -> bool:
        """Detecta si hay un ciclo en la jerarquía al establecer target_parent_id como padre de current_id.

        Args:
            session: Sesión de DB
            current_id: ID del nodo actual
            target_parent_id: ID del nodo que se quiere establecer como padre
            visited: Set de IDs ya visitados (para detección de ciclos)

        Returns:
            bool: True si hay ciclo, False si no hay ciclo
        """
        if visited is None:
            visited = set()

        # Si el nodo actual ya fue visitado, hay ciclo
        if current_id in visited:
            return True

        # Si llegamos al nodo que queremos como padre, hay ciclo
        if current_id == target_parent_id:
            return True

        # Marcar nodo actual como visitado
        visited.add(current_id)

        # Buscar hijos del nodo actual
        stmt = select(Categoria).where(
            Categoria.parent_id == current_id,
            Categoria.activo.is_(True),
        )
        children = session.exec(stmt).all()

        # Verificar recursivamente los hijos
        for child in children:
            if self._detect_cycle(session, child.id, target_parent_id, visited):
                return True

        return False

    def update(self, session: Session, item_id: UUID, data: Any):
        """Override para validar/update con contexto del objeto existente.
        - si se marca es_padre=True se limpia parent_id automáticamente.
        - si se marca es_padre=False se exige que exista parent_id (en data o en DB).
        - evita self-referencia y ciclos en la jerarquía
        """
        try:
            data = self._ensure_dict(data)
            db_obj = self.repo.get(session, item_id)
            if not db_obj:
                return None

            # Evitar que parent_id apunte a sí mismo
            if data.get("parent_id") and data.get("parent_id") == item_id:
                raise HTTPException(status_code=400, detail="parent_id no puede referenciar al mismo registro")

            # Detectar ciclos si se está cambiando el parent_id (cuando se proporciona uno nuevo)
            new_parent_id = data.get("parent_id")
            parent_changed = (
                new_parent_id is not None
                and new_parent_id != getattr(db_obj, "parent_id", None)
            )
            if new_parent_id and new_parent_id != getattr(db_obj, "parent_id", None):
                if self._detect_cycle(session, item_id, new_parent_id):
                    # Obtener nombres para mejorar el detalle del error (si están disponibles)
                    try:
                        parent_obj = session.get(Categoria, new_parent_id)
                    except Exception:
                        parent_obj = None

                    parent_nombre = getattr(parent_obj, "nombre", str(new_parent_id))
                    item_nombre = getattr(db_obj, "nombre", str(item_id))

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"La actualización crearía un ciclo en la jerarquía: intentar establecer "
                            f"parent '{parent_nombre}' (id={new_parent_id}) como padre de "
                            f"'{item_nombre}' (id={item_id}) formaría un bucle"
                        ),
                    )

            # Validar FKs si vienen en data
            if "parent_id" in data:
                self._check_fk_active_and_exists(session, data)

            # Regla B3 en update: antes de mover la categoría actual al nuevo padre
            if parent_changed:
                self._aplicar_regla_b3_migracion(session, new_parent_id)

            updated = self.repo.update(session, db_obj, data)
            session.commit()
            session.refresh(updated)
            return updated
        except Exception as exc:
            self._handle_transaction_error(session, exc)

    def get_atributos_heredados_por_categorias(
        self,
        session: Session,
        categoria_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        """
        Obtiene atributos aplicables desde una o varias categorías y sus ancestros
        usando CTE recursivo + row_number para deduplicar por atributo.
        Regla: gana la categoría más específica (menor profundidad).
        """
        if not categoria_ids:
            return []

        ancestros_cte = (
            select(
                Categoria.id.label("categoria_id"),
                Categoria.parent_id.label("parent_id"),
                literal(0).label("profundidad"),
            )
            .where(Categoria.id.in_(categoria_ids))
            .cte(name="categoria_ancestros", recursive=True)
        )

        categoria_padre = aliased(Categoria)
        ancestros_cte = ancestros_cte.union_all(
            select(
                categoria_padre.id.label("categoria_id"),
                categoria_padre.parent_id.label("parent_id"),
                (ancestros_cte.c.profundidad + 1).label("profundidad"),
            ).join(ancestros_cte, categoria_padre.id == ancestros_cte.c.parent_id)
        )

        ranked_cte = (
            select(
                CategoriaAtributo.atributo_id.label("atributo_id"),
                Atributo.nombre.label("atributo_nombre"),
                Atributo.tipo_dato.label("tipo_dato"),
                CategoriaAtributo.orden.label("orden"),
                CategoriaAtributo.obligatorio.label("obligatorio"),
                ancestros_cte.c.categoria_id.label("categoria_origen_id"),
                ancestros_cte.c.profundidad.label("profundidad"),
                func.row_number()
                .over(
                    partition_by=Atributo.id,
                    order_by=ancestros_cte.c.profundidad.asc(),
                )
                .label("rn"),
            )
            .join(ancestros_cte, CategoriaAtributo.categoria_id == ancestros_cte.c.categoria_id)
            .join(Atributo, Atributo.id == CategoriaAtributo.atributo_id)
            .where(CategoriaAtributo.activo.is_(True))
            .cte(name="atributos_ranked")
        )

        stmt = (
            select(
                ranked_cte.c.atributo_id,
                ranked_cte.c.atributo_nombre,
                ranked_cte.c.tipo_dato,
                ranked_cte.c.orden,
                ranked_cte.c.obligatorio,
                ranked_cte.c.categoria_origen_id,
                ranked_cte.c.profundidad,
            )
            .where(ranked_cte.c.rn == 1)
            .order_by(ranked_cte.c.atributo_nombre.asc())
        )

        rows = session.exec(stmt).all()
        return [
            {
                "atributo_id": row.atributo_id,
                "atributo_nombre": row.atributo_nombre,
                "tipo_dato": row.tipo_dato,
                "orden": row.orden,
                "obligatorio": row.obligatorio,
                "categoria_origen_id": row.categoria_origen_id,
                "profundidad": row.profundidad,
            }
            for row in rows
        ]

    def get_atributos_heredados_por_categoria(self, session: Session, categoria_id: UUID) -> list[dict[str, Any]]:
        """
        Obtiene atributos aplicables de una categoría y sus ancestros mediante CTE recursivo.
        """
        return self.get_atributos_heredados_por_categorias(session, [categoria_id])
