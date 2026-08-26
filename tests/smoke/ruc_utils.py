import random
import re

def generar_ruc_persona_natural():
    """Genera un RUC válido para persona natural.
    Usa el algoritmo para personas naturales (tercer dígito 0-5)
    con validación módulo 10 en posición 10.
    """
    # provincia 01-24
    provincia = str(random.randint(1, 24)).zfill(2)
    # tercer dígito 0-5 para persona natural
    tercer_digito = str(random.randint(0, 5))
    # 6 dígitos aleatorios
    cuerpo = ''.join([str(random.randint(0,9)) for _ in range(6)])
    # establecimiento siempre 001
    establecimiento = "001"

    # Módulo 10 usando coeficientes 2,1,2,1,2,1,2,1,2
    base = f"{provincia}{tercer_digito}{cuerpo}"
    coeficientes = [2,1,2,1,2,1,2,1,2]
    suma = 0
    for i, coef in enumerate(coeficientes):
        valor = int(base[i]) * coef
        if valor > 9:
            valor -= 9
        suma += valor
    verificador = 0 if suma % 10 == 0 else 10 - (suma % 10)

    return f"{provincia}{tercer_digito}{cuerpo}{verificador}{establecimiento}"

def generar_ruc_empresa():
    """Genera un RUC válido para empresa (sociedad).
    Usa el algoritmo oficial para tercer dígito=9 (empresa privada)
    con dígito verificador en posición 10.
    """
    # provincia 01-24 (Ecuador tiene 24 provincias)
    provincia = str(random.randint(1, 24)).zfill(2)
    # tercer dígito = 9 para empresas privadas
    tercer_digito = "9"
    # 6 dígitos aleatorios para el cuerpo (posiciones 4-9)
    cuerpo = ''.join([str(random.randint(0,9)) for _ in range(6)])
    # establecimiento siempre 001
    establecimiento = "001"

    # Calculamos dígito verificador posición 10 (coeficientes módulo 11)
    # Los coeficientes se aplican a las posiciones 0-8 de la base (9 dígitos)
    coeficientes_privada = [4,3,2,7,6,5,4,3,2]
    base = f"{provincia}{tercer_digito}{cuerpo}"
    suma = sum(int(d) * c for d, c in zip(base, coeficientes_privada))
    resto = suma % 11
    verificador = 0 if resto == 0 else 11 - resto
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 1

    return f"{provincia}{tercer_digito}{cuerpo}{verificador}{establecimiento}"

def validar_ruc_empresa(ruc):
    """Valida un RUC de sociedad (tercer dígito = 9).
    Returns: bool indicando si el RUC es válido.
    """
    if not ruc or not isinstance(ruc, str):
        return False
    if not re.match(r'^\d{13}$', ruc):
        return False
    if ruc[2] != '9':  # tercer dígito debe ser 9 para sociedades
        return False
    # provincia 01-24
    provincia = int(ruc[0:2])
    if not 1 <= provincia <= 24:
        return False
    # verificar dígito
    base = ruc[:-1]
    coeficientes = [4,3,2,7,6,5,4,3,2,7,6,5,4]
    suma = sum(int(d) * c for d, c in zip(base, coeficientes))
    verificador = 11 - (suma % 11)
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 1
    return str(verificador) == ruc[-1]

def validar_ruc_persona_natural(ruc):
    """Valida un RUC de persona natural (tercer dígito 0-5).
    Returns: bool indicando si el RUC es válido.
    """
    if not ruc or not isinstance(ruc, str):
        return False
    if not re.match(r'^\d{13}$', ruc):
        return False
    tercer_digito = int(ruc[2])
    if not 0 <= tercer_digito <= 5:  # tercer dígito 0-5 para personas naturales
        return False
    # provincia 01-24
    provincia = int(ruc[0:2])
    if not 1 <= provincia <= 24:
        return False

    # Verificar dígito usando algoritmo módulo 10
    base = ruc[:9]
    sum_pares = sum(int(base[i]) for i in range(0, len(base), 2))
    sum_impares = 0
    for i in range(1, len(base), 2):
        num = int(base[i]) * 2
        if num > 9:
            num -= 9
        sum_impares += num
    total = sum_pares + sum_impares
    verificador = (10 - (total % 10)) % 10

    return str(verificador) == ruc[9] and ruc[10:] == "001"