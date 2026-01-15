
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""
    initial_capital: float = 100000
    transaction_cost_bps: int = 5
    slippage_bps: int = 2
    max_position_size: float = 0.1
    leverage_limit: float = 2.0
    rebalance_frequency: str = 'daily'
    max_drawdown_limit: float = -0.20


@dataclass
class Trade:
    """Record of a single trade."""
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    side: int
    entry_price: float
    exit_price: float
    quantity: float
    entry_cost: float
    exit_proceeds: float
    pnl: float
    pnl_pct: float


class BacktestEngine:
    """
    Production-grade backtesting engine with comprehensive analytics.
    """
    
    def __init__(self, config: BacktestConfig = None):
        """Initialize the backtesting engine."""
        self.config = config or BacktestConfig()
        self.trades = []
        self.equity_curve = None
        self.position_log = []
    
    def backtest(self,
                prices: Dict[str, pd.Series],
                signals: Dict[str, pd.Series],
                capital: Optional[float] = None) -> Tuple[pd.Series, pd.Series, Dict]:
        """Run backtest on strategy signals."""
        capital = capital or self.config.initial_capital
        
        # Align all data
        common_dates = None
        for series in list(prices.values()) + list(signals.values()):
            if common_dates is None:
                common_dates = series.index
            else:
                common_dates = common_dates.intersection(series.index)
        
        # Initialize tracking
        positions = {}
        for asset in signals.keys():
            positions[asset] = 0
        
        equity_values = [capital]
        returns_list = [0]
        cash = capital
        
        # Daily P&L tracking
        daily_pnl = pd.Series(0.0, index=common_dates)
        
        # Main backtest loop
        for i, date in enumerate(common_dates):
            daily_pnl_val = 0
            
            # Process each asset
            for asset in signals.keys():
                price_today = prices[asset].loc[date]
                signal_today = signals[asset].loc[date]
                
                # Get yesterday's position
                prev_position = positions[asset]
                
                # Position change
                position_change = signal_today - prev_position
                
                if position_change != 0:
                    # Calculate transaction costs
                    transaction_cost = np.abs(position_change) * price_today * self.config.transaction_cost_bps / 10000
                    slippage = np.abs(position_change) * price_today * self.config.slippage_bps / 10000
                    
                    cash -= transaction_cost + slippage
                    daily_pnl_val -= (transaction_cost + slippage)
                    
                    # Log position change
                    self.position_log.append({
                        'date': date,
                        'asset': asset,
                        'position': signal_today,
                        'price': price_today,
                        'transaction_cost': transaction_cost
                    })
                
                # P&L from existing position
                if i > 0:
                    prev_price = prices[asset].iloc[i-1]
                    price_change = price_today - prev_price
                    daily_pnl_val += prev_position * price_change
                
                positions[asset] = signal_today
            
            # Update equity
            daily_pnl.iloc[i] = daily_pnl_val
            equity_values.append(equity_values[-1] + daily_pnl_val)
        
        equity_curve = pd.Series(equity_values[1:], index=common_dates)
        returns = equity_curve.pct_change().fillna(0)
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_curve, returns)
        
        self.equity_curve = equity_curve
        
        return equity_curve, returns, metrics
    
    def backtest_spread_based(self,
                            spread: pd.Series,
                            signals: pd.Series,
                            price_x: pd.Series,
                            price_y: pd.Series,
                            hedge_ratio: float = 1.0,
                            capital: Optional[float] = None) -> Tuple[pd.Series, pd.Series, Dict]:
        """Backtest on spread (pair trading specific)."""
        capital = capital or self.config.initial_capital
        
        # Align indices
        common_idx = spread.index.intersection(signals.index).intersection(price_x.index)
        spread = spread.loc[common_idx]
        signals = signals.loc[common_idx]
        price_x = price_x.loc[common_idx]
        price_y = price_y.loc[common_idx]
        
        equity = capital
        equity_curve = [equity]
        positions = 0
        
        for i in range(1, len(common_idx)):
            signal_today = signals.iloc[i]
            
            # Calculate PnL from previous day's position
            if positions != 0:
                pnl = positions * (spread.iloc[i] - spread.iloc[i-1])
                equity += pnl
            
            # Transaction costs on position changes
            if signal_today != positions:
                transaction_cost = np.abs(signal_today - positions) * np.abs(spread.iloc[i]) * self.config.transaction_cost_bps / 10000
                equity -= transaction_cost
            
            positions = signal_today
            equity_curve.append(equity)
        
        equity_curve = pd.Series(equity_curve, index=common_idx)
        returns = equity_curve.pct_change().fillna(0)
        metrics = self._calculate_metrics(equity_curve, returns)
        
        return equity_curve, returns, metrics
    
    @staticmethod
    def _calculate_metrics(equity_curve: pd.Series, 
                          returns: pd.Series) -> Dict:
        """Calculate comprehensive performance metrics."""
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
        annual_return = (1 + total_return) ** (252 / len(equity_curve)) - 1
        
        # Volatility
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        # Sharpe Ratio
        sharpe = (annual_return / annual_vol) if annual_vol > 0 else 0
        
        # Sortino Ratio
        downside_returns = returns[returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252)
        sortino = (annual_return / downside_vol) if downside_vol > 0 else 0
        
        # Maximum Drawdown
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()
        max_drawdown_duration = 0
        
        if len(drawdown) > 0:
            # Calculate drawdown duration
            in_drawdown = drawdown < 0
            if in_drawdown.any():
                transitions = (in_drawdown.astype(int).diff() != 0).astype(int)
                max_drawdown_duration = in_drawdown.sum()
        
        # Win Rate
        winning_days = (returns > 0).sum()
        total_days = len(returns[returns != 0])
        win_rate = (winning_days / total_days) if total_days > 0 else 0
        
        # Profit Factor
        gross_profit = returns[returns > 0].sum()
        gross_loss = np.abs(returns[returns < 0].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf
        
        # Calmar Ratio
        calmar = annual_return / np.abs(max_drawdown) if max_drawdown < 0 else np.inf
        
        metrics = {
            'total_return': total_return,
            'annual_return': annual_return,
            'daily_volatility': daily_vol,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'calmar_ratio': calmar,
            'total_trades': len(returns[returns != 0])
        }
        
        return metrics


class WalkForwardOptimizer:
    """
    Walk-forward analysis for robust strategy validation.
    """
    
    @staticmethod
    def walk_forward_backtest(data: pd.DataFrame,
                            signal_func,
                            train_window: int = 252,
                            test_window: int = 63,
                            step: int = 63,
                            config: BacktestConfig = None) -> Dict:
        """Perform walk-forward analysis."""
        engine = BacktestEngine(config)
        results = {
            'periods': [],
            'test_returns': [],
            'test_metrics': []
        }
        
        n = len(data)
        pos = 0
        
        while pos + train_window + test_window <= n:
            # Train/test split
            train_data = data.iloc[pos:pos + train_window]
            test_data = data.iloc[pos + train_window:pos + train_window + test_window]
            
            # Generate signals on test set (trained on train set)
            try:
                signals = signal_func(train_data, test_data)
                
                # Note: This is simplified. In practice, would need proper signal generation
                # that trains on train_data and applies to test_data
                
                results['periods'].append({
                    'train_start': train_data.index[0],
                    'test_start': test_data.index[0],
                    'test_end': test_data.index[-1]
                })
            except Exception as e:
                print(f"Walk-forward period failed: {e}")
            
            pos += step
        
        return results


class DrawdownAnalyzer:
    """
    Detailed drawdown and recovery analysis.
    """
    
    @staticmethod
    def calculate_drawdowns(equity_curve: pd.Series) -> pd.DataFrame:
        """
        Identify all drawdown periods.
        """
        running_max = equity_curve.expanding().max()
        drawdown_pct = (equity_curve - running_max) / running_max
        
        drawdowns = []
        in_dd = False
        dd_start = None
        dd_peak = None
        
        for date, value in equity_curve.items():
            dd_pct = drawdown_pct.loc[date]
            
            if dd_pct < 0 and not in_dd:
                in_dd = True
                dd_start = date
                dd_peak = running_max.loc[date]
            
            if dd_pct >= 0 and in_dd:
                in_dd = False
                drawdowns.append({
                    'start': dd_start,
                    'end': date,
                    'peak': dd_peak,
                    'trough': equity_curve.loc[dd_start:date].min(),
                    'drawdown': drawdown_pct.loc[dd_start:date].min(),
                    'duration': (date - dd_start).days
                })
        
        return pd.DataFrame(drawdowns)

