
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


class PerformanceMetrics:
    """
    Comprehensive performance metrics calculation.
    """
    
    @staticmethod
    def sharpe_ratio(returns: pd.Series, 
                    risk_free_rate: float = 0.0,
                    periods_per_year: int = 252) -> float:
        """Sharpe Ratio: (return - risk_free_rate) / volatility."""
        excess_returns = returns - (risk_free_rate / periods_per_year)
        return np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())
    
    @staticmethod
    def sortino_ratio(returns: pd.Series,
                     risk_free_rate: float = 0.0,
                     periods_per_year: int = 252,
                     target_return: float = 0.0) -> float:
        """Sortino Ratio: penalizes only downside volatility."""
        excess_returns = returns - (risk_free_rate / periods_per_year)
        downside_returns = excess_returns[excess_returns < target_return]
        
        if len(downside_returns) == 0:
            return np.inf
        
        downside_vol = downside_returns.std()
        
        if downside_vol == 0:
            return np.inf
        
        return np.sqrt(periods_per_year) * (excess_returns.mean() / downside_vol)
    
    @staticmethod
    def calmar_ratio(returns: pd.Series,
                    equity_curve: pd.Series,
                    periods_per_year: int = 252) -> float:
        """Calmar Ratio: annual return / max drawdown."""
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annual_return = (1 + total_return) ** (periods_per_year / len(equity_curve)) - 1
        
        max_dd = DrawdownMetrics.max_drawdown(equity_curve)
        
        if max_dd >= 0:
            return 0
        
        return annual_return / np.abs(max_dd)
    
    @staticmethod
    def information_ratio(returns: pd.Series,
                         benchmark_returns: pd.Series,
                         periods_per_year: int = 252) -> float:
        """Information Ratio: (return - benchmark_return) / tracking_error."""
        active_returns = returns - benchmark_returns
        tracking_error = active_returns.std()
        
        if tracking_error == 0:
            return 0
        
        return np.sqrt(periods_per_year) * (active_returns.mean() / tracking_error)
    
    @staticmethod
    def return_metrics(returns: pd.Series,
                      equity_curve: pd.Series,
                      periods_per_year: int = 252) -> Dict[str, float]:
        """Comprehensive return metrics."""
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annual_return = (1 + total_return) ** (periods_per_year / len(equity_curve)) - 1
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        
        return {
            'total_return': total_return,
            'annualized_return': annual_return,
            'daily_mean_return': returns.mean(),
            'daily_median_return': returns.median(),
            'best_day': returns.max(),
            'worst_day': returns.min(),
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis()
        }
    
    @staticmethod
    def volatility_metrics(returns: pd.Series,
                          periods_per_year: int = 252) -> Dict[str, float]:
        """Comprehensive volatility metrics."""
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(periods_per_year)
        
        # Rolling volatility
        rolling_vol = returns.rolling(20).std()
        
        return {
            'daily_volatility': daily_vol,
            'annual_volatility': annual_vol,
            'volatility_of_volatility': rolling_vol.std(),
            'min_rolling_vol': rolling_vol.min(),
            'max_rolling_vol': rolling_vol.max()
        }


class DrawdownMetrics:
    """
    Drawdown-specific metrics and analysis.
    """
    
    @staticmethod
    def max_drawdown(equity_curve: pd.Series) -> float:
        """Maximum drawdown as percentage."""
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        return drawdown.min()
    
    @staticmethod
    def drawdown_duration(equity_curve: pd.Series) -> Tuple[int, float]:
        """Maximum drawdown duration and average duration."""
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        
        in_drawdown = drawdown < 0
        durations = []
        current_duration = 0
        
        for in_dd in in_drawdown:
            if in_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0
        
        if not durations:
            return 0, 0
        
        return max(durations), np.mean(durations)
    
    @staticmethod
    def calmar_ratio_from_equity(equity_curve: pd.Series,
                                periods_per_year: int = 252) -> float:
        """Calculate Calmar ratio from equity curve."""
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annual_return = (1 + total_return) ** (periods_per_year / len(equity_curve)) - 1
        
        max_dd = DrawdownMetrics.max_drawdown(equity_curve)
        
        if max_dd >= 0:
            return 0
        
        return annual_return / np.abs(max_dd)
    
    @staticmethod
    def recovery_factor(equity_curve: pd.Series) -> float:
        """Recovery Factor = Total Profit / Max Drawdown."""
        total_profit = equity_curve.iloc[-1] - equity_curve.iloc[0]
        max_dd_dollars = equity_curve.iloc[0] * np.abs(DrawdownMetrics.max_drawdown(equity_curve))
        
        if max_dd_dollars == 0:
            return np.inf
        
        return total_profit / max_dd_dollars
    
    @staticmethod
    def underwater_plot_data(equity_curve: pd.Series) -> pd.Series:
        """Calculate underwater (drawdown) profile."""
        running_max = equity_curve.expanding().max()
        underwater = (equity_curve - running_max) / running_max
        return underwater


class TradeMetrics:
    """
    Individual trade and trade sequence metrics.
    """
    
    @staticmethod
    def winning_trades(returns: pd.Series) -> pd.Series:
        """Filter positive returns."""
        return returns[returns > 0]
    
    @staticmethod
    def losing_trades(returns: pd.Series) -> pd.Series:
        """Filter negative returns."""
        return returns[returns < 0]
    
    @staticmethod
    def trade_statistics(returns: pd.Series) -> Dict[str, float]:
        """Comprehensive trade statistics."""
        wins = TradeMetrics.winning_trades(returns)
        losses = TradeMetrics.losing_trades(returns)
        all_trades = returns[returns != 0]
        
        if len(all_trades) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'win_loss_ratio': 0,
                'profit_factor': 0
            }
        
        total_trades = len(all_trades)
        num_wins = len(wins)
        num_losses = len(losses)
        
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = losses.mean() if len(losses) > 0 else 0
        
        win_loss_ratio = avg_win / np.abs(avg_loss) if avg_loss != 0 else np.inf
        
        gross_profit = wins.sum() if len(wins) > 0 else 0
        gross_loss = np.abs(losses.sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
        
        return {
            'total_trades': total_trades,
            'winning_trades': num_wins,
            'losing_trades': num_losses,
            'win_rate': num_wins / total_trades if total_trades > 0 else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_loss_ratio': win_loss_ratio,
            'profit_factor': profit_factor,
            'largest_win': wins.max() if len(wins) > 0 else 0,
            'largest_loss': losses.min() if len(losses) > 0 else 0,
            'consecutive_wins': TradeMetrics.max_consecutive(wins),
            'consecutive_losses': TradeMetrics.max_consecutive(losses)
        }
    
    @staticmethod
    def max_consecutive(returns: pd.Series) -> int:
        """Maximum consecutive winning or losing trades."""
        if len(returns) == 0:
            return 0
        
        # Simple consecutive count
        consecutive = 1
        max_consecutive = 1
        
        for i in range(1, len(returns)):
            if (returns.iloc[i] > 0 and returns.iloc[i-1] > 0) or \
               (returns.iloc[i] < 0 and returns.iloc[i-1] < 0):
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 1
        
        return max_consecutive


class RiskMetrics:
    """
    Risk-focused metrics.
    """
    
    @staticmethod
    def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
        """Value at Risk: loss level at given confidence."""
        return np.percentile(returns, (1 - confidence) * 100)
    
    @staticmethod
    def conditional_value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
        """Conditional Value at Risk (Expected Shortfall)."""
        var = RiskMetrics.value_at_risk(returns, confidence)
        return returns[returns <= var].mean()
    
    @staticmethod
    def beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """
        Beta: covariance with benchmark / benchmark variance
        """
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        
        if benchmark_variance == 0:
            return 0
        
        return covariance / benchmark_variance
    
    @staticmethod
    def maximum_loss_ratio(returns: pd.Series) -> float:
        """Ratio of max loss to standard deviation."""
        max_loss = returns.min()
        std = returns.std()
        
        if std == 0:
            return 0
        
        return max_loss / std
    
    @staticmethod
    def tail_ratio(returns: pd.Series, percentile: int = 5) -> float:
        """Ratio of gains to losses at same percentile."""
        upper_tail = np.percentile(returns, 100 - percentile)
        lower_tail = np.percentile(returns, percentile)
        
        if lower_tail >= 0:
            return np.inf
        
        return np.abs(upper_tail / lower_tail)


def calculate_all_metrics(returns: pd.Series, 
                         equity_curve: pd.Series,
                         benchmark_returns: Optional[pd.Series] = None) -> Dict:
    """Calculate all available metrics at once."""
    all_metrics = {}
    
    # Performance metrics
    all_metrics['performance'] = PerformanceMetrics.return_metrics(returns, equity_curve)
    all_metrics['volatility'] = PerformanceMetrics.volatility_metrics(returns)
    all_metrics['risk_adjusted'] = {
        'sharpe_ratio': PerformanceMetrics.sharpe_ratio(returns),
        'sortino_ratio': PerformanceMetrics.sortino_ratio(returns),
        'calmar_ratio': PerformanceMetrics.calmar_ratio(returns, equity_curve),
    }
    
    # Drawdown metrics
    all_metrics['drawdown'] = {
        'max_drawdown': DrawdownMetrics.max_drawdown(equity_curve),
        'max_duration_days': DrawdownMetrics.drawdown_duration(equity_curve)[0],
        'recovery_factor': DrawdownMetrics.recovery_factor(equity_curve)
    }
    
    # Trade metrics
    all_metrics['trades'] = TradeMetrics.trade_statistics(returns)
    
    # Risk metrics
    all_metrics['risk'] = {
        'var_95': RiskMetrics.value_at_risk(returns, 0.95),
        'cvar_95': RiskMetrics.conditional_value_at_risk(returns, 0.95),
        'max_loss_ratio': RiskMetrics.maximum_loss_ratio(returns),
        'tail_ratio': RiskMetrics.tail_ratio(returns)
    }
    
    # Benchmark metrics (if provided)
    if benchmark_returns is not None:
        all_metrics['benchmark'] = {
            'beta': RiskMetrics.beta(returns, benchmark_returns),
            'information_ratio': PerformanceMetrics.information_ratio(returns, benchmark_returns)
        }
    
    return all_metrics

