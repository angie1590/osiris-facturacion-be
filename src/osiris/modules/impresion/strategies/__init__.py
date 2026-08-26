from __future__ import annotations

from osiris.modules.impresion.strategies.render_strategy import RenderStrategy
from osiris.modules.impresion.strategies.plantilla_preimpresa_strategy import (
    PlantillaPreimpresaStrategy,
)
from osiris.modules.impresion.strategies.ride_a4_strategy import RideA4Strategy
from osiris.modules.impresion.strategies.ticket_termico_strategy import TicketTermicoStrategy

__all__ = ["RenderStrategy", "RideA4Strategy", "TicketTermicoStrategy", "PlantillaPreimpresaStrategy"]
