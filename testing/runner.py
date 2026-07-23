#!/usr/bin/env python3
"""
Unified runner for strategy-engine backtesting and paper testing.

Usage:
    python testing/runner.py --mode backtest --strategy strategy_v1_3 --symbol FARTCOIN --start 2026-07-10 --end 2026-07-17
    python testing/runner.py --mode paper    --strategy strategy_v1_3 --symbol FARTCOIN

Modes:
- backtest: historical simulation (isolated store, no live orders)
- paper:    forward-testing with dry_run=True (no real capital)

This is the Z7 unified entrypoint that wraps backtests/runner.run_backtest
so both testing surfaces share one CLI.
"""

import argparse
import sys
import os

# Ensure project root is importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Strategy-engine unified test runner")
    parser.add_argument("--mode", choices=["paper", "backtest"], required=True,
                        help="paper = forward-test (dry_run); backtest = historical sim")
    parser.add_argument("--strategy", required=True, help="Strategy id (e.g. strategy_v1_3)")
    parser.add_argument("--symbol", required=True, help="Token symbol (e.g. FARTCOIN)")
    parser.add_argument("--start", help="Backtest start date YYYY-MM-DD")
    parser.add_argument("--end", help="Backtest end date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe (5m/15m/30m/1h/3h/1d)")
    parser.add_argument("--days", type=int, default=7, help="Backtest window in days (if no start/end)")
    parser.add_argument("--leverage", type=int, default=5, help="Leverage")
    parser.add_argument("--balance", type=float, default=100.0, help="Start balance (USDC)")
    parser.add_argument("--dry-run", action="store_true", help="Force dry_run (paper) mode")
    args = parser.parse_args()

    # Validate strategy exists via the engine registry (single source of truth)
    try:
        from engine.registry import get_strategy
        if get_strategy(args.strategy) is None:
            raise ValueError(f"strategy '{args.strategy}' not registered")
    except Exception as e:
        print(f"ERROR: strategy '{args.strategy}' not found: {e}")
        sys.exit(1)

    dry_run = args.dry_run or (args.mode == "paper")
    print(f"=== Z7 unified runner ===")
    print(f"mode={args.mode} strategy={args.strategy} symbol={args.symbol} "
          f"tf={args.timeframe} dry_run={dry_run}")

    try:
        from backtests.runner import run_backtest
    except ImportError as e:
        print(f"ERROR: cannot import backtests.runner: {e}")
        sys.exit(1)

    try:
        result = run_backtest(
            instance_slug=f"bt-{args.symbol.lower()}-{args.strategy}",
            token=args.symbol,
            strategy_id=args.strategy,
            timeframe=args.timeframe,
            mode="backtest",
            profile="conservative",
            days=args.days,
            leverage=args.leverage,
            initial_capital=args.balance,
        )
    except Exception as e:
        print(f"ERROR during backtest: {e}")
        sys.exit(1)

    if result is None:
        print("⚠️ run_backtest returned None (no data or no trades)")
        sys.exit(0)

    # Report
    summary = getattr(result, "to_dict", lambda: vars(result))()
    final = summary.get("final_capital", summary.get("initial_capital", "?"))
    ret = summary.get("total_return_pct", "?")
    trades = summary.get("total_trades", "?")
    print(f"✅ Done — final_capital={final} return%={ret} trades={trades}")


if __name__ == "__main__":
    main()
