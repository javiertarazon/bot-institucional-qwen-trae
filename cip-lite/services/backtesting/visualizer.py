"""
Generador de informes y visualizaciones de backtesting
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Para generar gráficos sin GUI
import matplotlib.pyplot as plt
from typing import Dict, Any
import structlog
import os
from datetime import datetime, timedelta

logger = structlog.get_logger()
# Usar estilo de matplotlib si seaborn no está disponible
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn' in plt.style.available else 'default')


class BacktestVisualizer:
    """Clase para generar gráficos de backtesting"""
    def __init__(self, output_dir: str = "backtest_reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def plot_equity_curve(self, equity_curve: list, benchmark_curve: list = None, title: str = "Curva de Capital"):
        """Grafica la curva de equity vs benchmark"""
        plt.figure(figsize=(14, 7))
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(len(equity_curve))]
        
        plt.plot(dates, equity_curve, label='Estrategia', linewidth=2, color='#2E86AB')
        if benchmark_curve:
            plt.plot(dates, benchmark_curve, label='Benchmark (Buy & Hold)', linewidth=2, color='#A23B72', linestyle='--')
        
        plt.title(title, fontsize=16, fontweight='bold')
        plt.xlabel("Fecha", fontsize=12)
        plt.ylabel("Capital ($)", fontsize=12)
        plt.legend(fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        path = os.path.join(self.output_dir, "equity_curve.png")
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Gráfico de curva de capital guardado en {path}")

    def plot_drawdown(self, equity_curve: list):
        """Grafica el drawdown"""
        equity_series = pd.Series(equity_curve)
        cumulative = (1 + equity_series.pct_change().dropna()).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        
        plt.figure(figsize=(14, 5))
        plt.fill_between(range(len(drawdown)), drawdown, 0, color='#F18F01', alpha=0.5)
        plt.plot(drawdown, color='#F18F01', linewidth=1.5)
        plt.title("Drawdown Histórico", fontsize=16, fontweight='bold')
        plt.xlabel("Días de Trading", fontsize=12)
        plt.ylabel("Drawdown (%)", fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        path = os.path.join(self.output_dir, "drawdown.png")
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Gráfico de drawdown guardado en {path}")

    def plot_monthly_returns(self, returns: pd.Series):
        """Grafica rendimientos mensuales"""
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        colors = ['#2E86AB' if x >=0 else '#A23B72' for x in monthly_returns]
        
        plt.figure(figsize=(14, 7))
        monthly_returns.plot(kind='bar', color=colors, alpha=0.8)
        plt.title("Rendimientos Mensuales", fontsize=16, fontweight='bold')
        plt.xlabel("Mes", fontsize=12)
        plt.ylabel("Rendimiento (%)", fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(True, axis='y', alpha=0.3)
        plt.tight_layout()
        
        path = os.path.join(self.output_dir, "monthly_returns.png")
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Gráfico de rendimientos mensuales guardado en {path}")


class BacktestReport:
    """Clase para generar informes de backtesting"""
    @staticmethod
    def generate_text_report(results: Dict[str, Any], filename: str = "backtest_reports/backtest_report.txt"):
        """Genera un informe de texto detallado"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        report = f"""
{'='*80}
INFORME DE BACKTESTING - CIP (Crypto Intelligence Platform)
{'='*80}

FECHA DEL INFORME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
METRÍCAS DE RENDIMIENTO
---
- Total de operaciones: {results['total_trades']}
- Operaciones ganadoras: {results['winning_trades']}
- Operaciones perdedoras: {results['losing_trades']}
- Tasa de aciertos (Win Rate): {results['win_rate']:.2%}
- Rendimiento total: {results['total_return']:.2%}
- Rendimiento anualizado: {results['annualized_return']:.2%}
- Ratio de Sharpe: {results['sharpe_ratio']:.2f}
- Ratio de Sortino: {results['sortino_ratio']:.2f}
- Máximo Drawdown: {results['max_drawdown']:.2%}
- Ratio Ganancia/Pérdida Promedio: {results['profit_loss_ratio']:.2f}
- Ganancia promedio por operación ganadora: ${results['avg_win']:.2f}
- Pérdida promedio por operación perdedora: ${results['avg_loss']:.2f}

---
CONCLUSIONES
---
{BacktestReport._generate_conclusions(results)}

{'='*80}
FIN DEL INFORME
{'='*80}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Informe de texto guardado en {filename}")

    @staticmethod
    def _generate_conclusions(results: Dict[str, Any]) -> str:
        """Genera conclusiones automáticas"""
        conclusions = []
        if results['sharpe_ratio'] > 1.0:
            conclusions.append("- ✅ El ratio de Sharpe es saludable (mayor que 1.0)")
        elif 0.5 <= results['sharpe_ratio'] <= 1.0:
            conclusions.append("- ⚠️ El ratio de Sharpe es aceptable, pero podría mejorar")
        else:
            conclusions.append("- ❌ El ratio de Sharpe es bajo, la estrategia tiene riesgo alto por unidad de retorno")
        
        if results['max_drawdown'] > -0.2:
            conclusions.append("- ✅ El máximo drawdown es controlado (menor al 20%)")
        else:
            conclusions.append("- ⚠️ El máximo drawdown es elevado, es importante revisar la gestión de riesgo")
        
        if results['win_rate'] > 0.5:
            conclusions.append("- ✅ La tasa de aciertos es mayor al 50%")
        else:
            conclusions.append("- ⚠️ La tasa de aciertos es baja, pero el ratio ganancia/pérdida podría compensarlo")
        
        return "\n".join(conclusions)
