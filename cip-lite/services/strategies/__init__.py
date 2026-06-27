"""
Strategies Module - CIP Lite
Estrategias específicas de trading por activo y régimen
"""
from .xauusd_scalper import XAUUSDScalper, XAUUSDConfig, XAUUSDBacktest

__all__ = ['XAUUSDScalper', 'XAUUSDConfig', 'XAUUSDBacktest']
