"""
Módulo de Memoria de Señales - v2.0
Aprende de operaciones ganadoras y perdedoras
Genera patrones y ajustes para el sistema
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import structlog

logger = structlog.get_logger()


@dataclass
class TradeRecord:
    """Registro de una operación"""
    trade_id: int
    timestamp: datetime
    symbol: str
    decision: str  # BUY, SELL
    confidence: float
    regime: str
    sentiment: float
    indicators: Dict[str, float]
    pnl_usd: Optional[float]
    exit_price: Optional[float]
    exit_reason: str
    result: str  # WIN, LOSS, PENDING


@dataclass
class PatternsReport:
    """Reporte de patrones detectados"""
    period_start: datetime
    period_end: datetime
    total_trades: int
    win_rate: float
    profit_factor: float
    
    winning_patterns: List[str]
    losing_patterns: List[str]
    management_insights: List[str]
    
    suggested_actions: List[str]


class SignalMemoryModule:
    """
    Memoria inteligente del sistema de trading
    Aprende de operaciones pasadas para mejorar decisiones futuras
    """
    
    def __init__(self, db_path: str = "../data/trading_journal.db", config_path: str = "../config.json"):
        self.db_path = db_path
        self.config_path = config_path
        self.insights_cache: Dict[str, any] = {}
        
        # Inicializar base de datos
        self._init_database()
        
        logger.info(f"Signal Memory Module v2.0 inicializado | DB: {db_path}")
    
    def get_correlation_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Analiza correlación entre indicadores y resultados.
        Retorna coeficientes de correlación de Pearson.
        """
        if df.empty or 'indicators' not in df.columns:
            return {}
        
        correlations = {}
        indicators_data = {}
        
        for _, row in df.iterrows():
            inds = row['indicators']
            if isinstance(inds, str):
                try:
                    inds = eval(inds)
                except:
                    continue
            if not isinstance(inds, dict):
                continue
            
            for key, val in inds.items():
                if isinstance(val, (int, float)):
                    if key not in indicators_data:
                        indicators_data[key] = []
                    indicators_data[key].append(val)
        
        results = df['result'].values
        for key, vals in indicators_data.items():
            if len(vals) == len(results):
                vals_arr = np.array(vals, dtype=float)
                results_binary = np.array([1 if r == 'WIN' else 0 for r in results], dtype=float)
                if np.std(vals_arr) > 0 and np.std(results_binary) > 0:
                    corr = np.corrcoef(vals_arr, results_binary)[0, 1]
                    correlations[key] = float(corr)
        
        return correlations
    
    def get_regime_confusion_matrix(self, df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
        """
        Matriz de confusión por régimen de mercado.
        Muestra qué regímenes producen mejores resultados.
        """
        matrix = {}
        if df.empty or 'regime' not in df.columns:
            return matrix
        
        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime]
            wins = len(regime_df[regime_df['result'] == 'WIN'])
            losses = len(regime_df[regime_df['result'] == 'LOSS'])
            total = len(regime_df)
            matrix[regime] = {
                'total': total,
                'wins': wins,
                'losses': losses,
                'win_rate': wins / total if total > 0 else 0
            }
        
        return matrix
    
    def generate_config_adjustments(self, period_days: int = 7) -> Dict:
        """
        Genera recomendaciones de ajuste para config.json
        basadas en el análisis estadístico de los trades.
        """
        conn = sqlite3.connect(self.db_path)
        since = datetime.now() - timedelta(days=period_days)
        query = "SELECT * FROM trades WHERE timestamp >= ? AND result != 'PENDING'"
        df = pd.read_sql_query(query, conn, params=(since.isoformat(),))
        conn.close()
        
        adjustments = {
            'win_rate': 0,
            'total_trades': len(df),
            'recommendations': [],
            'config_changes': {}
        }
        
        if df.empty:
            return adjustments
        
        wins = len(df[df['result'] == 'WIN'])
        adjustments['win_rate'] = wins / len(df) if len(df) > 0 else 0
        
        # Correlaciones
        correlations = self.get_correlation_analysis(df)
        adjustments['correlations'] = correlations
        
        # Matriz de regímenes
        regime_matrix = self.get_regime_confusion_matrix(df)
        adjustments['regime_matrix'] = regime_matrix
        
        # Recomendaciones basadas en correlaciones
        for indicator, corr in correlations.items():
            if abs(corr) > 0.3:
                if corr > 0:
                    adjustments['recommendations'].append(
                        f"Indicador {indicator} correlacionado positivamente ({corr:.2f}) - mantener/pesar más"
                    )
                else:
                    adjustments['recommendations'].append(
                        f"Indicador {indicator} correlacionado negativamente ({corr:.2f}) - considerar ajustar umbral"
                    )
        
        # Recomendaciones basadas en win rate
        if adjustments['win_rate'] < 0.4:
            adjustments['config_changes']['min_confidence'] = 0.65
            adjustments['recommendations'].append("Win rate bajo (<40%): aumentar confianza mínima a 0.65")
        elif adjustments['win_rate'] > 0.65:
            adjustments['config_changes']['max_position_size'] = 0.15
            adjustments['recommendations'].append("Win rate alto (>65%): aumentar tamaño de posición máx a 15%")
        
        # Recomendaciones basadas en regímenes
        for regime, stats in regime_matrix.items():
            if stats['win_rate'] < 0.3 and stats['total'] >= 3:
                adjustments['config_changes']['regime_blacklist'] = adjustments.get('config_changes', {}).get('regime_blacklist', []) + [regime]
                adjustments['recommendations'].append(f"Régimen {regime} con win rate bajo ({stats['win_rate']:.0%}): evitar o filtrar")
        
        return adjustments
    
    def apply_config_adjustments(self, adjustments: Dict) -> bool:
        """
        Aplica ajustes recomendados al archivo config.json
        """
        try:
            import json
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            changed = False
            for key, value in adjustments.get('config_changes', {}).items():
                if key in config:
                    config[key] = value
                    changed = True
                    logger.info(f"Config ajustado: {key} → {value}")
            
            if changed:
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                logger.info("✅ config.json actualizado con ajustes")
            
            return changed
            
        except Exception as e:
            logger.error(f"Error aplicando ajustes: {e}")
            return False
    
    def get_adaptive_insights(self, symbol: str, period_days: int = 7) -> Dict:
        """
        Obtiene insights adaptativos que integran:
        - Análisis estadístico
        - Correlaciones
        - Ajustes de configuración
        - Recomendaciones para Trae
        """
        insights = self.get_insights(symbol, period_days)
        
        if insights.get('status') != 'success':
            return insights
        
        # Obtener datos completos
        conn = sqlite3.connect(self.db_path)
        since = datetime.now() - timedelta(days=period_days)
        query = "SELECT * FROM trades WHERE symbol = ? AND timestamp >= ?"
        df = pd.read_sql_query(query, conn, params=(symbol, since.isoformat()))
        conn.close()
        
        if df.empty:
            return insights
        
        # Añadir análisis avanzado
        insights['correlations'] = self.get_correlation_analysis(df)
        insights['regime_matrix'] = self.get_regime_confusion_matrix(df)
        
        # Recomendaciones de ajuste
        adjustments = self.generate_config_adjustments(period_days)
        insights['config_adjustments'] = adjustments
        
        # Análisis de secuencias (rachas)
        if len(df) >= 5:
            recent_results = df.head(10)['result'].tolist()
            wins_streak = 0
            for r in recent_results:
                if r == 'WIN':
                    wins_streak += 1
                else:
                    break
            losses_streak = 0
            for r in recent_results:
                if r == 'LOSS':
                    losses_streak += 1
                else:
                    break
            insights['win_streak'] = wins_streak
            insights['loss_streak'] = losses_streak
            if losses_streak >= 3:
                insights['recommendations'] = insights.get('recommendations', []) + [
                    "Racha de 3+ pérdidas - considerar pausa temporal del símbolo"
                ]
        
        return insights
    
    def _init_database(self):
        """Inicializa SQLite para almacenar trades"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                decision TEXT NOT NULL,
                confidence REAL,
                regime TEXT,
                sentiment REAL,
                indicators TEXT,
                pnl_usd REAL,
                exit_price REAL,
                exit_reason TEXT,
                result TEXT DEFAULT 'PENDING'
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_symbol 
            ON trades(symbol)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp 
            ON trades(timestamp)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Base de datos inicializada")
    
    def record_trade(self, trade_data: Dict):
        """
        Registra una nueva operación
        trade_data: {
            'timestamp': datetime,
            'symbol': str,
            'decision': str,
            'confidence': float,
            'regime': str,
            'sentiment': float,
            'indicators': dict,
            'result': str (PENDING, WIN, LOSS)
        }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades 
                (timestamp, symbol, decision, confidence, regime, sentiment, 
                 indicators, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('timestamp', datetime.now()).isoformat(),
                trade_data.get('symbol', 'UNKNOWN'),
                trade_data.get('decision', 'HOLD'),
                trade_data.get('confidence', 0.0),
                trade_data.get('regime', 'UNKNOWN'),
                trade_data.get('sentiment', 0.0),
                str(trade_data.get('indicators', {})),
                trade_data.get('result', 'PENDING')
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Trade registrado: {trade_data.get('symbol')} | {trade_data.get('decision')}")
            
        except Exception as e:
            logger.error(f"Error registrando trade: {e}")
    
    def update_trade_result(self, trade_id: int, pnl_usd: float, 
                           exit_price: float, exit_reason: str):
        """Actualiza el resultado de una operación"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            result = 'WIN' if pnl_usd > 0 else 'LOSS'
            
            cursor.execute('''
                UPDATE trades 
                SET pnl_usd = ?, exit_price = ?, exit_reason = ?, result = ?
                WHERE id = ?
            ''', (pnl_usd, exit_price, exit_reason, result, trade_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Trade {trade_id} actualizado: {result} | PnL: ${pnl_usd:+.2f}")
            
        except Exception as e:
            logger.error(f"Error actualizando trade: {e}")
    
    def get_insights(self, symbol: str, period_days: int = 7) -> Dict:
        """
        Obtiene insights de aprendizaje para un símbolo
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Obtener trades recientes
            since = datetime.now() - timedelta(days=period_days)
            query = '''
                SELECT * FROM trades 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            '''
            
            df = pd.read_sql_query(query, conn, params=(symbol, since.isoformat()))
            conn.close()
            
            if df.empty:
                return {'status': 'no_data', 'message': 'Sin trades recientes'}
            
            insights = {
                'status': 'success',
                'period_days': period_days,
                'total_trades': len(df),
                'win_rate': len(df[df['result'] == 'WIN']) / len(df),
                'avg_confidence': df['confidence'].mean(),
                'avg_pnl': df['pnl_usd'].mean() if 'pnl_usd' in df else 0,
                'best_regime': self._find_best_regime(df),
                'best_hours': self._find_best_hours(df),
                'worst_conditions': self._find_worst_conditions(df),
                'patterns': self._detect_patterns(df)
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error obteniendo insights: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def analyze_performance(self, period_days: int = 7) -> PatternsReport:
        """
        Analiza performance completa del período
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            since = datetime.now() - timedelta(days=period_days)
            query = '''
                SELECT * FROM trades 
                WHERE timestamp >= ? AND result != 'PENDING'
                ORDER BY timestamp
            '''
            
            df = pd.read_sql_query(query, conn, params=(since.isoformat(),))
            conn.close()
            
            if df.empty:
                return PatternsReport(
                    period_start=since,
                    period_end=datetime.now(),
                    total_trades=0,
                    win_rate=0,
                    profit_factor=0,
                    winning_patterns=[],
                    losing_patterns=[],
                    management_insights=[],
                    suggested_actions=[]
                )
            
            # Análisis
            total_trades = len(df)
            wins = df[df['result'] == 'WIN']
            losses = df[df['result'] == 'LOSS']
            win_rate = len(wins) / total_trades if total_trades > 0 else 0
            
            profit_factor = abs(wins['pnl_usd'].sum() / losses['pnl_usd'].sum()) if len(losses) > 0 and losses['pnl_usd'].sum() != 0 else 0
            
            # Detectar patrones
            winning_patterns = self._extract_patterns(wins, "WINNING")
            losing_patterns = self._extract_patterns(losses, "LOSING")
            
            # Insights de gestión
            management_insights = self._analyze_management(df)
            
            # Acciones sugeridas
            suggested_actions = self._suggest_actions(
                winning_patterns, losing_patterns, management_insights, win_rate
            )
            
            return PatternsReport(
                period_start=since,
                period_end=datetime.now(),
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                winning_patterns=winning_patterns,
                losing_patterns=losing_patterns,
                management_insights=management_insights,
                suggested_actions=suggested_actions
            )
            
        except Exception as e:
            logger.error(f"Error analizando performance: {e}")
            return PatternsReport(
                period_start=datetime.now() - timedelta(days=period_days),
                period_end=datetime.now(),
                total_trades=0,
                win_rate=0,
                profit_factor=0,
                winning_patterns=[],
                losing_patterns=[],
                management_insights=[],
                suggested_actions=["Error en análisis"]
            )
    
    def generate_learning_report(self, period_days: int = 7) -> str:
        """
        Genera reporte de aprendizaje en formato Markdown
        Para ser usado por Trae en el ciclo diario
        """
        report = self.analyze_performance(period_days)
        
        lines = [
            f"# REPORTE DE INTELIGENCIA - {report.period_end.strftime('%d %b %Y')}",
            "",
            "## 📊 MÉTRICAS GENERALES",
            f"- **Operaciones:** {report.total_trades}",
            f"- **Win Rate:** {report.win_rate:.1%}",
            f"- **Profit Factor:** {report.profit_factor:.2f}",
            "",
        ]
        
        if report.winning_patterns:
            lines.extend([
                "## 🟢 PATRONES GANADORES",
                *[f"- {p}" for p in report.winning_patterns],
                ""
            ])
        
        if report.losing_patterns:
            lines.extend([
                "## 🔴 PATRONES PERDEDORES",
                *[f"- {p}" for p in report.losing_patterns],
                ""
            ])
        
        if report.management_insights:
            lines.extend([
                "## 🟡 GESTIÓN",
                *[f"- {p}" for p in report.management_insights],
                ""
            ])
        
        if report.suggested_actions:
            lines.extend([
                "## 🎯 ACCIONES SUGERIDAS",
                *[f"{i+1}. {a}" for i, a in enumerate(report.suggested_actions)],
                ""
            ])
        
        return "\n".join(lines)
    
    def _find_best_regime(self, df: pd.DataFrame) -> str:
        """Encuentra el régimen más rentable"""
        if df.empty or 'regime' not in df.columns:
            return "UNKNOWN"
        
        regime_performance = df.groupby('regime').agg({
            'pnl_usd': 'mean',
            'result': lambda x: (x == 'WIN').mean()
        }).sort_values('pnl_usd', ascending=False)
        
        if not regime_performance.empty:
            return regime_performance.index[0]
        return "UNKNOWN"
    
    def _find_best_hours(self, df: pd.DataFrame) -> List[str]:
        """Encuentra las horas más rentables"""
        if 'timestamp' not in df.columns or df.empty:
            return []
        
        try:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            hour_perf = df.groupby('hour').agg({
                'pnl_usd': 'mean',
                'result': lambda x: (x == 'WIN').mean()
            }).sort_values('pnl_usd', ascending=False)
            
            best_hours = hour_perf.head(3).index.tolist()
            return [f"{h:02d}:00 UTC" for h in best_hours]
        except:
            return []
    
    def _find_worst_conditions(self, df: pd.DataFrame) -> List[str]:
        """Identifica condiciones que generan pérdidas"""
        conditions = []
        
        losses = df[df['result'] == 'LOSS']
        if losses.empty:
            return []
        
        # Spread alto
        if 'indicators' in losses.columns:
            avg_spread = losses['indicators'].apply(lambda x: x.get('spread', 0) if isinstance(x, dict) else 0).mean()
            if avg_spread > 1.5:
                conditions.append(f"Spread alto promedio en pérdidas: {avg_spread:.2f}")
        
        # Horas perdedoras
        if 'timestamp' in losses.columns:
            try:
                losses['hour'] = pd.to_datetime(losses['timestamp']).dt.hour
                worst_hours = losses['hour'].value_counts().head(2).index.tolist()
                for h in worst_hours:
                    conditions.append(f"Hora perdedora: {h:02d}:00 UTC")
            except:
                pass
        
        # Confianza baja
        if 'confidence' in losses.columns and losses['confidence'].mean() < 0.5:
            conditions.append("Confianza promedio baja en pérdidas")
        
        return conditions
    
    def _detect_patterns(self, df: pd.DataFrame) -> Dict[str, List]:
        """Detecta patrones en los datos"""
        patterns = {
            'trending_up': [],
            'trending_down': [],
            'high_volatility': [],
            'low_confidence': []
        }
        
        for _, row in df.iterrows():
            regime = row.get('regime', '')
            confidence = row.get('confidence', 0)
            
            if regime == 'trending_up':
                patterns['trending_up'].append(row['symbol'])
            elif regime == 'trending_down':
                patterns['trending_down'].append(row['symbol'])
            
            # Detectar alta volatilidad desde indicators
            indicators = row.get('indicators', {})
            if isinstance(indicators, dict):
                atr = indicators.get('atr', 0)
                if atr > 0.05:  # 5% ATR
                    patterns['high_volatility'].append(row['symbol'])
            
            if confidence < 0.5:
                patterns['low_confidence'].append(row['symbol'])
        
        return patterns
    
    def _extract_patterns(self, df: pd.DataFrame, pattern_type: str) -> List[str]:
        """Extrae patrones descriptivos"""
        patterns = []
        
        if df.empty:
            return patterns
        
        # Patrón: Confianza alta → Ganancia
        avg_conf = df['confidence'].mean()
        if avg_conf > 0.7 and pattern_type == "WINNING":
            patterns.append(f"Alta confianza ({avg_conf:.2f}) asociada a ganancias")
        
        # Patrón: Régimen ganador
        if 'regime' in df.columns:
            best_regime = df['regime'].value_counts().index[0]
            patterns.append(f"Régimen predominante: {best_regime}")
        
        # Patrón: Horario
        if 'timestamp' in df.columns:
            try:
                df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
                best_hour = df['hour'].value_counts().index[0]
                patterns.append(f"Hora óptima: {best_hour:02d}:00 UTC")
            except:
                pass
        
        # Patrón: Indicadores ganadores
        if 'indicators' in df.columns:
            rsi_vals = df['indicators'].apply(
                lambda x: x.get('rsi', 50) if isinstance(x, dict) else 50
            )
            if rsi_vals.mean() < 40 or rsi_vals.mean() > 60:
                patterns.append(f"RSI promedio en zonas extremas: {rsi_vals.mean():.1f}")
        
        return patterns
    
    def _analyze_management(self, df: pd.DataFrame) -> List[str]:
        """Analiza aspectos de gestión"""
        insights = []
        
        if 'exit_reason' in df.columns and not df.empty:
            exit_reasons = df['exit_reason'].value_counts()
            
            # TP hit rate
            tp_hits = exit_reasons.get('TP', 0)
            if tp_hits > 0:
                insights.append(f"TP alcanzado en {tp_hits}/{len(df)} operaciones")
        
        # Duración promedio (si hay timestamp de entrada/salida)
        if 'pnl_usd' in df.columns:
            avg_pnl = df['pnl_usd'].mean()
            if avg_pnl > 0:
                insights.append(f"Ganancia promedio: ${avg_pnl:.2f}")
            else:
                insights.append(f"Pérdida promedio: ${abs(avg_pnl):.2f}")
        
        return insights
    
    def _suggest_actions(self, winning_patterns: List[str], 
                        losing_patterns: List[str],
                        management_insights: List[str],
                        win_rate: float) -> List[str]:
        """Genera acciones sugeridas basadas en el análisis"""
        actions = []
        
        # Basado en win rate
        if win_rate < 0.4:
            actions.append("Aumentar filtros de entrada - reducir operaciones")
        elif win_rate > 0.6:
            actions.append("Considerar aumentar tamaño de posición")
        
        # Basado en patrones perdedores
        for pattern in losing_patterns:
            if "hora" in pattern.lower():
                actions.append("Añadir hora a blacklist")
            elif "spread" in pattern.lower():
                actions.append("Reducir max_spread_pips")
            elif "confianza" in pattern.lower():
                actions.append("Elevar umbral mínimo de confianza")
        
        # Basado en management
        for insight in management_insights:
            if "TP" in insight:
                actions.append("Optimizar niveles de Take Profit")
        
        if not actions:
            actions.append("Mantener configuración actual - sistema óptimo")
        
        return actions
    
    def get_trade_history(self, symbol: Optional[str] = None, 
                         limit: int = 100) -> List[TradeRecord]:
        """Obtiene historial de trades"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = '''
                SELECT * FROM trades 
                {}
                ORDER BY timestamp DESC 
                LIMIT ?
            '''.format("WHERE symbol = ?" if symbol else "")
            
            params = (symbol, limit) if symbol else (limit,)
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            trades = []
            for _, row in df.iterrows():
                trade = TradeRecord(
                    trade_id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    symbol=row['symbol'],
                    decision=row['decision'],
                    confidence=row['confidence'],
                    regime=row.get('regime', 'UNKNOWN'),
                    sentiment=row.get('sentiment', 0),
                    indicators=eval(row.get('indicators', '{}')) if isinstance(row.get('indicators'), str) else row.get('indicators', {}),
                    pnl_usd=row.get('pnl_usd'),
                    exit_price=row.get('exit_price'),
                    exit_reason=row.get('exit_reason', ''),
                    result=row.get('result', 'PENDING')
                )
                trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")
            return []


# Función de conveniencia
def create_signal_memory(db_path: str = "../data/trading_journal.db") -> SignalMemoryModule:
    """Factory para crear módulo de memoria"""
    return SignalMemoryModule(db_path)


if __name__ == "__main__":
    print("Testing Signal Memory Module v2.0...")
    print("=" * 60)
    
    memory = create_signal_memory("/tmp/test_trading.db")
    
    # Test registro
    test_trade = {
        'timestamp': datetime.now(),
        'symbol': 'EURUSD',
        'decision': 'BUY',
        'confidence': 0.8,
        'regime': 'MOMENTUM',
        'sentiment': 0.3,
        'indicators': {'rsi': 35, 'macd': 0.5},
        'result': 'WIN'
    }
    
    memory.record_trade(test_trade)
    print("\n✅ Trade registrado")
    
    # Test análisis
    insights = memory.get_insights('EURUSD', 7)
    print(f"\n📊 Insights:")
    print(f"   Status: {insights.get('status')}")
    print(f"   Win Rate: {insights.get('win_rate', 0):.1%}")
    
    # Test reporte
    report = memory.generate_learning_report(7)
    print(f"\n📝 Reporte generado: {len(report)} caracteres")
    
    print("\n✅ Signal Memory Module funcionando correctamente")