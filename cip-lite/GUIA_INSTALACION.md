# GUÍA DE INSTALACIÓN - Aura-X Trader v1.0.0

**Fecha:** 2026-06-27
**Versión:** 1.0.0-AURA-X
**Sistema Operativo:** Linux (Ubuntu/Zorin), macOS, Windows con WSL

---

## 📋 REQUISITOS PREVIOS

### Hardware Mínimo:
- CPU: Intel i5 6ta Gen o equivalente
- RAM: 8GB mínimo (16GB recomendado)
- Disco: 1GB libre mínimo
- Internet: Conexión estable

### Software:
- Python 3.8 o superior
- pip 21.0 o superior
- Git 2.25 o superior
- (Opcional) Rust 1.70+ para fast-path

---

## 🚀 INSTALACIÓN PASO A PASO

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/bot-trader-institucional.git
cd "bot trader institucional"
```

### Paso 2: Cambiar a la Versión 1.0.0

```bash
git checkout v1.0.0-aura-x
```

### Paso 3: Crear Entorno Virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows
```

### Paso 4: Instalar Dependencias

```bash
cd cip-lite
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-linux.txt  # Si aplica
```

### Paso 5: Configurar Variables de Entorno

```bash
# Crear archivo .env en cip-lite/
cat > .env << EOF
# Broker Configuration
MT5_LOGIN=tu_login
MT5_PASSWORD=tu_password
MT5_SERVER=tu_servidor

# Pepperstone (Recomendado para producción)
PEPPERSTONE_LOGIN=
PEPPERSTONE_PASSWORD=
PEPPERSTONE_SERVER=

# Telegram (Opcional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# OpenRouter (Para Hermes)
OPENROUTER_API_KEY=
EOF
```

### Paso 6: Validar Instalación

```bash
python3 system_monitor.py
```

**Resultado esperado:**
```
✅ PASADOS: 16/16
🎉 SISTEMA OPERATIVO Y LISTO PARA OPERAR
```

---

## ⚙️ CONFIGURACIÓN DEL BROKER

### Opción A: Pepperstone (Recomendado para Latencia)

**Ventajas:**
- cTrader nativo para Linux
- Latencia < 5ms
- Spreads ajustados

**Configuración:**
```json
{
  "broker": {
    "primary": "Pepperstone",
    "primary_type": "ctrader_open_api",
    "primary_host": "live.ctraderapi.com"
  }
}
```

### Opción B: Exness (Compatible con MT5)

**Ventajas:**
- Soporte MetaTrader 5 completo
- Compatible con shadow mode
- Buena para paper trading

**Configuración:**
```json
{
  "broker": {
    "fallback": "Exness",
    "fallback_type": "metaapi"
  }
}
```

---

## 🧪 VERIFICACIÓN POST-INSTALACIÓN

### Test 1: Estrategia XAUUSD
```bash
python3 test_xauusd_strategy.py
```
**Esperado:** 4 tests PASADOS

### Test 2: Sistema Original
```bash
python3 -m pytest tests/test_mt5_system.py -v
```
**Esperado:** 18 tests (16 PASSED + 2 SKIPPED)

### Test 3: Monitor
```bash
python3 system_monitor.py
```
**Esperado:** 16/16 checks PASADOS

### Test 4: Generador Daily Intel
```bash
python3 populate_sample_trades.py
python3 generate_daily_intel.py
cat DAILY_INTEL.md
```
**Esperado:** Reporte generado correctamente

---

## 🖥️ USO DEL MENÚ PRINCIPAL

```bash
./aura_x.sh
```

**Opciones disponibles:**

1. 🚀 Iniciar bot de trading (paper trading)
2. 🧪 Ejecutar tests de estrategia XAUUSD
3. 📊 Generar reporte diario (Daily Intel)
4. 🔍 Verificar estado del sistema
5. 📝 Ver DAILY_INTEL.md
6. 📋 Ver config.json
7. 💾 Poblar base de datos con trades de prueba
8. 🧠 Ver reglas de Trae (.trae/rules.md)
9. ❌ Salir

---

## 🔧 CONFIGURACIÓN AVANZADA

### Modificar Parámetros de Estrategia

Editar `cip-lite/config.json`:

```json
{
  "assets": [
    {
      "symbol": "XAUUSD",
      "filters": {
        "max_spread_points": 50.0,    // Spread máximo permitido
        "min_candle_body_percent": 30.0,  // Cuerpo mínimo de vela
        "blacklist_hours_utc": [22, 23]  // Horas bloqueadas
      },
      "exit_strategy": {
        "base_sl_points": 100,        // Stop Loss en points
        "base_tp_points": 150,        // Take Profit en points
        "breakeven_trigger_points": 60,  // BE trigger
        "trailing_step_points": 30    // Trailing step
      }
    }
  ]
}
```

### Programar Reporte Diario Automático

```bash
# Crontab: ejecutar a las 23:00 UTC cada día
crontab -e

# Agregar línea:
0 23 * * * cd /path/to/cip-lite && source ../venv/bin/activate && python3 generate_daily_intel.py
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### Error: "MT5 no conecta"
```bash
# Verificar que MT5 esté instalado
which mt5
# Si no existe, instalar:
sudo apt install mt5
```

### Error: "No se generan señales"
```bash
# Verificar horario (no debe estar en blacklist)
python3 -c "
from datetime import datetime
print('Hora UTC:', datetime.utcnow().hour)
"
```

### Error: "DB not found"
```bash
# El directorio data/ se crea automáticamente
mkdir -p cip-lite/data
python3 populate_sample_trades.py
```

### Error: "JSON inválido en config.json"
```bash
python3 -c "import json; json.load(open('cip-lite/config.json'))"
```

---

## 📚 DOCUMENTACIÓN RELACIONADA

- [CHANGELOG.md](CHANGELOG.md) - Historial de versiones
- [REGISTRO_TAREAS_v1.0.0.md](REGISTRO_TAREAS_v1.0.0.md) - Tareas completadas
- [RESUMEN_IMPLEMENTACION.md](RESUMEN_IMPLEMENTACION.md) - Resumen técnico
- [ANALISIS_ESTRATEGIA_CHAT.md](ANALISIS_ESTRATEGIA_CHAT.md) - Análisis estratégico
- [.trae/rules.md](.trae/rules.md) - Reglas para IA

---

## 🆘 SOPORTE

Para problemas o preguntas:

1. **Revisar documentación** - La mayoría de respuestas están aquí
2. **Ejecutar system_monitor.py** - Diagnóstico automático
3. **Revisar logs** - `logs/` directory
4. **Generar Daily Intel** - Estado más reciente

---

**Instalación completada exitosamente.**
**Versión:** 1.0.0-AURA-X
**Fecha:** 2026-06-27
