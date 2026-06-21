"""
Tests para backtesting visualizer y report generator
"""
import pytest
import os
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from services.backtesting.visualizer import BacktestVisualizer, BacktestReport


class TestBacktestVisualizer:
    """Tests para BacktestVisualizer"""
    
    def test_initialization(self):
        """Verifica inicialización correcta"""
        with tempfile.TemporaryDirectory() as temp_dir:
            viz = BacktestVisualizer(output_dir=temp_dir)
            assert viz.output_dir == temp_dir
            assert os.path.exists(temp_dir)
    
    def test_plot_equity_curve(self):
        """Verifica que se genera el gráfico de equity curve"""
        with tempfile.TemporaryDirectory() as temp_dir:
            viz = BacktestVisualizer(output_dir=temp_dir)
            equity_curve = [100000, 101000, 102500, 101800, 103000]
            viz.plot_equity_curve(equity_curve)
            assert os.path.exists(os.path.join(temp_dir, "equity_curve.png"))
    
    def test_plot_equity_curve_with_benchmark(self):
        """Verifica que se genera el gráfico con benchmark"""
        with tempfile.TemporaryDirectory() as temp_dir:
            viz = BacktestVisualizer(output_dir=temp_dir)
            equity_curve = [100000, 101000, 102500, 101800, 103000]
            benchmark = [100000, 100500, 101000, 100800, 101500]
            viz.plot_equity_curve(equity_curve, benchmark_curve=benchmark)
            assert os.path.exists(os.path.join(temp_dir, "equity_curve.png"))
    
    def test_plot_drawdown(self):
        """Verifica que se genera el gráfico de drawdown"""
        with tempfile.TemporaryDirectory() as temp_dir:
            viz = BacktestVisualizer(output_dir=temp_dir)
            equity_curve = [100000, 101000, 102500, 101800, 103000]
            viz.plot_drawdown(equity_curve)
            assert os.path.exists(os.path.join(temp_dir, "drawdown.png"))
    
    def test_plot_monthly_returns(self):
        """Verifica que se genera el gráfico de rendimientos mensuales"""
        with tempfile.TemporaryDirectory() as temp_dir:
            viz = BacktestVisualizer(output_dir=temp_dir)
            # Crear Series con fechas mensuales
            dates = pd.date_range(start="2024-01-01", periods=6, freq="ME")
            returns = pd.Series([0.02, -0.01, 0.03, 0.015, -0.005, 0.025], index=dates)
            viz.plot_monthly_returns(returns)
            assert os.path.exists(os.path.join(temp_dir, "monthly_returns.png"))


class TestBacktestReport:
    """Tests para BacktestReport"""
    
    def test_generate_text_report(self):
        """Verifica que se genera el informe de texto"""
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = os.path.join(temp_dir, "test_report.txt")
            results = {
                "total_trades": 100,
                "winning_trades": 60,
                "losing_trades": 40,
                "win_rate": 0.6,
                "total_return": 0.15,
                "annualized_return": 0.18,
                "sharpe_ratio": 1.5,
                "sortino_ratio": 2.0,
                "max_drawdown": -0.1,
                "profit_loss_ratio": 2.5,
                "avg_win": 500,
                "avg_loss": 200
            }
            BacktestReport.generate_text_report(results, filename=report_path)
            assert os.path.exists(report_path)
            # Verificar que el contenido del informe tiene información relevante
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "INFORME DE BACKTESTING" in content
                assert "Total de operaciones: 100" in content
                assert "Tasa de aciertos (Win Rate): 60.00%" in content
    
    def test_generate_conclusions_good(self):
        """Verifica las conclusiones para un rendimiento bueno"""
        results = {
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.1,
            "win_rate": 0.6
        }
        conclusions = BacktestReport._generate_conclusions(results)
        assert "✅ El ratio de Sharpe es saludable" in conclusions
        assert "✅ El máximo drawdown es controlado" in conclusions
        assert "✅ La tasa de aciertos es mayor al 50%" in conclusions
    
    def test_generate_conclusions_medium(self):
        """Verifica las conclusiones para un rendimiento medio"""
        results = {
            "sharpe_ratio": 0.75,
            "max_drawdown": -0.15,
            "win_rate": 0.45
        }
        conclusions = BacktestReport._generate_conclusions(results)
        assert "⚠️ El ratio de Sharpe es aceptable" in conclusions
        assert "✅ El máximo drawdown es controlado" in conclusions
        assert "⚠️ La tasa de aciertos es baja" in conclusions
    
    def test_generate_conclusions_poor(self):
        """Verifica las conclusiones para un rendimiento pobre"""
        results = {
            "sharpe_ratio": 0.2,
            "max_drawdown": -0.25,
            "win_rate": 0.4
        }
        conclusions = BacktestReport._generate_conclusions(results)
        assert "❌ El ratio de Sharpe es bajo" in conclusions
        assert "⚠️ El máximo drawdown es elevado" in conclusions
        assert "⚠️ La tasa de aciertos es baja" in conclusions
