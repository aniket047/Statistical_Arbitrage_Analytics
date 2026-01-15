
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint, adfuller, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from typing import Tuple, Union
import warnings

warnings.filterwarnings('ignore')


class CointegratedPairAnalyzer:
    """
    Analyzes cointegration between two time series using multiple econometric tests.
    """
    
    @staticmethod
    def engle_granger_test(x: np.ndarray, y: np.ndarray, 
                          deterministic: str = "ci") -> Tuple[float, float, np.ndarray]:
        """Engle-Granger two-step cointegration test."""
        test_stat, pvalue, _ = coint(x, y, autolag='AIC', maxlag=12)
        
        X = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        
        return test_stat, pvalue, beta
    
    @staticmethod
    def johansen_test(data: pd.DataFrame, det_order: int = 0, 
                     k_ar_diff: int = 1) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Johansen cointegration test for multivariate systems."""
        result = coint_johansen(data, det_order=det_order, k_ar_diff=k_ar_diff)
        return result.eig[0], result.eig[1], result.lr1[:, 0]
    
    @staticmethod
    def adf_test(series: Union[pd.Series, np.ndarray], 
                maxlag: int = 12) -> Tuple[float, float, int, int]:
        """Augmented Dickey-Fuller stationarity test."""
        result = adfuller(series, maxlag=maxlag, autolag='AIC')
        return result[0], result[1], result[2], result[3]
    
    @staticmethod
    def kpss_test(series: Union[pd.Series, np.ndarray], 
                 regression: str = 'c') -> Tuple[float, float]:
        """KPSS stationarity test (null: series is stationary)."""
        result = kpss(series, regression=regression, nlags='auto')
        return result[0], result[1]
    
    @staticmethod
    def is_cointegrated(x: np.ndarray, y: np.ndarray, 
                       threshold: float = 0.05) -> bool:
        """Check if series are cointegrated at given significance level."""
        _, pvalue, _ = coint(x, y, autolag='AIC')
        return pvalue < threshold
    
    @staticmethod
    def is_stationary(series: Union[pd.Series, np.ndarray], 
                     test: str = 'adf', threshold: float = 0.05) -> bool:
        """Check if series is stationary using specified test."""
        if test == 'adf':
            _, pvalue, _, _ = CointegratedPairAnalyzer.adf_test(series)
            return pvalue < threshold
        elif test == 'kpss':
            _, pvalue = CointegratedPairAnalyzer.kpss_test(series)
            return pvalue > threshold
        else:
            raise ValueError(f"Unknown test: {test}")


class ZScoreCalculator:
    """
    Advanced z-score calculations with multiple normalization methods.
    """
    
    @staticmethod
    def simple_zscore(series: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """
        Standard z-score: (x - mean) / std
        """
        series_arr = np.asarray(series)
        mean = np.mean(series_arr)
        std = np.std(series_arr)
        if std == 0:
            return np.zeros_like(series_arr)
        return (series_arr - mean) / std
    
    @staticmethod
    def rolling_zscore(series: Union[pd.Series, np.ndarray], 
                      window: int = 60) -> pd.Series:
        """Rolling z-score with adaptive window."""
        if isinstance(series, np.ndarray):
            series = pd.Series(series)
        
        rolling_mean = series.rolling(window=window, min_periods=1).mean()
        rolling_std = series.rolling(window=window, min_periods=1).std()
        rolling_std = rolling_std.replace(0, np.nan)  # Avoid division by zero
        
        zscore = (series - rolling_mean) / rolling_std
        return zscore.fillna(0)
    
    @staticmethod
    def exponential_zscore(series: Union[pd.Series, np.ndarray], 
                          span: int = 30) -> pd.Series:
        """Exponential moving average z-score."""
        if isinstance(series, np.ndarray):
            series = pd.Series(series)
        
        ema_mean = series.ewm(span=span, adjust=False).mean()
        ema_std = series.ewm(span=span, adjust=False).std()
        ema_std = ema_std.replace(0, np.nan)
        
        zscore = (series - ema_mean) / ema_std
        return zscore.fillna(0)
    
    @staticmethod
    def mahalanobis_distance(x: np.ndarray, mean: np.ndarray = None, 
                            cov: np.ndarray = None) -> np.ndarray:
        """Mahalanobis distance for multivariate z-score."""
        x = np.asarray(x)
        if mean is None:
            mean = np.mean(x, axis=0)
        if cov is None:
            cov = np.cov(x.T)
        
        diff = x - mean
        try:
            inv_cov = np.linalg.inv(cov)
            distances = np.sqrt(np.sum(diff @ inv_cov * diff, axis=1))
        except np.linalg.LinAlgError:
            # If singular, use pseudo-inverse
            inv_cov = np.linalg.pinv(cov)
            distances = np.sqrt(np.sum(diff @ inv_cov * diff, axis=1))
        
        return distances


class MeanReversionAnalyzer:
    """
    Analyzes mean reversion properties of spreads.
    """
    
    @staticmethod
    def half_life_ar1(spread: Union[pd.Series, np.ndarray]) -> float:
        """Estimate half-life of mean reversion using AR(1) model."""
        spread_arr = np.asarray(spread)
        if len(spread_arr) < 2:
            return np.nan
        
        # Fit AR(1): y_t = c + phi * y_{t-1} + epsilon_t
        y = spread_arr[1:]
        X = np.column_stack([np.ones(len(y)), spread_arr[:-1]])
        
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            phi = beta[1]
            
            if phi <= 0 or phi >= 1:
                return np.nan
            
            half_life = -np.log(2) / np.log(phi)
            return half_life
        except:
            return np.nan
    
    @staticmethod
    def autocorrelation_decay(spread: Union[pd.Series, np.ndarray], 
                             max_lags: int = 50) -> Tuple[np.ndarray, float]:
        """Compute autocorrelation decay and estimate mean reversion strength."""
        spread_arr = np.asarray(spread)
        mean = np.mean(spread_arr)
        c0 = np.sum((spread_arr - mean) ** 2) / len(spread_arr)
        
        acf = np.zeros(max_lags)
        for k in range(max_lags):
            acf[k] = np.sum((spread_arr[:-k-1] - mean) * (spread_arr[k+1:] - mean)) / (len(spread_arr) * c0)
        
        # Mean reversion score: negative slope of autocorrelation
        x = np.arange(max_lags)
        slope = np.polyfit(x, acf, 1)[0]
        
        return acf, -slope  # Return negative slope as strength


class CorrelationAnalyzer:
    """
    Robust correlation analysis with multiple estimators.
    """
    
    @staticmethod
    def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
        """Pearson correlation coefficient."""
        return np.corrcoef(x, y)[0, 1]
    
    @staticmethod
    def spearman_correlation(x: np.ndarray, y: np.ndarray) -> float:
        """Spearman rank correlation (robust to outliers)."""
        from scipy.stats import spearmanr
        return spearmanr(x, y)[0]
    
    @staticmethod
    def rolling_correlation(x: pd.Series, y: pd.Series, 
                           window: int = 60) -> pd.Series:
        """Rolling Pearson correlation."""
        return x.rolling(window).corr(y)
    
    @staticmethod
    def correlation_matrix_robust(data: pd.DataFrame, 
                                 method: str = 'pearson') -> pd.DataFrame:
        """Robust correlation matrix computation."""
        return data.corr(method=method)


class BetaHedgingCalculator:
    """
    Calculates optimal hedge ratios for pair trading.
    """
    
    @staticmethod
    def hedge_ratio_ols(x: np.ndarray, y: np.ndarray) -> float:
        """OLS hedge ratio: regression slope."""
        X = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        return beta[1]
    
    @staticmethod
    def hedge_ratio_gls(x: np.ndarray, y: np.ndarray) -> float:
        """Generalized Least Squares hedge ratio."""
        X = np.column_stack([np.ones(len(x)), x])
        
        # First pass OLS
        beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ beta_ols
        
        # Estimate heteroskedasticity
        weights = 1 / (np.abs(residuals) + 1e-6)
        W = np.diag(weights)
        
        # GLS
        beta_gls = np.linalg.lstsq(W**0.5 @ X, W**0.5 @ y, rcond=None)[0]
        return beta_gls[1]

