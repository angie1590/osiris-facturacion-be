#!/usr/bin/env python3
"""
Script de validación de configuración multiplataforma (Mac/Windows/Linux)
Verifica que el entorno esté correctamente configurado antes de ejecutar la aplicación.
"""
import sys
from pathlib import Path
import subprocess
import platform

# Colores para terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_success(text: str):
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    print(f"{YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    print(f"{BLUE}ℹ{RESET} {text}")


def check_os():
    """Verifica el sistema operativo"""
    print_header("Sistema Operativo")
    os_name = platform.system()
    os_version = platform.version()
    architecture = platform.machine()

    print_info(f"Sistema: {os_name}")
    print_info(f"Versión: {os_version}")
    print_info(f"Arquitectura: {architecture}")

    if os_name == "Windows":
        print_success("Windows detectado")
        return "windows"
    elif os_name == "Darwin":
        print_success("macOS detectado")
        return "mac"
    elif os_name == "Linux":
        print_success("Linux detectado")
        return "linux"
    else:
        print_warning(f"Sistema operativo no reconocido: {os_name}")
        return "unknown"


def check_docker():
    """Verifica instalación de Docker"""
    print_header("Docker")
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        print_success(f"Docker instalado: {version}")

        # Verificar que Docker está corriendo
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success("Docker daemon está corriendo")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("Docker no está instalado o no está corriendo")
        print_info("Instala Docker Desktop desde: https://www.docker.com/products/docker-desktop")
        return False


def check_docker_compose():
    """Verifica Docker Compose"""
    print_header("Docker Compose")
    try:
        # Intentar con plugin moderno
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        print_success(f"Docker Compose (plugin) instalado: {version}")
        return True
    except subprocess.CalledProcessError:
        # Intentar con binario legacy
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            version = result.stdout.strip()
            print_warning(f"Docker Compose (legacy) instalado: {version}")
            print_info("Considera actualizar a Docker Compose plugin (docker compose)")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_error("Docker Compose no está instalado")
            return False


def check_wsl2(os_type):
    """Verifica WSL2 en Windows"""
    if os_type != "windows":
        return True

    print_header("WSL2 (Windows)")
    try:
        # Intentar primero con --status
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Si el comando funciona, verificar la salida
        if result.returncode == 0:
            if "WSL 2" in result.stdout or "versión 2" in result.stdout or "version 2" in result.stdout.lower():
                print_success("WSL2 está activo")
                return True
            else:
                print_warning("WSL2 podría no estar configurado como predeterminado")
                print_info("Ejecuta: wsl --set-default-version 2")
                # No es crítico, retornar True para continuar
                return True

        # Si --status no funciona, intentar listar distribuciones
        result = subprocess.run(
            ["wsl", "--list", "--verbose"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout:
            print_warning("WSL instalado pero no se pudo verificar versión 2")
            print_info("Docker Desktop debería funcionar correctamente con WSL backend")
            return True

        # WSL no responde adecuadamente
        print_warning("No se pudo verificar WSL2 completamente")
        print_info("Si Docker Desktop funciona, WSL2 está configurado correctamente")
        return True  # No bloquear si Docker funciona

    except subprocess.TimeoutExpired:
        print_warning("WSL no responde (timeout)")
        print_info("Si Docker Desktop funciona, la configuración es correcta")
        return True
    except FileNotFoundError:
        print_error("WSL no está instalado")
        print_info("Instala WSL2 desde: https://docs.microsoft.com/en-us/windows/wsl/install")
        print_info("O usa Docker Desktop con Hyper-V (menos recomendado)")
        return False


def check_env_file():
    """Verifica archivo .env.development"""
    print_header("Archivos de Configuración")

    env_file = Path(".env.development")
    if env_file.exists():
        print_success(f".env.development encontrado: {env_file.absolute()}")

        # Verificar variables críticas base
        required_vars = [
            "ENVIRONMENT",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "DATABASE_URL",
            "SRI_MODO_EMISION",
            "FEEC_AMBIENTE",
            "FEEC_TIPO_EMISION",
            "FEEC_REGIMEN",
        ]

        with open(env_file, 'r') as f:
            content = f.read()

        env_vars = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip().strip('"').strip("'")

        missing_vars = []
        for var in required_vars:
            if var not in env_vars:
                missing_vars.append(var)

        # FE-EC electrónica requiere certificados.
        if env_vars.get("SRI_MODO_EMISION", "").upper() == "ELECTRONICO":
            for var in ("FEEC_P12_PATH", "FEEC_P12_PASSWORD", "FEEC_XSD_PATH"):
                if var not in env_vars:
                    missing_vars.append(var)

        if missing_vars:
            print_error(f"Variables faltantes en .env.development: {', '.join(missing_vars)}")
            return False
        else:
            print_success("Todas las variables requeridas están presentes")

        # Verificar line endings en Windows
        if platform.system() == "Windows":
            with open(env_file, 'rb') as f:
                content_bytes = f.read()
            if b'\r\n' in content_bytes:
                print_warning(".env.development tiene line endings CRLF (Windows)")
                print_info("Recomendado convertir a LF para compatibilidad")
                print_info("Comando: dos2unix .env.development")
            else:
                print_success(".env.development tiene line endings LF correctos")

        return True
    else:
        print_error(".env.development NO encontrado")
        print_info("Crea el archivo .env.development siguiendo el ejemplo del README")
        return False


def check_required_files():
    """Verifica archivos requeridos"""
    print_header("Archivos Requeridos del Proyecto")

    required_files = [
        ("pyproject.toml", "Configuración de Poetry"),
        ("Dockerfile.dev", "Dockerfile de desarrollo"),
        ("docker-compose.yml", "Configuración de Docker Compose"),
        ("Makefile", "Comandos de desarrollo"),
        ("conf/aux_impuesto_catalogo.json", "Catálogo de impuestos SRI"),
    ]

    all_present = True
    for file_path, description in required_files:
        if Path(file_path).exists():
            print_success(f"{description}: {file_path}")
        else:
            print_error(f"{description} NO encontrado: {file_path}")
            all_present = False

    # Verificar archivos sensibles (opcional)
    sensitive_files = [
        ("conf/firma.p12", "Certificado digital (.p12)"),
        ("conf/sri_docs/factura_V1_1.xsd", "Esquema XSD del SRI"),
    ]

    print("\nArchivos sensibles (opcionales para desarrollo):")
    for file_path, description in sensitive_files:
        if Path(file_path).exists():
            print_success(f"{description}: {file_path}")
        else:
            print_warning(f"{description} NO encontrado: {file_path}")
            print_info("  (Necesario solo para firmar documentos electrónicos)")

    return all_present


def check_docker_import_path():
    """Verifica que Docker use el mismo import path que local (sin hacks de PYTHONPATH)."""
    print_header("Configuración de Import Path")

    dockerfile = Path("Dockerfile.dev")
    if not dockerfile.exists():
        print_error("Dockerfile.dev no encontrado")
        return False

    with open(dockerfile, 'r') as f:
        content = f.read()

    # No usar PYTHONPATH manual; importar paquete igual que en local.
    if "ENV PYTHONPATH=" in content:
        print_error("Dockerfile.dev define PYTHONPATH manualmente (no recomendado)")
        print_info("Usa imports `osiris.*` sin hacks de path")
        return False
    else:
        print_success("Dockerfile.dev no depende de PYTHONPATH manual")

    # Verificar CMD
    if '"osiris.main:app"' in content:
        print_success('CMD usa "osiris.main:app" (correcto)')
    elif '"src.osiris.main:app"' in content:
        print_error('CMD usa "src.osiris.main:app" (INCORRECTO)')
        print_info("Debe ser: osiris.main:app para coincidir con local y Docker")
        return False
    else:
        print_warning("No se pudo verificar el módulo en CMD")

    if "COPY osiris ./osiris" in content:
        print_success("Dockerfile.dev copia paquete puente `osiris/`")
    else:
        print_warning("Dockerfile.dev no copia `osiris/`; verifica imports en runtime")

    return True


def check_docker_compose_config():
    """Verifica configuración de docker-compose.yml"""
    print_header("Configuración de Docker Compose")

    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        print_error("docker-compose.yml no encontrado")
        return False

    with open(compose_file, 'r') as f:
        content = f.read()

    # Verificar que no tenga platform específico
    if "platform: linux/arm64" in content:
        print_error("docker-compose.yml tiene platform: linux/arm64 (incompatible con Windows)")
        print_info("Elimina la línea 'platform: linux/arm64' para compatibilidad multiplataforma")
        return False
    else:
        print_success("docker-compose.yml no tiene restricción de platform (correcto)")

    # Verificar volumes
    if "- .:/app" in content or "- ./:/app" in content:
        print_success("Volume mount configurado correctamente")
    else:
        print_warning("Volume mount podría no estar configurado")

    return True


def main():
    print_header("VALIDACIÓN DE CONFIGURACIÓN OSIRIS-BE")
    print_info("Validando entorno de desarrollo multiplataforma\n")

    # Sistema operativo
    os_type = check_os()

    # Docker
    docker_ok = check_docker()
    compose_ok = check_docker_compose()

    # WSL2 (solo Windows)
    wsl_ok = check_wsl2(os_type) if os_type == "windows" else True

    # Archivos
    env_ok = check_env_file()
    files_ok = check_required_files()

    # Configuración
    import_path_ok = check_docker_import_path()
    compose_config_ok = check_docker_compose_config()

    # Resumen final
    print_header("RESUMEN DE VALIDACIÓN")

    all_checks = [
        ("Docker instalado", docker_ok),
        ("Docker Compose disponible", compose_ok),
        ("WSL2 activo (Windows)", wsl_ok),
        (".env.development configurado", env_ok),
        ("Archivos del proyecto presentes", files_ok),
        ("Import path Docker/local consistente", import_path_ok),
        ("docker-compose.yml compatible", compose_config_ok),
    ]

    passed = sum(1 for _, ok in all_checks if ok)
    total = len(all_checks)

    for check_name, ok in all_checks:
        if ok:
            print_success(check_name)
        else:
            print_error(check_name)

    print(f"\n{BLUE}{'=' * 60}{RESET}")
    if passed == total:
        print(f"{GREEN}✓ Todas las validaciones pasaron ({passed}/{total}){RESET}")
        print(f"\n{GREEN}El entorno está listo para desarrollo.{RESET}")
        print(f"{BLUE}Ejecuta: make run{RESET}")
        return 0
    else:
        print(f"{RED}✗ Algunas validaciones fallaron ({passed}/{total}){RESET}")
        print(f"\n{YELLOW}Corrige los errores antes de continuar.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
