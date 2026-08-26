#!/usr/bin/env bash
# Script bash simple de validación para sistemas sin Python disponible

set -e

echo "=========================================="
echo "   VALIDACIÓN RÁPIDA OSIRIS-BE"
echo "=========================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Verificar Docker
echo "Verificando Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    success "Docker instalado: $DOCKER_VERSION"
else
    error "Docker no está instalado"
    exit 1
fi

# Verificar Docker Compose
echo ""
echo "Verificando Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    success "Docker Compose plugin: $COMPOSE_VERSION"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    warning "Docker Compose legacy: $COMPOSE_VERSION"
else
    error "Docker Compose no está disponible"
    exit 1
fi

# Verificar .env.development
echo ""
echo "Verificando archivos de configuración..."
if [ -f ".env.development" ]; then
    success ".env.development existe"
else
    error ".env.development NO encontrado"
    echo "  Crea el archivo siguiendo el ejemplo del README"
    exit 1
fi

# Verificar archivos críticos
echo ""
echo "Verificando archivos del proyecto..."
REQUIRED_FILES=(
    "pyproject.toml"
    "Dockerfile.dev"
    "docker-compose.yml"
    "Makefile"
    "conf/aux_impuesto_catalogo.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        success "$file existe"
    else
        error "$file NO encontrado"
        exit 1
    fi
done

# Verificar configuración en docker-compose.yml
echo ""
echo "Verificando docker-compose.yml..."
if grep -q "platform: linux/arm64" docker-compose.yml; then
    error "docker-compose.yml contiene 'platform: linux/arm64'"
    echo "  Esto causa incompatibilidad con Windows/Linux AMD64"
    echo "  Elimina esa línea para compatibilidad multiplataforma"
    exit 1
else
    success "docker-compose.yml compatible (sin restricción de platform)"
fi

# Verificar Dockerfile.dev
echo ""
echo "Verificando Dockerfile.dev..."
if grep -q 'ENV PYTHONPATH=' Dockerfile.dev; then
    error "Dockerfile.dev define PYTHONPATH manualmente (no permitido)"
    echo "  Usa imports osiris.* sin hacks de path"
    exit 1
else
    success "Dockerfile.dev no depende de PYTHONPATH manual"
fi

if grep -q '"osiris.main:app"' Dockerfile.dev; then
    success 'CMD usa "osiris.main:app" (correcto)'
elif grep -q '"src.osiris.main:app"' Dockerfile.dev; then
    error 'CMD usa "src.osiris.main:app" (INCORRECTO)'
    echo "  Debe ser: osiris.main:app para coincidir con local y Docker"
    exit 1
fi

if grep -q 'COPY osiris ./osiris' Dockerfile.dev; then
    success 'Dockerfile.dev copia paquete puente osiris/'
else
    warning 'Dockerfile.dev no copia osiris/ (revisar imports en runtime)'
fi

# Resumen
echo ""
echo "=========================================="
echo -e "${GREEN}✓ Todas las validaciones pasaron${NC}"
echo "=========================================="
echo ""
echo "El entorno está listo. Ejecuta:"
echo "  make run"
echo ""

exit 0
