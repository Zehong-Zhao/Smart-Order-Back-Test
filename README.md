# Smart Order Router (Cont & Kukanov) Back Test

This project implements a static smart order router (SOR) and compares its performance against baseline strategies including Best Ask, TWAP, and VWAP, using Level 1 order book data. The implementation is based on the cost model from Cont & Kukanov (2013).

## Files

- `l1_day.csv` — L1 market data used as input.
- `main.py` — Core implementation of the allocator, baselines, and backtesting.
- `backtest_results.json` — Output file storing total costs and average prices from each strategy.

## How It Works

### 1. Data Preprocessing

The `dataProcess()` function loads and cleans the order book data:
- Parses timestamps
- Ensures numeric consistency
- Groups snapshots by `ts_event` and `publisher_id`

### 2. Order Execution Strategies

- **Static Allocator** (`allocate`):
  - Follows Cont-Kukanov pseudocode
  - Optimizes expected cost under penalties for overfill, underfill, and queue risk

- **Baselines**:
  - `best_ask_baseline`: Always buys from the venue with the best ask price
  - `twap_baseline`: Splits the total order evenly over time buckets (e.g., 60 seconds)
  - `vwap_baseline`: Allocates shares across venues proportionally to liquidity

### 3. Backtesting

The `backtest()` function simulates filling the target order (default: 5000 shares) using the allocator or a baseline strategy.

### 4. Parameter Optimization

The `parameter_optimization()` function performs random search over the cost model parameters:
- `lambda_over`: penalty for overfilling
- `lambda_under`: penalty for underfilling
- `theta_queue`: penalty for mis-execution risk

### 5. Output

Results from each strategy are written to `backtest_results.json`, including:
- Total execution cost
- Average fill price
- Optimized penalty parameters

## Configuration

- Modify `order_size`, `bucket_window`, or random search `iteration` count in `main()`.
- Data path for CSV file is passed into `dataProcess()`.

## Potential Improvement
Currently the allocation algorithm output any allocation only if the size at any given time stemp exceeds the order size. Need to rewrite allocation algorithm for smoother allocation.

Example Output

{
  "optimal_parameters": {"lambda_over": 0.012, "lambda_under": 0.344, "theta_queue": 0.003},
  "result_from_optimal_parameters": {"total_cost": 50034.2, "average_price": 10.0068},
  "best_ask_baseline": {"total_cost": 50079.5, "average_price": 10.0159},
  "twap_baseline": {"total_cost": 50120.0, "average_price": 10.024},
  "vwap_baseline": {"total_cost": 50050.5, "average_price": 10.0101}
}
Notes

Current implementation assumes a single venue (NASDAQ, publisher_id = 2).
All costs are computed in simple dollar terms, without slippage or latency effects.
Share chunks are executed in increments of 100 shares.