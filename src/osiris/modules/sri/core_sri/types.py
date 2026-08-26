from __future__ import annotations

from enum import Enum


class TipoIdentificacionSRI(str, Enum):
    RUC = "RUC"
    CEDULA = "CEDULA"
    PASAPORTE = "PASAPORTE"


class FormaPagoSRI(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"


class TipoImpuestoMVP(str, Enum):
    IVA = "IVA"
    ICE = "ICE"


class TipoRetencionSRI(str, Enum):
    RENTA = "RENTA"
    IVA = "IVA"


class EstadoRetencion(str, Enum):
    REGISTRADA = "REGISTRADA"
    BORRADOR = "BORRADOR"
    ENCOLADA = "ENCOLADA"
    EMITIDA = "EMITIDA"
    ANULADA = "ANULADA"


class EstadoVenta(str, Enum):
    BORRADOR = "BORRADOR"
    EMITIDA = "EMITIDA"
    ANULADA = "ANULADA"
    PENDIENTE = BORRADOR


class TipoEmisionVenta(str, Enum):
    ELECTRONICA = "ELECTRONICA"
    NOTA_VENTA_FISICA = "NOTA_VENTA_FISICA"


class EstadoCompra(str, Enum):
    BORRADOR = "BORRADOR"
    REGISTRADA = "REGISTRADA"
    ANULADA = "ANULADA"
    PENDIENTE = BORRADOR
    PAGADA = REGISTRADA


class EstadoCuentaPorPagar(str, Enum):
    PENDIENTE = "PENDIENTE"
    PARCIAL = "PARCIAL"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class EstadoCuentaPorCobrar(str, Enum):
    PENDIENTE = "PENDIENTE"
    PARCIAL = "PARCIAL"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class SustentoTributarioSRI(str, Enum):
    CREDITO_TRIBUTARIO_BIENES = "01"
    CREDITO_TRIBUTARIO_SERVICIOS = "02"
    SIN_CREDITO_TRIBUTARIO = "05"


class EstadoDocumentoElectronico(str, Enum):
    EN_COLA = "EN_COLA"
    FIRMADO = "FIRMADO"
    RECIBIDO = "RECIBIDO"
    ENVIADO = "ENVIADO"
    AUTORIZADO = "AUTORIZADO"
    RECHAZADO = "RECHAZADO"
    DEVUELTO = "DEVUELTO"


class TipoDocumentoElectronico(str, Enum):
    FACTURA = "FACTURA"
    RETENCION = "RETENCION"


class EstadoSriDocumento(str, Enum):
    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    REINTENTO = "REINTENTO"
    AUTORIZADO = "AUTORIZADO"
    RECHAZADO = "RECHAZADO"
    ERROR = "ERROR"


class EstadoColaSri(str, Enum):
    PENDIENTE = "PENDIENTE"
    PROCESANDO = "PROCESANDO"
    REINTENTO_PROGRAMADO = "REINTENTO_PROGRAMADO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"


class EstadoRetencionRecibida(str, Enum):
    BORRADOR = "BORRADOR"
    APLICADA = "APLICADA"
    ANULADA = "ANULADA"
