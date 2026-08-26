"""seed sri tax catalog from json

Revision ID: 20f3d9f4a008
Revises: 06ee39e487b6
Create Date: 2025-11-29 17:46:18.256000

"""
from typing import Sequence, Union
import json
import uuid
from datetime import datetime, date
from pathlib import Path

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20f3d9f4a008'
down_revision: Union[str, None] = 'cec1e957113e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Limpiar relaciones primero (foreign key)
    op.execute("DELETE FROM tbl_producto_impuesto")
    # Limpiar tabla existente
    op.execute("DELETE FROM aux_impuesto_catalogo")

    # Leer JSON desde conf/aux_impuesto_catalogo.json
    # La ruta es relativa al root del repo
    json_path = Path(__file__).parents[5] / "conf" / "aux_impuesto_catalogo.json"

    with open(json_path, 'r', encoding='utf-8') as f:
        impuestos = json.load(f)

    # Preparar datos para inserción
    conn = op.get_bind()
    now = datetime.utcnow()

    # Mapeos de normalización para valores del JSON a enums de Python
    modo_calculo_map = {
        "ESPECIFICA": "ESPECIFICO",
        "MIXTA": "MIXTO",
        "AD_VALOREM": "AD_VALOREM"
    }

    unidad_base_map = {
        "UNIDAD": "UNIDAD",
        "LITRO": "LITRO",
        "KILO": "KILO",
        "MIL_UNIDADES": "MIL_UNIDADES",
        "OTRO": "OTRO"
    }

    # Control de duplicados exactos (codigo_sri + descripcion)
    registros_insertados = set()

    for impuesto in impuestos:
        # Crear clave única para detectar duplicados
        clave_unica = (impuesto["codigo_sri"], impuesto["descripcion"])

        # Skip duplicados exactos
        if clave_unica in registros_insertados:
            continue

        registros_insertados.add(clave_unica)

        # Generar UUID
        id_uuid = str(uuid.uuid4())

        # Preparar valores, convirtiendo None y manejando fechas
        vigente_desde = impuesto.get("vigente_desde")
        if vigente_desde:
            vigente_desde = date.fromisoformat(vigente_desde) if isinstance(vigente_desde, str) else vigente_desde
        else:
            vigente_desde = date(2023, 2, 1)  # Default a 01/02/2023 si es null

        vigente_hasta = impuesto.get("vigente_hasta")
        if vigente_hasta and isinstance(vigente_hasta, str):
            vigente_hasta = date.fromisoformat(vigente_hasta)

        # Normalizar modo_calculo_ice y unidad_base
        modo_calculo_ice = impuesto.get("modo_calculo_ice")
        if modo_calculo_ice:
            modo_calculo_ice = modo_calculo_map.get(modo_calculo_ice, modo_calculo_ice)

        unidad_base = impuesto.get("unidad_base")
        if unidad_base:
            unidad_base = unidad_base_map.get(unidad_base, "UNIDAD")  # Default a UNIDAD si no está en el enum

        # Insertar registro
        conn.execute(
            sa.text("""
                INSERT INTO aux_impuesto_catalogo (
                    id, activo, creado_en, actualizado_en, usuario_auditoria,
                    tipo_impuesto, codigo_tipo_impuesto, codigo_sri, descripcion,
                    vigente_desde, vigente_hasta, aplica_a,
                    porcentaje_iva, clasificacion_iva,
                    tarifa_ad_valorem, tarifa_especifica, modo_calculo_ice, unidad_base
                ) VALUES (
                    :id, :activo, :creado_en, :actualizado_en, :usuario_auditoria,
                    :tipo_impuesto, :codigo_tipo_impuesto, :codigo_sri, :descripcion,
                    :vigente_desde, :vigente_hasta, :aplica_a,
                    :porcentaje_iva, :clasificacion_iva,
                    :tarifa_ad_valorem, :tarifa_especifica, :modo_calculo_ice, :unidad_base
                )
            """),
            {
                "id": id_uuid,
                "activo": impuesto.get("activo", True),
                "creado_en": now,
                "actualizado_en": now,
                "usuario_auditoria": impuesto.get("usuario_auditoria", "system"),
                "tipo_impuesto": impuesto["tipo_impuesto"],
                "codigo_tipo_impuesto": impuesto["codigo_tipo_impuesto"],
                "codigo_sri": impuesto["codigo_sri"],
                "descripcion": impuesto["descripcion"],
                "vigente_desde": vigente_desde,
                "vigente_hasta": vigente_hasta,
                "aplica_a": impuesto["aplica_a"],
                "porcentaje_iva": impuesto.get("porcentaje_iva"),
                "clasificacion_iva": impuesto.get("clasificacion_iva"),
                "tarifa_ad_valorem": impuesto.get("tarifa_ad_valorem"),
                "tarifa_especifica": impuesto.get("tarifa_especifica"),
                "modo_calculo_ice": modo_calculo_ice,
                "unidad_base": unidad_base,
            }
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Limpiar todos los registros insertados
    op.execute("DELETE FROM aux_impuesto_catalogo")
