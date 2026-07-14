#!/usr/bin/env python3
"""
CIP-Lite v2.0 - Sistema de Trading Algorítmico Modular
Punto de entrada principal del sistema
Integración: hot-reload config.json, ciclo diario de inteligencia, ONNX
"""

import asyncio
import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta

# Agregar directorios al path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger("Main")

# Módulos del sistema
# Nota: ConfigManager no existe en services.config, se usa ConfigHotReload directamente
from services.cline_trading_bot import ClineTradingBot

# ==================== HOT-RELOAD CONFIG ====================

class ConfigHotReload:
    """
    Monitorea config.json y recarga cambios automáticamente.
    Usa stat() para polling ligero sin inotify.
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.last_mtime = 0
        self.config = {}
        self._load()
    
    def _load(self):
        """Carga config.json si existe"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            self.last_mtime = os.path.getmtime(self.config_path)
            logger.info(f"Config cargada: {len(self.config)} keys")
        else:
            logger.warning(f"Config no encontrada: {self.config_path}")
            self.config = {}
    
    def check_reload(self) -> bool:
        """
        Verifica si config.json cambió y recarga si es necesario.
        Retorna True si hubo recarga.
        """
        if not os.path.exists(self.config_path):
            return False
        
        current_mtime = os.path.getmtime(self.config_path)
        if current_mtime > self.last_mtime:
            try:
                with open(self.config_path, 'r') as f:
                    new_config = json.load(f)
                
                # Detectar cambios
                changes = []
                for key in set(list(self.config.keys()) + list(new_config.keys())):
                    if key not in self.config:
                        changes.append(f"+ {key}")
                    elif key not in new_config:
                        changes.append(f"- {key}")
                    elif self.config[key] != new_config[key]:
                        old = self.config[key]
                        new = new_config[key]
                        changes.append(f"~ {key}: {old} -> {new}")
                
                self.config = new_config
                self.last_mtime = current_mtime
                
                if changes:
                    logger.info(f"Config recargada: {len(changes)} cambios")
                    for c in changes:
                        logger.info(f"  {c}")
                
                return True
                
            except Exception as e:
                logger.error(f"Error recargando config: {e}")
                return False
        
        return False
    
    def get(self, key, default=None):
        """Obtiene valor de config con fallback"""
        return self.config.get(key, default)


# ==================== CICLO DIARIO DE INTELIGENCIA ====================

class DailyIntelCycle:
    """
    Ejecuta tareas de inteligencia diaria:
    - Generar reporte de aprendizaje
    - Analizar correlaciones
    - Ajustar configuración
    - Entrenar modelo ONNX si es necesario
    """
    
    def __init__(self, config_hot_reload: ConfigHotReload, bot: ClineTradingBot):
        self.config = config_hot_reload
        self.bot = bot
        self.last_daily_run = None
        self.daily_report_path = "python_brain/daily_intel_output.md"
    
    async def run_daily_intel(self):
        """
        Ejecuta el ciclo diario si no se ha ejecutado hoy.
        """
        today = datetime.now().date()
        
        if self.last_daily_run == today:
            return False  # Ya se ejecutó hoy
        
        logger.info(f"🔄 Iniciando ciclo diario de inteligencia - {today}")
        
        try:
            # 1. Ejecutar generación de inteligencia si existe
            daily_script = Path("python_brain/generate_daily_intel.py")
            if daily_script.exists():
                logger.info("Ejecutando generate_daily_intel.py...")
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(daily_script)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info("✅ Inteligencia diaria generada")
                    if result.stdout:
                        for line in result.stdout.strip().split('\n')[-5:]:
                            logger.info(f"  {line}")
                else:
                    logger.error(f"❌ Error en generación diaria: {result.stderr[:200]}")
            
            # 2. Verificar si hay recomendaciones de ajuste
            recommendations_path = Path("python_brain/daily_intel_recommendations.json")
            if recommendations_path.exists():
                logger.info("Aplicando recomendaciones de inteligencia...")
                try:
                    with open(recommendations_path, 'r') as f:
                        recommendations = json.load(f)
                    
                    # Aplicar cambios a config.json
                    if 'config_changes' in recommendations:
                        current_config = self.config.config.copy()
                        current_config.update(recommendations['config_changes'])
                        with open(self.config.config_path, 'w') as f:
                            json.dump(current_config, f, indent=2)
                        logger.info(f"✅ {len(recommendations['config_changes'])} ajustes aplicados")
                    
                    # Mover recomendaciones a histórico
                    os.rename(recommendations_path, 
                              f"python_brain/recommendations_{today.isoformat()}.json")
                    
                except Exception as e:
                    logger.error(f"Error aplicando recomendaciones: {e}")
            
            # 3. Entrenar modelo ONNX si no existe
            model_path = Path("regime_model.onnx")
            if not model_path.exists():
                logger.info("Modelo ONNX no encontrado, entrenando...")
                train_script = Path("python_brain/train_and_export_onnx.py")
                if train_script.exists():
                    result = subprocess.run(
                        [sys.executable, str(train_script)],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        logger.info("✅ Modelo ONNX entrenado exitosamente")
                    else:
                        logger.error(f"❌ Error entrenando ONNX: {result.stderr[:200]}")
            
            self.last_daily_run = today
            logger.info("✅ Ciclo diario completado")
            return True
            
        except Exception as e:
            logger.error(f"Error en ciclo diario: {e}")
            return False


# ==================== BUCLE PRINCIPAL ====================

async def main_loop():
    """
    Bucle principal del sistema con:
    - Hot-reload de configuración
    - Ciclo diario de inteligencia
    - Ciclo de trading normal
    """
    print("=" * 70)
    print("🚀 CIP-Lite v2.0 - Sistema de Trading Algorítmico Modular")
    print("   Hot-Reload Config | Intel Diaria | ONNX ML")
    print("=" * 70)
    
    # 1. Cargar configuración
    config_reloader = ConfigHotReload("config.json")
    
    # 2. Inicializar bot
    print("\n📦 Inicializando bot de trading...")
    bot = ClineTradingBot()
    print("✅ Bot inicializado")
    
    # 3. Inicializar ciclo diario
    daily_intel = DailyIntelCycle(config_reloader, bot)
    
    # 4. Ciclo principal
    print("\n🔄 Iniciando ciclo principal...")
    cycle_count = 0
    intelligence_interval = config_reloader.get("intelligence_interval_minutes", 60)
    trading_interval = config_reloader.get("trading_interval_seconds", 60)
    
    print(f"   - Ciclo inteligencia: cada {intelligence_interval} min")
    print(f"   - Ciclo trading: cada {trading_interval}s")
    print(f"   - Hot-reload: activo")
    
    try:
        while True:
            cycle_start = time.time()
            cycle_count += 1
            
            # --- FASE 1: HOT-RELOAD ---
            if config_reloader.check_reload():
                # Actualizar intervalos si cambiaron
                intelligence_interval = config_reloader.get("intelligence_interval_minutes", 60)
                trading_interval = config_reloader.get("trading_interval_seconds", 60)
            
            # --- FASE 2: INTELIGENCIA DIARIA ---
            if cycle_count % (60 * intelligence_interval // max(trading_interval, 1)) == 0:
                await daily_intel.run_daily_intel()
            
            # --- FASE 3: CICLO DE TRADING ---
            if cycle_count % max(1, 60 // max(trading_interval, 1)) == 0:
                symbols = config_reloader.get("symbols", ["EURUSD", "XAUUSD"])
                regime_blacklist = config_reloader.get("regime_blacklist", [])
                min_confidence = config_reloader.get("min_confidence", 0.5)
                max_position_size = config_reloader.get("max_position_size", 0.1)
                
                for symbol in symbols:
                    try:
                        result = await bot.process_symbol(symbol)
                        
                        if result.get('decision') in ['BUY', 'SELL']:
                            confidence = result.get('confidence', 0)
                            
                            # Filtrar por confianza mínima
                            if confidence < min_confidence:
                                logger.info(f"{symbol}: señal {result['decision']} con confianza {confidence:.2f} < {min_confidence} - FILTRADA")
                                continue
                            
                            logger.info(f"{symbol}: {result['decision']} (confianza: {confidence:.2f})")
                            
                    except Exception as e:
                        logger.error(f"Error procesando {symbol}: {e}")
                
                if cycle_count % 10 == 0:
                    print(f"   Ciclo #{cycle_count}: {len(symbols)} símbolos procesados")
            
            # Esperar hasta el siguiente ciclo
            elapsed = time.time() - cycle_start
            sleep_time = max(0.1, trading_interval - elapsed)
            await asyncio.sleep(sleep_time)
            
    except asyncio.CancelledError:
        print("\n⚠️  Bucle principal cancelado")
    except KeyboardInterrupt:
        print("\n⚠️  Sistema detenido por usuario")


async def main():
    """Función principal (compatibilidad hacia atrás)"""
    await main_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Sistema detenido por usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)