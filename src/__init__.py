"""
Statistical Arbitrage Analytics - Source Module
Production-grade quantitative research package
"""

__version__ = "1.0.0"
__author__ = "Quantitative Research Team"

from . import statistics
from . import strategy
from . import backtest
from . import metrics
from . import regime_detection

__all__ = [
    'statistics',
    'strategy',
    'backtest',
    'metrics',
    'regime_detection'
]
