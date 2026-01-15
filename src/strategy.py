
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
from .statistics import ZScoreCalculator, MeanReversionAnalyzer


class PairTradingStrategy:
    """
    Implements a mean-reversion based pair trading strategy.
    """
    
    def __init__(self, 
                 z_entry: float = 2.0,
                 z_exit: float = 0.5,
                 z_max: float = 3.5,
                 volatility_window: int = 30):
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.z_max = z_max
        self.vol_window = volatility_window
        self.state = None
    
    def generate_signals(self, 
                        spread: pd.Series,
                        entry: Optional[float] = None,
                        exit: Optional[float] = None,
                        rolling_window: int = 60,
                        use_exponential: bool = True) -> Tuple[pd.Series, pd.Series]:
        """Generate buy/sell signals based on z-score of spread."""
        entry = entry or self.z_entry
        exit = exit or self.z_exit
        
        # Calculate z-scores
        if use_exponential:
            z_scores = ZScoreCalculator.exponential_zscore(spread, span=rolling_window)
        else:
            z_scores = ZScoreCalculator.rolling_zscore(spread, window=rolling_window)
        
        # Initialize signals
        signals = pd.Series(0, index=spread.index, dtype=float)
        position = 0  # 0: flat, 1: long, -1: short
        
        # State machine for entry/exit
        for i in range(len(z_scores)):
            z = z_scores.iloc[i]
            
            if pd.isna(z):
                signals.iloc[i] = position
                continue
            
            # Exit signals (tighter threshold)
            if position == 1 and z < exit:  # Long exit
                position = 0
            elif position == -1 and z > -exit:  # Short exit
                position = 0
            
            # Entry signals (wider threshold)
            elif position == 0:
                if z > entry:  # Short signal (mean will revert down)
                    position = -1
                elif z < -entry:  # Long signal (mean will revert up)
                    position = 1
            
            signals.iloc[i] = position
        
        return signals, z_scores
    
    def generate_signals_with_filters(self,
                                     spread: pd.Series,
                                     price_x: pd.Series,
                                     price_y: pd.Series,
                                     entry: float = 2.0,
                                     exit: float = 0.5,
                                     min_halflife: int = 5,
                                     max_halflife: int = 252) -> pd.Series:
        """Generate signals with mean reversion quality filters."""
        signals, z_scores = self.generate_signals(spread, entry, exit)
        
        # Calculate mean reversion halflife
        halflife = MeanReversionAnalyzer.half_life_ar1(spread)
        
        # Filter: only trade if mean reversion is reasonable
        if pd.isna(halflife) or halflife < min_halflife or halflife > max_halflife:
            return pd.Series(0, index=spread.index)
        
        # Adjust signals based on trend in underlying prices
        price_x_momentum = price_x.pct_change(5).rolling(10).mean()
        
        # Reduce position size if prices are in strong trend
        momentum_filter = np.abs(price_x_momentum) < 0.02  # 2% threshold
        
        filtered_signals = signals.copy()
        filtered_signals[~momentum_filter] = filtered_signals[~momentum_filter] * 0.5
        
        return filtered_signals
    
    def volatility_adjusted_signals(self,
                                   spread: pd.Series,
                                   signals: pd.Series,
                                   vol_window: int = 30) -> pd.Series:
        """Adjust signal strength based on volatility."""
        volatility = spread.rolling(vol_window).std()
        vol_ma = volatility.rolling(60).mean()
        vol_ratio = volatility / (vol_ma + 1e-6)
        
        # Adjust signal magnitude inversely to volatility
        adjusted_signals = signals.copy()
        for i in range(len(signals)):
            if vol_ratio.iloc[i] > 1.5:  # High volatility
                adjusted_signals.iloc[i] = signals.iloc[i] * 0.5
            elif vol_ratio.iloc[i] < 0.75:  # Low volatility
                adjusted_signals.iloc[i] = signals.iloc[i] * 1.2
        
        return adjusted_signals
    
    def regime_adjusted_signals(self,
                               signals: pd.Series,
                               regimes: pd.Series,
                               regime_params: Dict[int, float]) -> pd.Series:
        """Adjust signals based on detected market regime."""
        adjusted = signals.copy()
        for regime, multiplier in regime_params.items():
            mask = regimes == regime
            adjusted[mask] = signals[mask] * multiplier
        
        return adjusted


class PairSelectionStrategy:
    """
    Identifies and ranks potential pairs for statistical arbitrage.
    """
    
    @staticmethod
    def select_pairs(price_matrix: pd.DataFrame,
                    min_correlation: float = 0.6,
                    max_correlation: float = 0.95,
                    coint_pvalue: float = 0.05) -> list:
        """Select cointegrated pairs from asset universe."""
        from .statistics import CointegratedPairAnalyzer
        
        pairs = []
        assets = price_matrix.columns
        n = len(assets)
        
        for i in range(n):
            for j in range(i + 1, n):
                asset1, asset2 = assets[i], assets[j]
                x, y = price_matrix[asset1].values, price_matrix[asset2].values
                
                # Correlation filter
                corr = np.corrcoef(x, y)[0, 1]
                if corr < min_correlation or corr > max_correlation:
                    continue
                
                # Cointegration test
                try:
                    _, pval, beta = CointegratedPairAnalyzer.engle_granger_test(x, y)
                    if pval < coint_pvalue:
                        pairs.append({
                            'pair': (asset1, asset2),
                            'correlation': corr,
                            'coint_pvalue': pval,
                            'hedge_ratio': beta[1]
                        })
                except:
                    continue
        
        # Sort by p-value (most cointegrated first)
        pairs = sorted(pairs, key=lambda x: x['coint_pvalue'])
        return pairs
    
    @staticmethod
    def score_pairs(pairs: list, 
                   halflife_min: int = 5,
                   halflife_max: int = 252) -> list:
        """Score pairs based on trading quality metrics."""
        scored = []
        
        for pair_info in pairs:
            pair = pair_info['pair']
            
            # In production, would load actual price data here
            # For now, assigning composite score
            
            score = {
                'pair': pair,
                'coint_score': 100 * (0.05 / (pair_info['coint_pvalue'] + 0.001)),
                'correlation_score': pair_info['correlation'] * 100,
                'composite_score': 0
            }
            
            # Weighted composite score
            score['composite_score'] = (
                0.5 * score['coint_score'] + 
                0.5 * score['correlation_score']
            )
            
            scored.append(score)
        
        # Sort by composite score (highest first)
        return sorted(scored, key=lambda x: x['composite_score'], reverse=True)

