
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, Tuple, List
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    CAPITAL, TRADING_DAYS, Z_ENTRY, Z_EXIT, COINT_PVALUE_THRESHOLD,
    DATA_PATH, RESULTS_PATH, LOG_LEVEL, LOG_FORMAT, MIN_CORRELATION,
    LOOKBACK_COINT, ROLLING_WINDOW_ZSCORE, TRAIN_WINDOW, TEST_WINDOW,
    TICKERS_UNIVERSE
)

from src.statistics import (
    CointegratedPairAnalyzer, ZScoreCalculator, MeanReversionAnalyzer,
    CorrelationAnalyzer, BetaHedgingCalculator
)

from src.strategy import PairTradingStrategy, PairSelectionStrategy
from src.backtest import BacktestEngine, BacktestConfig, WalkForwardOptimizer
from src.metrics import (
    PerformanceMetrics, DrawdownMetrics, TradeMetrics, RiskMetrics,
    calculate_all_metrics
)
from src.regime_detection import RegimeDetector, VolatilityClusteringDetector


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)
def load_data(tickers: List[str], lookback_days: int = 252) -> pd.DataFrame:
    """Load price data for specified tickers."""
    logger.info(f"Loading data for {len(tickers)} tickers...")
    
    data = {}
    for ticker in tickers:
        csv_path = os.path.join(DATA_PATH, f"{ticker}.csv")
        
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, index_col='Date', parse_dates=True)
            close_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            data[ticker] = df[close_col].iloc[-lookback_days:]
            logger.info(f"  {ticker}: Loaded {len(data[ticker])} observations")
        else:
            logger.warning(f"  {ticker}: Data file not found at {csv_path}")
    
    return pd.DataFrame(data).dropna()


def analyze_and_select_pairs(prices: pd.DataFrame,
                            min_corr: float = MIN_CORRELATION,
                            pval_thresh: float = COINT_PVALUE_THRESHOLD) -> List[Dict]:
    """Comprehensive pair selection with cointegration testing."""
    logger.info("Analyzing pairs for cointegration...")
    
    analyzer = CointegratedPairAnalyzer()
    selected_pairs = []
    
    assets = prices.columns.tolist()
    n = len(assets)
    
    logger.info(f"Testing {n * (n-1) // 2} potential pairs...")
    
    for i in range(n):
        for j in range(i + 1, n):
            asset1, asset2 = assets[i], assets[j]
            x = prices[asset1].values
            y = prices[asset2].values
            
            # Correlation check
            corr = np.corrcoef(x, y)[0, 1]
            if corr < min_corr or corr > 0.99:  # Avoid near-perfect correlation
                continue
            
            # Stationarity tests
            try:
                adf_stat1, adf_pval1, _, _ = analyzer.adf_test(x)
                adf_stat2, adf_pval2, _, _ = analyzer.adf_test(y)
                
                # Both should be I(1) - non-stationary
                if adf_pval1 < 0.05 or adf_pval2 < 0.05:
                    continue
                
                # Cointegration test
                _, coint_pval, beta = analyzer.engle_granger_test(x, y)
                
                if coint_pval > pval_thresh:
                    continue
                
                # Calculate spread
                spread = y - beta[1] * x
                
                # Mean reversion properties
                halflife = MeanReversionAnalyzer.half_life_ar1(spread)
                acf, mr_strength = MeanReversionAnalyzer.autocorrelation_decay(spread)
                
                # Only trade if halflife is reasonable
                if not np.isnan(halflife) and 5 <= halflife <= 252:
                    pair_info = {
                        'pair': (asset1, asset2),
                        'correlation': corr,
                        'coint_pvalue': coint_pval,
                        'hedge_ratio': beta[1],
                        'halflife': halflife,
                        'mr_strength': mr_strength,
                        'adf_pval_x': adf_pval1,
                        'adf_pval_y': adf_pval2
                    }
                    selected_pairs.append(pair_info)
                    
                    logger.info(f"  ✓ {asset1}-{asset2}: Coint p={coint_pval:.4f}, "
                              f"HL={halflife:.1f}d, Corr={corr:.3f}")
            
            except Exception as e:
                logger.debug(f"  ✗ {asset1}-{asset2}: {str(e)}")
                continue
    
    # Sort by cointegration strength
    selected_pairs = sorted(selected_pairs, key=lambda x: x['coint_pvalue'])
    
    logger.info(f"\nFound {len(selected_pairs)} cointegrated pair(s)")
    
    return selected_pairs


def generate_trading_signals(prices: Dict[str, pd.Series],
                            pair_info: Dict,
                            config: BacktestConfig) -> Tuple[pd.Series, pd.Series]:
    """Generate trading signals for a cointegrated pair."""
    asset1, asset2 = pair_info['pair']
    hedge_ratio = pair_info['hedge_ratio']
    
    x = prices[asset1]
    y = prices[asset2]
    
    # Calculate spread
    spread = y - hedge_ratio * x
    
    # Generate signals with regime detection
    strategy = PairTradingStrategy(
        z_entry=Z_ENTRY,
        z_exit=Z_EXIT,
        volatility_window=30
    )
    
    signals, z_scores = strategy.generate_signals(
        spread,
        rolling_window=ROLLING_WINDOW_ZSCORE,
        use_exponential=True
    )
    
    # Detect regimes
    returns = spread.pct_change().dropna()
    regimes = RegimeDetector.detect_regimes_kmeans(
        returns,
        n_regimes=2,
        window=20,
        features='volatility'
    )
    
    # Adjust signals for regime
    regime_params = {
        0: 1.0,   # Low volatility: full signal
        1: 0.7    # High volatility: reduced signal
    }
    
    from src.regime_detection import RegimeBasedTrading
    signals = RegimeBasedTrading.scale_signals_by_regime(
        signals, regimes, regime_params
    )
    
    return signals, z_scores


def backtest_pair_strategy(prices: Dict[str, pd.Series],
                          signals: pd.Series,
                          pair_info: Dict,
                          capital: float = CAPITAL) -> Dict:
    """Run backtest on pair trading strategy."""
    logger.info("Running backtest...")
    
    config = BacktestConfig(
        initial_capital=capital,
        transaction_cost_bps=5,
        slippage_bps=2
    )
    
    engine = BacktestEngine(config)
    
    # Calculate spread
    asset1, asset2 = pair_info['pair']
    hedge_ratio = pair_info['hedge_ratio']
    
    x = prices[asset1]
    y = prices[asset2]
    spread = y - hedge_ratio * x
    
    # Run backtest
    equity_curve, returns, metrics = engine.backtest_spread_based(
        spread=spread,
        signals=signals,
        price_x=x,
        price_y=y,
        hedge_ratio=hedge_ratio,
        capital=capital
    )
    
    logger.info(f"Backtest Period: {equity_curve.index[0].date()} to "
              f"{equity_curve.index[-1].date()}")
    logger.info(f"Initial Capital: ${capital:,.0f}")
    logger.info(f"Final Equity: ${equity_curve.iloc[-1]:,.0f}")
    logger.info(f"Total Return: {metrics['total_return']:.2%}")
    logger.info(f"Annual Return: {metrics['annual_return']:.2%}")
    logger.info(f"Annual Volatility: {metrics['annual_volatility']:.2%}")
    logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    logger.info(f"Win Rate: {metrics['win_rate']:.2%}")
    
    return {
        'pair': pair_info['pair'],
        'equity_curve': equity_curve,
        'returns': returns,
        'metrics': metrics,
        'signals': signals
    }


def detailed_performance_analysis(backtest_results: Dict) -> Dict:
    """Generate detailed performance analysis."""
    logger.info("Computing detailed metrics...")
    
    equity = backtest_results['equity_curve']
    returns = backtest_results['returns']
    
    # All metrics
    all_metrics = calculate_all_metrics(returns, equity)
    
    logger.info("\n--- RETURN METRICS ---")
    for key, value in all_metrics['performance'].items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.4f}")
    
    logger.info("\n--- VOLATILITY METRICS ---")
    for key, value in all_metrics['volatility'].items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.4f}")
    
    logger.info("\n--- RISK-ADJUSTED RETURNS ---")
    for key, value in all_metrics['risk_adjusted'].items():
        logger.info(f"  {key}: {value:.4f}")
    
    logger.info("\n--- DRAWDOWN ANALYSIS ---")
    for key, value in all_metrics['drawdown'].items():
        logger.info(f"  {key}: {value:.4f}")
    
    logger.info("\n--- TRADE STATISTICS ---")
    for key, value in all_metrics['trades'].items():
        if isinstance(value, (int, float)):
            logger.info(f"  {key}: {value:.2f}")
    
    return all_metrics


def main():
    """Run the Statistical Arbitrage Analytics production pipeline."""
    logger.info(f"Starting SAA pipeline: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Load Data
    logger.info("STEP 1: DATA LOADING")
    logger.info("-" * 70)
    prices = load_data(TICKERS_UNIVERSE, lookback_days=LOOKBACK_COINT)
    
    if prices.empty:
        logger.error("No price data loaded. Exiting.")
        return
    
    logger.info(f"Data loaded: {prices.shape[0]} observations, {prices.shape[1]} assets\n")
    
    # Step 2: Pair Selection
    logger.info("STEP 2: PAIR SELECTION & COINTEGRATION")
    logger.info("-" * 70)
    pairs = analyze_and_select_pairs(prices)
    
    if not pairs:
        logger.error("No cointegrated pairs found. Exiting.")
        return
    
    logger.info()
    
    # Step 3: Strategy & Backtest (for each pair)
    results = {}
    
    for pair_idx, pair_info in enumerate(pairs[:3], 1):  # Top 3 pairs
        logger.info(f"STEP 3.{pair_idx}: STRATEGY GENERATION & BACKTEST - "
                   f"{pair_info['pair'][0]}/{pair_info['pair'][1]}")
        logger.info("-" * 70)
        
        config = BacktestConfig()
        
        # Generate signals
        pair_prices = {
            pair_info['pair'][0]: prices[pair_info['pair'][0]],
            pair_info['pair'][1]: prices[pair_info['pair'][1]]
        }
        
        signals, z_scores = generate_trading_signals(pair_prices, pair_info, config)
        
        # Run backtest
        backtest_result = backtest_pair_strategy(pair_prices, signals, pair_info)
        
        # Detailed analysis
        detailed_metrics = detailed_performance_analysis(backtest_result)
        backtest_result['detailed_metrics'] = detailed_metrics
        
        results[f"Pair_{pair_idx}"] = backtest_result
        
        logger.info()
    
    # Step 4: Summary
    logger.info("STEP 4: SUMMARY & RECOMMENDATIONS")
    logger.info("=" * 70)
    
    logger.info(f"\nAnalyzed {len(pairs)} cointegrated pair(s)")
    logger.info(f"Backtested top {min(3, len(pairs))} pair(s)")
    
    if results:
        best_pair = max(results.items(), 
                       key=lambda x: x[1]['metrics']['sharpe_ratio'])
        logger.info(f"Best Performing Pair: {best_pair[0]} "
                   f"(Sharpe: {best_pair[1]['metrics']['sharpe_ratio']:.2f})")
    
    logger.info("\nResults saved to:", RESULTS_PATH)
    logger.info("\n✓ Analysis Complete!\n")
    
    return results


if __name__ == "__main__":
    results = main()

