"""
QUICK START EXAMPLES
Statistical Arbitrage Analytics (SAA)

This document provides quick copy-paste examples to get started with the upgraded
Statistical Arbitrage Analytics system.

===============================================================================
                         EXAMPLE 1: BASIC SETUP
===============================================================================

# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Verify installation
python -c "from config import CAPITAL; print(f'Config loaded: Initial capital = ${CAPITAL:,}')"

# Step 3: Run main pipeline
python main.py


===============================================================================
                   EXAMPLE 2: COINTEGRATION TESTING
===============================================================================

import pandas as pd
import numpy as np
from src.statistics import CointegratedPairAnalyzer

# Load data
prices_x = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
prices_y = pd.read_csv('data/raw/MSFT.csv', index_col='Date', parse_dates=True)['Close']

# Initialize analyzer
analyzer = CointegratedPairAnalyzer()

# Test 1: ADF (Augmented Dickey-Fuller) - check if series are I(1)
adf_stat, adf_pval, n_lags, n_obs = analyzer.adf_test(prices_x)
print(f"AAPL - ADF Statistic: {adf_stat:.4f}, P-value: {adf_pval:.4f}")
print(f"If p-value > 0.05: Series is I(1) (non-stationary) ✓")

# Test 2: KPSS - alternative stationarity test
kpss_stat, kpss_pval = analyzer.kpss_test(prices_x)
print(f"AAPL - KPSS Statistic: {kpss_stat:.4f}, P-value: {kpss_pval:.4f}")
print(f"If p-value < 0.05: Series is I(1) (non-stationary) ✓")

# Test 3: Engle-Granger Cointegration
eg_stat, eg_pval, beta = analyzer.engle_granger_test(prices_x.values, prices_y.values)
print(f"\nEngle-Granger Cointegration Test:")
print(f"Test Statistic: {eg_stat:.4f}")
print(f"P-value: {eg_pval:.6f}")
print(f"Hedge Ratio: {beta[1]:.4f}")
print(f"Cointegrated: {'YES' if eg_pval < 0.05 else 'NO'}")

# Test 4: Check if cointegrated
is_coint = analyzer.is_cointegrated(prices_x.values, prices_y.values, threshold=0.05)
print(f"\nQuick Check - Are AAPL and MSFT cointegrated? {is_coint}")

# Calculate spread
spread = prices_y - beta[1] * prices_x
print(f"Spread Mean: {spread.mean():.4f}, Std: {spread.std():.4f}")


===============================================================================
                    EXAMPLE 3: MEAN REVERSION ANALYSIS
===============================================================================

import pandas as pd
from src.statistics import MeanReversionAnalyzer, ZScoreCalculator

# Load spread (from previous example or calculate it)
prices_x = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
prices_y = pd.read_csv('data/raw/MSFT.csv', index_col='Date', parse_dates=True)['Close']
hedge_ratio = 0.8234  # From cointegration test
spread = prices_y - hedge_ratio * prices_x

# Calculate half-life of mean reversion
halflife = MeanReversionAnalyzer.half_life_ar1(spread)
print(f"Half-life of mean reversion: {halflife:.1f} days")
print(f"Interpretation: Spread reverts to mean in ~{halflife:.1f} days on average")

# Analyze autocorrelation decay
acf, mr_strength = MeanReversionAnalyzer.autocorrelation_decay(spread, max_lags=50)
print(f"\nMean Reversion Strength: {mr_strength:.4f}")
print(f"(Higher = stronger mean reversion, better for trading)")

# Check if mean reversion is within trading range
if 5 <= halflife <= 252:
    print(f"✓ Valid for trading (halflife between 5-252 days)")
else:
    print(f"✗ Not suitable for trading (halflife outside 5-252 day range)")


===============================================================================
                   EXAMPLE 4: SIGNAL GENERATION
===============================================================================

import pandas as pd
import numpy as np
from src.strategy import PairTradingStrategy
from config import Z_ENTRY, Z_EXIT, ROLLING_WINDOW_ZSCORE

# Load data and calculate spread (as in Example 3)
prices_x = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
prices_y = pd.read_csv('data/raw/MSFT.csv', index_col='Date', parse_dates=True)['Close']
hedge_ratio = 0.8234
spread = prices_y - hedge_ratio * prices_x

# Initialize strategy
strategy = PairTradingStrategy(z_entry=Z_ENTRY, z_exit=Z_EXIT)

# Generate signals (basic)
signals, z_scores = strategy.generate_signals(
    spread,
    entry=Z_ENTRY,
    exit=Z_EXIT,
    rolling_window=ROLLING_WINDOW_ZSCORE,
    use_exponential=True
)

# Display results
print(f"Signal Summary:")
print(f"  Long positions (1):  {(signals == 1).sum()} days")
print(f"  Short positions (-1): {(signals == -1).sum()} days")
print(f"  Flat positions (0):  {(signals == 0).sum()} days")

# Show recent signals
print(f"\nRecent Signals (last 10 days):")
print(f"{'Date':<12} {'Z-Score':<10} {'Signal':<8}")
print("-" * 30)
for date, z, sig in zip(spread.index[-10:], z_scores[-10:], signals[-10:]):
    sig_label = {1: 'LONG', -1: 'SHORT', 0: 'FLAT'}[int(sig)]
    print(f"{date.date()} {z:>8.2f} {sig_label:>8}")


===============================================================================
                   EXAMPLE 5: VOLATILITY-ADJUSTED SIGNALS
===============================================================================

import pandas as pd
from src.strategy import PairTradingStrategy

# Setup (using previous examples)
prices_x = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
prices_y = pd.read_csv('data/raw/MSFT.csv', index_col='Date', parse_dates=True)['Close']
hedge_ratio = 0.8234
spread = prices_y - hedge_ratio * prices_x

strategy = PairTradingStrategy()
signals, z_scores = strategy.generate_signals(spread, rolling_window=60)

# Apply volatility adjustment
vol_adjusted_signals = strategy.volatility_adjusted_signals(spread, signals, vol_window=30)

print("Signal Adjustment by Volatility:")
print(f"{'Date':<12} {'Vol Regime':<15} {'Base Signal':<12} {'Adj Signal':<12}")
print("-" * 51)

for i in range(-20, 0):
    date = spread.index[i]
    vol = spread.iloc[i:].std() if i < 0 else spread.std()
    vol_ma = spread.rolling(60).std().iloc[i]
    vol_ratio = vol / vol_ma if vol_ma > 0 else 1.0
    
    regime = "HIGH VOL (0.5x)" if vol_ratio > 1.5 else "NORMAL (1.0x)" if vol_ratio > 0.75 else "LOW VOL (1.2x)"
    base = signals.iloc[i]
    adj = vol_adjusted_signals.iloc[i]
    
    print(f"{date.date()} {regime:<15} {base:>5.1f}       {adj:>5.1f}")


===============================================================================
                    EXAMPLE 6: REGIME DETECTION
===============================================================================

import pandas as pd
from src.regime_detection import RegimeDetector, VolatilityClusteringDetector

# Load price data
prices = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
returns = prices.pct_change().dropna()

# Method 1: K-Means Clustering (fast, simple)
regimes_kmeans = RegimeDetector.detect_regimes_kmeans(
    returns, 
    n_regimes=2,
    window=20,
    features='volatility'
)
print("K-Means Regimes:")
print(f"  Regime 0 (Low Vol): {(regimes_kmeans == 0).sum()} days")
print(f"  Regime 1 (High Vol): {(regimes_kmeans == 1).sum()} days")

# Method 2: Mahalanobis Distance
regimes_maha = RegimeDetector.detect_regimes_mahalanobis(
    returns,
    n_regimes=2,
    window=20,
    threshold_std=2.0
)

# Method 3: Hidden Markov Models (if hmmlearn installed)
try:
    regimes_hmm = RegimeDetector.detect_regimes_hmm(returns, n_regimes=2)
    print("\n✓ HMM Regimes available")
except:
    print("\n✗ HMM not available (hmmlearn not installed)")
    regimes_hmm = regimes_kmeans

# Volatility Clustering Analysis
vol_persistence = VolatilityClusteringDetector.volatility_persistence(returns, lags=20)
print(f"\nVolatility Persistence: {vol_persistence:.4f}")
print(f"  (0.0 = no clustering, 1.0 = extreme clustering)")

# Extreme Volatility Periods
extreme_vol = VolatilityClusteringDetector.extreme_volatility_periods(
    returns,
    window=20,
    threshold_std=1.5
)
print(f"Extreme Volatility Periods: {extreme_vol.sum()} days")


===============================================================================
                    EXAMPLE 7: BACKTESTING A PAIR
===============================================================================

import pandas as pd
from src.backtest import BacktestEngine, BacktestConfig
from src.strategy import PairTradingStrategy
from config import Z_ENTRY, Z_EXIT, CAPITAL

# Load data and setup
prices_x = pd.read_csv('data/raw/AAPL.csv', index_col='Date', parse_dates=True)['Close']
prices_y = pd.read_csv('data/raw/MSFT.csv', index_col='Date', parse_dates=True)['Close']
hedge_ratio = 0.8234

# Calculate spread
spread = prices_y - hedge_ratio * prices_x

# Generate signals
strategy = PairTradingStrategy(z_entry=Z_ENTRY, z_exit=Z_EXIT)
signals, _ = strategy.generate_signals(spread, rolling_window=60)

# Configure and run backtest
config = BacktestConfig(
    initial_capital=CAPITAL,
    transaction_cost_bps=5,
    slippage_bps=2
)

engine = BacktestEngine(config)
equity_curve, returns, metrics = engine.backtest_spread_based(
    spread=spread,
    signals=signals,
    price_x=prices_x,
    price_y=prices_y,
    hedge_ratio=hedge_ratio,
    capital=CAPITAL
)

# Display results
print("BACKTEST RESULTS")
print("=" * 50)
print(f"Period: {equity_curve.index[0].date()} to {equity_curve.index[-1].date()}")
print(f"Initial Capital: ${CAPITAL:,.0f}")
print(f"Final Equity: ${equity_curve.iloc[-1]:,.0f}")
print(f"\nRETURNS:")
print(f"  Total Return: {metrics['total_return']:.2%}")
print(f"  Annual Return: {metrics['annual_return']:.2%}")
print(f"\nRISK:")
print(f"  Annual Volatility: {metrics['annual_volatility']:.2%}")
print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
print(f"  Max DD Duration: {metrics['max_drawdown_duration']} days")
print(f"\nRISK-ADJUSTED:")
print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"  Win Rate: {metrics['win_rate']:.2%}")
print(f"  Profit Factor: {metrics['profit_factor']:.2f}")


===============================================================================
                  EXAMPLE 8: COMPREHENSIVE METRICS
===============================================================================

import pandas as pd
from src.metrics import calculate_all_metrics
from src.backtest import BacktestEngine, BacktestConfig

# Use equity_curve and returns from Example 7 (backtesting)
# ... (setup from Example 7) ...

equity_curve, returns, _ = engine.backtest_spread_based(...)

# Calculate all metrics at once
all_metrics = calculate_all_metrics(returns, equity_curve)

# Performance Metrics
print("PERFORMANCE METRICS")
for key, value in all_metrics['performance'].items():
    if isinstance(value, float):
        print(f"  {key}: {value:.4f}")

# Volatility Metrics
print("\nVOLATILITY METRICS")
for key, value in all_metrics['volatility'].items():
    if isinstance(value, float):
        print(f"  {key}: {value:.4f}")

# Risk-Adjusted Returns
print("\nRISK-ADJUSTED RETURNS")
for key, value in all_metrics['risk_adjusted'].items():
    print(f"  {key}: {value:.4f}")

# Drawdown Analysis
print("\nDRAWDOWN ANALYSIS")
for key, value in all_metrics['drawdown'].items():
    print(f"  {key}: {value:.4f}")

# Trade Statistics
print("\nTRADE STATISTICS")
for key, value in all_metrics['trades'].items():
    if isinstance(value, (int, float)):
        print(f"  {key}: {value:.2f}")

# Risk Metrics
print("\nRISK METRICS")
for key, value in all_metrics['risk'].items():
    print(f"  {key}: {value:.4f}")


===============================================================================
                 EXAMPLE 9: CONFIGURING PARAMETERS
===============================================================================

# Edit config.py to customize ALL parameters

from config import (
    CAPITAL,                    # Initial capital
    Z_ENTRY, Z_EXIT,           # Signal thresholds
    COINT_PVALUE_THRESHOLD,    # Cointegration significance
    MIN_CORRELATION,           # Pair correlation filter
    ROLLING_WINDOW_ZSCORE,     # Z-score window
    MAX_POSITION_SIZE,         # Position sizing
    TRANSACTION_COST_BPS,      # Transaction costs
    REGIME_DETECTION_METHOD,   # Regime detection: 'kmeans', 'hmm', 'mahalanobis'
    N_REGIMES,                 # Number of regimes
    TRAIN_WINDOW,              # Walk-forward training
    TEST_WINDOW                # Walk-forward testing
)

# Change parameters
import config

# Override parameters for a specific run
config.Z_ENTRY = 2.5  # More conservative entries
config.Z_EXIT = 0.3   # Tighter exits
config.TRANSACTION_COST_BPS = 3  # Lower costs

# Now run with new parameters
from main import main
results = main()

# To make permanent changes, edit config.py directly


===============================================================================
                   EXAMPLE 10: COMPLETE PIPELINE
===============================================================================

# Run the complete statistical arbitrage pipeline in one script

import pandas as pd
from config import (
    CAPITAL, TRADING_DAYS, Z_ENTRY, Z_EXIT, COINT_PVALUE_THRESHOLD,
    DATA_PATH, MIN_CORRELATION, LOOKBACK_COINT, ROLLING_WINDOW_ZSCORE
)
from src.statistics import CointegratedPairAnalyzer, MeanReversionAnalyzer
from src.strategy import PairTradingStrategy
from src.backtest import BacktestEngine, BacktestConfig
from src.metrics import calculate_all_metrics
from src.regime_detection import RegimeDetector
import os

# STEP 1: Load Data
print("STEP 1: Loading Data...")
tickers = ['AAPL', 'MSFT', 'GOOGL']
prices = {}
for ticker in tickers:
    path = os.path.join(DATA_PATH, f"{ticker}.csv")
    if os.path.exists(path):
        prices[ticker] = pd.read_csv(path, index_col='Date', parse_dates=True)['Close']
        print(f"  {ticker}: {len(prices[ticker])} observations")

price_df = pd.DataFrame(prices)

# STEP 2: Find Cointegrated Pairs
print("\nSTEP 2: Finding Cointegrated Pairs...")
analyzer = CointegratedPairAnalyzer()
viable_pairs = []

for i, ticker1 in enumerate(tickers):
    for ticker2 in tickers[i+1:]:
        x = price_df[ticker1].values
        y = price_df[ticker2].values
        
        corr = np.corrcoef(x, y)[0, 1]
        if corr < MIN_CORRELATION or corr > 0.95:
            continue
        
        try:
            _, pval, beta = analyzer.engle_granger_test(x, y)
            if pval < COINT_PVALUE_THRESHOLD:
                spread = y - beta[1] * x
                hl = MeanReversionAnalyzer.half_life_ar1(spread)
                
                if 5 <= hl <= 252:
                    viable_pairs.append({
                        'pair': (ticker1, ticker2),
                        'pval': pval,
                        'hedge_ratio': beta[1],
                        'halflife': hl
                    })
                    print(f"  ✓ {ticker1}-{ticker2}: pval={pval:.4f}, HL={hl:.1f}d")
        except:
            continue

if not viable_pairs:
    print("  No cointegrated pairs found!")
    exit()

# STEP 3: Backtest Top Pair
print(f"\nSTEP 3: Backtesting {viable_pairs[0]['pair'][0]}/{viable_pairs[0]['pair'][1]}...")

pair = viable_pairs[0]
t1, t2 = pair['pair']
x = price_df[t1]
y = price_df[t2]
spread = y - pair['hedge_ratio'] * x

# Generate signals
strategy = PairTradingStrategy(z_entry=Z_ENTRY, z_exit=Z_EXIT)
signals, z_scores = strategy.generate_signals(spread, rolling_window=ROLLING_WINDOW_ZSCORE)

# Backtest
config = BacktestConfig(initial_capital=CAPITAL, transaction_cost_bps=5)
engine = BacktestEngine(config)
equity, returns, metrics = engine.backtest_spread_based(
    spread, signals, x, y, pair['hedge_ratio']
)

# STEP 4: Comprehensive Analysis
print("\nSTEP 4: Performance Analysis...")
all_metrics = calculate_all_metrics(returns, equity)

print(f"\nFINAL RESULTS:")
print(f"  Total Return: {all_metrics['performance']['total_return']:.2%}")
print(f"  Sharpe Ratio: {all_metrics['risk_adjusted']['sharpe_ratio']:.2f}")
print(f"  Max Drawdown: {all_metrics['drawdown']['max_drawdown']:.2%}")
print(f"  Win Rate: {all_metrics['trades']['win_rate']:.2%}")
print(f"  Profit Factor: {all_metrics['trades']['profit_factor']:.2f}")

print("\n✓ Pipeline Complete!")


===============================================================================
                         COMMON QUESTIONS
===============================================================================

Q1: How do I load my own data?
A: Place CSV files in data/raw/ folder with format:
   Date,Open,High,Low,Close,Adj Close,Volume
   The code loads the 'Close' column automatically

Q2: Can I test more pairs?
A: Yes, add tickers to TICKERS_UNIVERSE in config.py
   Increase N_REGIMES or add more regime detection methods

Q3: How do I customize signal entry/exit?
A: Change Z_ENTRY and Z_EXIT in config.py
   Or pass different values to PairTradingStrategy()

Q4: What if cointegration test fails?
A: Check that prices are I(1) not I(0)
   Try different pairs or longer lookback period

Q5: How do I validate without look-ahead bias?
A: Use WalkForwardOptimizer - splits data into train/test windows

Q6: Can I use different regime methods?
A: Yes, change REGIME_DETECTION_METHOD in config.py
   Options: 'kmeans', 'hmm', 'mahalanobis'

Q7: How do I adjust position size?
A: Edit volatility_adjusted_signals() method
   Or override regime_parameters() for regime-based sizing

Q8: What are good parameter values?
A: See docs/ folder or academic literature
   Start with defaults and tune based on backtest results

===============================================================================
"""
