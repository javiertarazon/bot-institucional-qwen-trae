#!/usr/bin/env python3
"""
Aura-X System Monitor
Monitorea el estado del sistema y verifica que todos los componentes funcionan
"""

import sys
import os
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent


class SystemChecker:
    """Verifica el estado de todos los componentes del sistema"""

    def __init__(self):
        self.results = {'passed': [], 'warnings': [], 'errors': []}
        self.checks_run = 0

    def check(self, name, condition, error_msg="", warning_msg=""):
        """Ejecuta un check y registra resultado"""
        self.checks_run += 1
        if condition:
            self.results['passed'].append(name)
            logger.info(f"✅ {name}")
            return True
        elif warning_msg:
            self.results['warnings'].append(f"{name}: {warning_msg}")
            logger.warning(f"⚠️  {name}: {warning_msg}")
            return False
        else:
            self.results['errors'].append(f"{name}: {error_msg}")
            logger.error(f"❌ {name}: {error_msg}")
            return False

    def check_python_version(self):
        """Verifica versión de Python"""
        v = sys.version_info
        ok = v.major == 3 and v.minor >= 8
        self.check(
            "Python >= 3.8",
            ok,
            f"Python {v.major}.{v.minor} detectado (se requiere 3.8+)"
        )

    def check_required_files(self):
        """Verifica archivos requeridos"""
        required = [
            'config.json',
            'services/__init__.py',
            'services/strategies/__init__.py',
            'services/strategies/xauusd_scalper.py',
            'generate_daily_intel.py',
            '.trae/rules.md',
        ]
        for f in required:
            path = PROJECT_ROOT / f
            self.check(
                f"Archivo: {f}",
                path.exists(),
                f"No encontrado: {path}"
            )

    def check_config_json(self):
        """Valida config.json"""
        config_path = PROJECT_ROOT / "config.json"
        if not config_path.exists():
            self.check("config.json válido", False, "Archivo no existe")
            return

        try:
            with open(config_path) as f:
                cfg = json.load(f)

            # Validar campos críticos
            self.check(
                "config.json: risk_per_trade_percent = 0.20",
                cfg.get('global_settings', {}).get('risk_per_trade_percent') == 0.20,
                "Valor incorrecto de risk_per_trade_percent"
            )

            self.check(
                "config.json: max_open_trades = 3",
                cfg.get('global_settings', {}).get('max_open_trades') == 3,
                "Valor incorrecto de max_open_trades"
            )

            # Validar que XAUUSD está habilitado
            xauusd = next((a for a in cfg.get('assets', []) if a['symbol'] == 'XAUUSD'), None)
            self.check(
                "XAUUSD configurado",
                xauusd is not None,
                "XAUUSD no encontrado en assets"
            )

            if xauusd:
                self.check(
                    "XAUUSD habilitado",
                    xauusd.get('enabled', False),
                    "XAUUSD deshabilitado"
                )

        except json.JSONDecodeError as e:
            self.check("config.json: JSON válido", False, str(e))

    def check_database(self):
        """Verifica la base de datos"""
        db_path = PROJECT_ROOT / "data" / "trades.db"
        if not db_path.exists():
            self.check("Base de datos existe", False, "No se encontró trades.db")
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM trades")
            total = cursor.fetchone()[0]
            conn.close()

            self.check(
                f"Base de datos operativa ({total} trades)",
                total > 0,
                "Base de datos vacía"
            )
        except Exception as e:
            self.check("Base de datos operativa", False, str(e))

    def check_strategy_import(self):
        """Verifica que la estrategia se puede importar"""
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from services.strategies import XAUUSDScalper, XAUUSDConfig
            scalper = XAUUSDScalper()
            self.check("Estrategia XAUUSD importable", True)
        except Exception as e:
            self.check("Estrategia XAUUSD importable", False, str(e))

    def check_daily_intel_output(self):
        """Verifica que existe el reporte diario"""
        intel_path = PROJECT_ROOT / "DAILY_INTEL.md"
        if not intel_path.exists():
            self.check("DAILY_INTEL.md existe", False, "Reporte no generado aún")
            return

        # Verificar que es reciente (menos de 24h)
        mtime = datetime.fromtimestamp(intel_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600

        self.check(
            f"DAILY_INTEL.md reciente ({age_hours:.1f}h)",
            age_hours < 24,
            "Reporte tiene más de 24h, regenerar"
        )

    def check_disk_space(self):
        """Verifica espacio en disco"""
        stat = os.statvfs(PROJECT_ROOT)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        self.check(
            f"Espacio en disco ({free_gb:.1f}GB libre)",
            free_gb > 1.0,
            "Espacio en disco bajo (< 1GB)"
        )

    def check_logs_directory(self):
        """Verifica directorio de logs"""
        logs_dir = PROJECT_ROOT / "logs"
        if not logs_dir.exists():
            logs_dir.mkdir(exist_ok=True)
        self.check("Directorio logs/ existe", True)

    def run_all_checks(self):
        """Ejecuta todos los checks"""
        logger.info("🔍 Iniciando verificación del sistema Aura-X...\n")

        self.check_python_version()
        self.check_required_files()
        self.check_config_json()
        self.check_database()
        self.check_strategy_import()
        self.check_daily_intel_output()
        self.check_disk_space()
        self.check_logs_directory()

    def print_summary(self):
        """Imprime resumen de resultados"""
        print("\n" + "="*70)
        print("📊 RESUMEN DE VERIFICACIÓN DEL SISTEMA AURA-X")
        print("="*70)

        print(f"\n✅ PASADOS: {len(self.results['passed'])}/{self.checks_run}")
        print(f"⚠️  ADVERTENCIAS: {len(self.results['warnings'])}")
        print(f"❌ ERRORES: {len(self.results['errors'])}")

        if self.results['errors']:
            print("\n❌ ERRORES CRÍTICOS:")
            for err in self.results['errors']:
                print(f"   • {err}")

        if self.results['warnings']:
            print("\n⚠️  ADVERTENCIAS:")
            for warn in self.results['warnings']:
                print(f"   • {warn}")

        if not self.results['errors']:
            print("\n🎉 SISTEMA OPERATIVO Y LISTO PARA OPERAR")
            return 0
        else:
            print("\n⚠️  SISTEMA CON ERRORES - REVISAR ANTES DE OPERAR")
            return 1


def main():
    checker = SystemChecker()
    checker.run_all_checks()
    exit_code = checker.print_summary()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
