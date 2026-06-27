#!/usr/bin/env bash
# Aura-X Trader - Script Principal de Ejecución
# Sistema de Trading Institucional con IA

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║              🧠  AURA-X TRADER INSTITUCIONAL  🧠                ║"
echo "║                                                                  ║"
echo "║         Plataforma de Trading con IA - Perfil Balanceado        ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Activar venv
if [ -d "../venv" ]; then
    source ../venv/bin/activate
    echo -e "${GREEN}✅ Entorno virtual activado${NC}"
else
    echo -e "${YELLOW}⚠️  No se encontró venv, usando Python del sistema${NC}"
fi

# Cambiar al directorio del proyecto
cd "$(dirname "$0")"

# Menú principal
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    MENÚ PRINCIPAL                              ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  1. 🚀 Iniciar bot de trading (paper trading)"
echo "  2. 🧪 Ejecutar tests de estrategia XAUUSD"
echo "  3. 📊 Generar reporte diario (Daily Intel)"
echo "  4. 🔍 Verificar estado del sistema"
echo "  5. 📝 Ver DAILY_INTEL.md"
echo "  6. 📋 Ver config.json"
echo "  7. 💾 Poblar base de datos con trades de prueba"
echo "  8. 🧠 Ver reglas de Trae (.trae/rules.md)"
echo "  9. ❌ Salir"
echo ""
echo -n "Selecciona opción [1-9]: "
read opcion

case $opcion in
    1)
        echo -e "${YELLOW}⚠️  Paper trading - aún no implementado completamente${NC}"
        echo "Por favor, conecta MT5 y ejecuta: python3 services/mt5_integration.py"
        ;;
    2)
        echo -e "${CYAN}🧪 Ejecutando tests de estrategia XAUUSD...${NC}"
        python3 test_xauusd_strategy.py
        ;;
    3)
        echo -e "${CYAN}📊 Generando reporte diario...${NC}"
        python3 generate_daily_intel.py
        echo -e "${GREEN}✅ Reporte generado en DAILY_INTEL.md${NC}"
        ;;
    4)
        echo -e "${CYAN}🔍 Verificando sistema...${NC}"
        python3 system_monitor.py
        ;;
    5)
        if [ -f "DAILY_INTEL.md" ]; then
            cat DAILY_INTEL.md
        else
            echo -e "${RED}❌ DAILY_INTEL.md no existe. Genera primero (opción 3)${NC}"
        fi
        ;;
    6)
        if [ -f "config.json" ]; then
            cat config.json | python3 -m json.tool
        else
            echo -e "${RED}❌ config.json no existe${NC}"
        fi
        ;;
    7)
        echo -e "${CYAN}💾 Poblando base de datos...${NC}"
        python3 populate_sample_trades.py
        ;;
    8)
        if [ -f ".trae/rules.md" ]; then
            cat .trae/rules.md
        else
            echo -e "${RED}❌ .trae/rules.md no existe${NC}"
        fi
        ;;
    9)
        echo -e "${GREEN}👋 Saliendo...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Opción inválida${NC}"
        exit 1
        ;;
esac
