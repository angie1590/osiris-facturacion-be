import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    supervisor = "supervisor"


class IdentificationType(str, enum.Enum):
    ruc = "ruc"
    cedula = "cedula"
    pasaporte = "pasaporte"
    consumidor_final = "consumidor_final"


class ComprobanteTipo(str, enum.Enum):
    factura = "01"
    nota_credito = "04"
    nota_debito = "05"
    guia_remision = "06"
    retencion = "07"


class TipoPersona(str, enum.Enum):
    cliente = "cliente"
    proveedor = "proveedor"
