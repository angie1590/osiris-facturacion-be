from enum import Enum

class TipoIdentificacionEnum(Enum):
    CEDULA = 0
    RUC_PERSONA_NATURAL = 1
    RUC_SOCIEDAD_PRIVADA = 2
    RUC_SOCIEDAD_PUBLICA = 3


class ValidacionCedulaRucService:
    @staticmethod
    def es_identificacion_valida(identificacion: str) -> bool:
        if not identificacion:
            return False

        longitud = len(identificacion)
        if not ValidacionCedulaRucService._es_numero_identificacion_valida(identificacion, longitud):
            return False

        if longitud == 10:
            return ValidacionCedulaRucService.es_cedula_valida(identificacion)
        elif longitud == 13:
            tercer_digito = int(identificacion[2])
            if 0 <= tercer_digito <= 5:
                return ValidacionCedulaRucService.es_ruc_persona_natural_valido(identificacion)
            elif tercer_digito == 6:
                return ValidacionCedulaRucService.es_ruc_sociedad_publica_valido(identificacion)
            elif tercer_digito == 9:
                return ValidacionCedulaRucService.es_ruc_sociedad_privada_valido(identificacion)

        return False

    @staticmethod
    def es_cedula_valida(numero_cedula: str) -> bool:
        if not ValidacionCedulaRucService._validaciones_previas(numero_cedula, 10, TipoIdentificacionEnum.CEDULA):
            return False

        ultimo_digito = int(numero_cedula[9])
        return ValidacionCedulaRucService._algoritmo_verifica_identificacion(numero_cedula, ultimo_digito, TipoIdentificacionEnum.CEDULA)

    @staticmethod
    def es_ruc_persona_natural_valido(numero_ruc: str) -> bool:
        if not ValidacionCedulaRucService._validaciones_previas(numero_ruc, 13, TipoIdentificacionEnum.RUC_PERSONA_NATURAL):
            return False

        return ValidacionCedulaRucService._algoritmo_verifica_identificacion(numero_ruc, int(numero_ruc[9]), TipoIdentificacionEnum.RUC_PERSONA_NATURAL)

    @staticmethod
    def es_ruc_sociedad_privada_valido(numero_ruc: str) -> bool:
        if not ValidacionCedulaRucService._validaciones_previas(numero_ruc, 13, TipoIdentificacionEnum.RUC_SOCIEDAD_PRIVADA):
            return False

        return ValidacionCedulaRucService._algoritmo_verifica_identificacion(numero_ruc, int(numero_ruc[9]), TipoIdentificacionEnum.RUC_SOCIEDAD_PRIVADA)

    @staticmethod
    def es_ruc_sociedad_publica_valido(numero_ruc: str) -> bool:
        if not ValidacionCedulaRucService._validaciones_previas(numero_ruc, 13, TipoIdentificacionEnum.RUC_SOCIEDAD_PUBLICA):
            return False

        return ValidacionCedulaRucService._algoritmo_verifica_identificacion(numero_ruc, int(numero_ruc[8]), TipoIdentificacionEnum.RUC_SOCIEDAD_PUBLICA)

    @staticmethod
    def _es_numero_identificacion_valida(identificacion: str, longitud: int) -> bool:
        return len(identificacion) == longitud and identificacion.isdigit()

    @staticmethod
    def _es_codigo_provincia_valido(identificacion: str) -> bool:
        numero_provincia = int(identificacion[:2])
        return 1 <= numero_provincia <= 24

    @staticmethod
    def _es_codigo_establecimiento_valido(identificacion: str) -> bool:
        return identificacion[10:13] == "001"

    @staticmethod
    def _es_tercer_digito_valido(identificacion: str, tipo: TipoIdentificacionEnum) -> bool:
        digito = int(identificacion[2])
        if tipo == TipoIdentificacionEnum.CEDULA:
            return 0 <= digito <= 5
        elif tipo == TipoIdentificacionEnum.RUC_PERSONA_NATURAL:
            return 0 <= digito <= 5
        elif tipo == TipoIdentificacionEnum.RUC_SOCIEDAD_PRIVADA:
            return digito == 9
        elif tipo == TipoIdentificacionEnum.RUC_SOCIEDAD_PUBLICA:
            return digito == 6
        return False

    @staticmethod
    def _validaciones_previas(identificacion: str, longitud: int, tipo: TipoIdentificacionEnum) -> bool:
        return (
            ValidacionCedulaRucService._es_numero_identificacion_valida(identificacion, longitud) and
            ValidacionCedulaRucService._es_codigo_provincia_valido(identificacion) and
            ValidacionCedulaRucService._es_tercer_digito_valido(identificacion, tipo) and
            (tipo == TipoIdentificacionEnum.CEDULA or ValidacionCedulaRucService._es_codigo_establecimiento_valido(identificacion))
        )

    @staticmethod
    def _obtener_coeficientes(tipo: TipoIdentificacionEnum):
        if tipo in (TipoIdentificacionEnum.CEDULA, TipoIdentificacionEnum.RUC_PERSONA_NATURAL):
            return [2, 1, 2, 1, 2, 1, 2, 1, 2]
        elif tipo == TipoIdentificacionEnum.RUC_SOCIEDAD_PRIVADA:
            return [4, 3, 2, 7, 6, 5, 4, 3, 2]
        elif tipo == TipoIdentificacionEnum.RUC_SOCIEDAD_PUBLICA:
            return [3, 2, 7, 6, 5, 4, 3, 2]
        return []

    @staticmethod
    def _algoritmo_verifica_identificacion(identificacion: str, digito_verificador: int, tipo: TipoIdentificacionEnum) -> bool:
        coeficientes = ValidacionCedulaRucService._obtener_coeficientes(tipo)
        suma = 0

        for i in range(len(coeficientes)):
            valor = int(identificacion[i]) * coeficientes[i]
            suma += ValidacionCedulaRucService._sumatoria_multiplicacion(valor, tipo)

        return digito_verificador == ValidacionCedulaRucService._obtener_digito_verificador(suma, tipo)

    @staticmethod
    def _sumatoria_multiplicacion(multiplicacion: int, tipo: TipoIdentificacionEnum) -> int:
        if tipo == TipoIdentificacionEnum.CEDULA:
            return multiplicacion if multiplicacion < 10 else multiplicacion - 9
        elif tipo == TipoIdentificacionEnum.RUC_PERSONA_NATURAL:
            return sum(int(d) for d in str(multiplicacion))
        return multiplicacion

    @staticmethod
    def _obtener_digito_verificador(suma: int, tipo: TipoIdentificacionEnum) -> int:
        if tipo in (TipoIdentificacionEnum.CEDULA, TipoIdentificacionEnum.RUC_PERSONA_NATURAL):
            return 0 if suma % 10 == 0 else 10 - (suma % 10)
        elif tipo in (TipoIdentificacionEnum.RUC_SOCIEDAD_PRIVADA, TipoIdentificacionEnum.RUC_SOCIEDAD_PUBLICA):
            return 0 if suma % 11 == 0 else 11 - (suma % 11)
        return -1
