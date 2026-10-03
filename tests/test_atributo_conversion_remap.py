from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from osiris.modules.common.audit_log.entity import AuditLog
from osiris.modules.common.catalogo.entity import Catalogo, CatalogoValor
from osiris.modules.inventario.atributo.entity import Atributo, TipoDato
from osiris.modules.inventario.atributo.remap_service import AtributoRemapeoService
from osiris.modules.inventario.atributo.service import AtributoService
from osiris.modules.inventario.casa_comercial.entity import CasaComercial
from osiris.modules.inventario.categoria.entity import Categoria
from osiris.modules.inventario.categoria_atributo.entity import CategoriaAtributo
from osiris.modules.inventario.producto.entity import Producto, ProductoCategoria, TipoProducto
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoRemapeo, ProductoAtributoValor
from osiris.modules.inventario.producto.models_atributos import ProductoAtributoRemapeoResolve


def _engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            AuditLog.__table__,
            Catalogo.__table__,
            CatalogoValor.__table__,
            CasaComercial.__table__,
            Atributo.__table__,
            Categoria.__table__,
            CategoriaAtributo.__table__,
            Producto.__table__,
            ProductoCategoria.__table__,
            ProductoAtributoValor.__table__,
            ProductoAtributoRemapeo.__table__,
        ],
    )
    return engine


def test_type_change_converts_valid_values_and_preserves_invalid_values_for_remap():
    engine = _engine()
    with Session(engine) as session:
        attribute = Atributo(
            nombre="Garantía",
            tipo_dato=TipoDato.STRING,
            usuario_auditoria="test",
            activo=True,
        )
        valid_product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        invalid_product = Producto(
            nombre=f"Product-{uuid4().hex[:8]}",
            tipo=TipoProducto.BIEN,
            pvp=Decimal("10.00"),
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([attribute, valid_product, invalid_product])
        session.flush()
        category = Categoria(
            nombre=f"Categoria-{uuid4().hex[:8]}",
            es_padre=False,
            usuario_auditoria="test",
            activo=True,
        )
        session.add(category)
        session.flush()
        session.add_all(
            [
                ProductoCategoria(producto_id=valid_product.id, categoria_id=category.id),
                ProductoCategoria(producto_id=invalid_product.id, categoria_id=category.id),
                CategoriaAtributo(
                    categoria_id=category.id,
                    atributo_id=attribute.id,
                    obligatorio=False,
                    usuario_auditoria="test",
                    activo=True,
                ),
            ]
        )
        valid_value = ProductoAtributoValor(
            producto_id=valid_product.id,
            atributo_id=attribute.id,
            valor_string="42",
            usuario_auditoria="test",
            activo=True,
        )
        invalid_value = ProductoAtributoValor(
            producto_id=invalid_product.id,
            atributo_id=attribute.id,
            valor_string="n/a",
            usuario_auditoria="test",
            activo=True,
        )
        session.add_all([valid_value, invalid_value])
        session.commit()

        updated = AtributoService().update(session, attribute.id, {"tipo_dato": TipoDato.INTEGER})

        assert updated.tipo_dato == TipoDato.INTEGER
        session.refresh(valid_value)
        session.refresh(invalid_value)
        assert valid_value.valor_integer == 42
        assert valid_value.valor_string is None
        assert invalid_value.valor_string == "n/a"
        remaps = session.exec(
            select(ProductoAtributoRemapeo).where(ProductoAtributoRemapeo.atributo_id == attribute.id)
        ).all()
        assert len(remaps) == 1
        assert remaps[0].producto_id == invalid_product.id
        assert remaps[0].valor_anterior == {"value": "n/a"}
        assert remaps[0].activo is True

        remap_service = AtributoRemapeoService()
        pending = remap_service.listar_pendientes(session)
        assert pending["total"] == 1
        assert pending["groups"][0]["target_type"] == "integer"
        result = remap_service.resolver(
            session,
            [ProductoAtributoRemapeoResolve(id=remaps[0].id, valor=7)],
        )
        assert result == {"resolved": 1}

        session.refresh(invalid_value)
        session.refresh(remaps[0])
        assert invalid_value.valor_integer == 7
        assert invalid_value.valor_string is None
        assert remaps[0].activo is False
