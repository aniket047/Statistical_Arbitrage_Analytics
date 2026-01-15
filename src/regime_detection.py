
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import warnings

warnings.filterwarnings('ignore')


class RegimeDetector:
    """
    Base regime detection with multiple methods.
    """
    
    @staticmethod
    def detect_regimes_kmeans(returns: pd.Series,
                             n_regimes: int = 2,
                             window: int = 20,
                             features: str = 'volatility') -> pd.Series:
        """K-Means clustering for regime detection."""
        if features == 'volatility':
            X = returns.rolling(window).std().dropna().values.reshape(-1, 1)
            valid_idx = returns.rolling(window).std().dropna().index
        
        elif features == 'volatility_skew':
            vol = returns.rolling(window).std().dropna()
            skew = returns.rolling(window).skew().dropna()
            valid_idx = vol.index.intersection(skew.index)
            X = np.column_stack([
                vol.loc[valid_idx].values,
                skew.loc[valid_idx].values
            ])
        
        elif features == 'vol_momentum':
            vol = returns.rolling(window).std()
            vol_momentum = vol.diff()
            valid_idx = vol_momentum.dropna().index
            X = np.column_stack([
                vol.loc[valid_idx].values,
                vol_momentum.loc[valid_idx].values
            ])
        
        else:
            raise ValueError(f"Unknown features: {features}")
        
        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # K-Means clustering
        kmeans = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        # Sort by volatility (regime 0 = low vol, regime 1 = high vol)
        regime_vol = {}
        for regime in range(n_regimes):
            regime_vol[regime] = X[labels == regime, 0].mean()
        
        sorted_regimes = sorted(regime_vol.items(), key=lambda x: x[1])
        regime_mapping = {old: new for new, (old, _) in enumerate(sorted_regimes)}
        labels = np.array([regime_mapping[l] for l in labels])
        
        # Align with original index
        result = pd.Series(np.nan, index=returns.index)
        result.loc[valid_idx] = labels
        
        return result.fillna(method='ffill').fillna(0)
    
    @staticmethod
    def detect_regimes_mahalanobis(returns: pd.Series,
                                  n_regimes: int = 2,
                                  window: int = 20,
                                  threshold_std: float = 2.0) -> pd.Series:
        """Regime detection using Mahalanobis distance."""
        vol = returns.rolling(window).std().dropna()
        valid_idx = vol.index
        
        X = vol.values.reshape(-1, 1)
        
        # Multivariate Gaussian components
        mean = np.mean(X)
        std = np.std(X)
        
        # Simple regime: high vs low volatility
        regimes = np.zeros(len(X))
        regimes[X.flatten() > mean + threshold_std * std] = 1
        
        # Smooth regimes
        regimes_series = pd.Series(regimes, index=valid_idx)
        regimes_smoothed = regimes_series.rolling(5, center=True).mean() > 0.5
        
        # Align with original index
        result = pd.Series(0, index=returns.index)
        result.loc[valid_idx] = regimes_smoothed.astype(int)
        
        return result
    
    @staticmethod
    def detect_regimes_hmm(returns: pd.Series,
                          n_regimes: int = 2,
                          window: int = 20) -> pd.Series:
        """Hidden Markov Model regime detection."""
        try:
            from hmmlearn import hmm
        except ImportError:
            print("hmmlearn not installed. Falling back to K-Means.")
            return RegimeDetector.detect_regimes_kmeans(returns, n_regimes, window)
        
        # Features for HMM
        vol = returns.rolling(window).std().dropna()
        valid_idx = vol.index
        
        X = np.column_stack([
            vol.values,
            returns.loc[valid_idx].values
        ])
        
        # Fit Gaussian HMM
        model = hmm.GaussianHMM(n_components=n_regimes, covariance_type="full", 
                               n_iter=1000, random_state=42)
        regimes = model.fit_predict(X)
        
        # Sort by volatility
        regime_vol = {}
        for regime in range(n_regimes):
            regime_vol[regime] = X[regimes == regime, 0].mean()
        
        sorted_regimes = sorted(regime_vol.items(), key=lambda x: x[1])
        regime_mapping = {old: new for new, (old, _) in enumerate(sorted_regimes)}
        regimes = np.array([regime_mapping[r] for r in regimes])
        
        # Align with original index
        result = pd.Series(np.nan, index=returns.index)
        result.loc[valid_idx] = regimes
        
        return result.fillna(method='ffill').fillna(0)


class VolatilityClusteringDetector:
    """
    Detects volatility clustering and GARCH effects.
    """
    
    @staticmethod
    def garch_volatility(returns: pd.Series,
                        p: int = 1,
                        q: int = 1) -> pd.Series:
        """Estimate GARCH(p,q) conditional volatility."""
        try:
            from arch import arch_model
        except ImportError:
            print("arch library not installed. Using rolling volatility.")
            return returns.rolling(20).std()
        
        # Fit GARCH model
        model = arch_model(returns * 100, vol='Garch', p=p, q=q)
        result = model.fit(disp='off')
        
        return result.conditional_volatility / 100
    
    @staticmethod
    def volatility_persistence(returns: pd.Series,
                              lags: int = 20) -> float:
        """Measure volatility clustering strength using autocorrelation."""
        squared_returns = (returns ** 2).dropna()
        
        acf_values = []
        for lag in range(1, lags + 1):
            x = squared_returns[:-lag].values
            y = squared_returns[lag:].values
            
            corr = np.corrcoef(x, y)[0, 1]
            if not np.isnan(corr):
                acf_values.append(np.abs(corr))
        
        return np.mean(acf_values) if acf_values else 0
    
    @staticmethod
    def extreme_volatility_periods(returns: pd.Series,
                                  window: int = 20,
                                  threshold_std: float = 1.5) -> pd.Series:
        """Identify periods of extreme volatility."""
        vol = returns.rolling(window).std()
        vol_mean = vol.rolling(60).mean()
        vol_std = vol.rolling(60).std()
        
        z_vol = (vol - vol_mean) / (vol_std + 1e-6)
        
        return z_vol > threshold_std


class RegimeBasedTrading:
    """
    Adapt trading strategy based on detected regimes.
    """
    
    @staticmethod
    def regime_parameters(regime: int,
                         base_entry: float = 2.0,
                         base_exit: float = 0.5) -> Dict:
        """Get trading parameters for each regime."""
        if regime == 0:  # Low volatility regime
            return {
                'entry': base_entry * 1.5,      # Less sensitive
                'exit': base_exit * 1.5,
                'position_size': 0.5,            # Smaller positions
                'stop_loss': 0.03,               # Tighter stops
            }
        else:  # High volatility regime (choppy market)
            return {
                'entry': base_entry * 0.8,      # More sensitive
                'exit': base_exit * 0.8,
                'position_size': 1.0,            # Normal positions
                'stop_loss': 0.05,               # Wider stops
            }
    
    @staticmethod
    def scale_signals_by_regime(signals: pd.Series,
                               regimes: pd.Series,
                               regime_multipliers: Dict[int, float]) -> pd.Series:
        """Scale signal strength based on regime."""
        scaled = signals.copy()
        
        for regime, multiplier in regime_multipliers.items():
            mask = regimes == regime
            scaled[mask] = signals[mask] * multiplier
        
        return scaled


class MarketMicrostructureRegime:
    """
    Detect microstructure-based regimes (liquidity, spread widening, etc.)
    """
    
    @staticmethod
    def bid_ask_spread_regime(bid_prices: pd.Series,
                             ask_prices: pd.Series,
                             window: int = 20) -> pd.Series:
        """Classify regimes based on bid-ask spread widening."""
        spread = ask_prices - bid_prices
        spread_pct = spread / bid_prices
        
        spread_ma = spread_pct.rolling(window).mean()
        spread_std = spread_pct.rolling(window).std()
        
        z_spread = (spread_pct - spread_ma) / (spread_std + 1e-6)
        
        regimes = pd.Series(0, index=spread.index)
        regimes[z_spread > 1.5] = 1  # Wide spread regime
        regimes[z_spread < -1.5] = 2  # Tight spread regime
        
        return regimes
    
    @staticmethod
    def volume_regime(volume: pd.Series,
                     window: int = 20) -> pd.Series:
        """Classify volume regimes (high vs low liquidity)."""
        vol_ma = volume.rolling(window).mean()
        vol_std = volume.rolling(window).std()
        
        z_vol = (volume - vol_ma) / (vol_std + 1e-6)
        
        regimes = pd.Series(0, index=volume.index)
        regimes[z_vol > 1.0] = 1  # High volume
        regimes[z_vol < -1.0] = 2  # Low volume
        
        return regimes

