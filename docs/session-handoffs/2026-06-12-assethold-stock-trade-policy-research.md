# 2026-06-12 assethold stock trade-policy research handoff

## Purpose

This handoff captures the research-only session on how `assethold` should evolve from daily Build/Hold/Trim scoring into a stock trade-candidate engine for long-term holders of tickers such as XOM, BRKB/BRK-B, and VOO.

No implementation was performed in this session. No GitHub issue was implemented or closed.

## Session Summary

The user asked to review all `assethold` stock-analysis topics, research open source stock-analysis libraries, and identify trade types that can take advantage of periodic cycles for existing stock holders.

Inspection found that `assethold` already has a mature base for portfolio-aware signals:

- Daily strategy reports produce Build/Hold/Trim recommendations and explain the weighted signal model in `README.md`.
- `docs/architecture.md` maps the stock-analysis split between `analysis/daily_strategy/`, `signals/`, and `modules/stocks/`.
- `config/targets.yaml` encodes target allocations, DCA cadence, trim rules, and legacy position handling.
- `config/daily_strategy.yaml` currently treats BRKB and VOO as `managed`, while XOM and RIG are `trim_only`.
- `src/assethold/options/covered_call.py` already contains a covered-call analyzer, but it does not yet have full options Greeks, assignment-risk policy, or tax-aware sell constraints.
- `docs/domain/stocks/tradingview/PRD.md` captures the current adverse-event / RSI-oversold recovery hypothesis.

## Existing Topics To Preserve

The relevant issue-plan backlog is already represented in `docs/plans/`:

- `2026-05-05-issue-5-breakout-trends-backtesting.md` - deterministic breakout criteria and trend-change history.
- `2026-05-05-issue-7-portfolio-value.md` - cash, stocks, dividends, FD/SPY comparators.
- `2026-05-05-issue-17-dividend-yield-forecasting.md` - DDM models.
- `2026-05-05-issue-18-fama-french-factor-model.md` - factor attribution.
- `2026-05-05-issue-21-portfolio-dashboard-allocation-tracking.md` - allocation monitor, DCA tracker, daily report.
- `2026-05-05-issue-23-whatsapp-trade-signals.md` - trade signal delivery.
- `2026-05-05-issue-24-market-disruption-monitor.md` - intraday disruption alerts.
- `2026-05-05-issue-25-tax-lot-aging-report.md` - long-term-gain-aware trim policy.
- `2026-05-05-issue-26-dividend-reinvestment-ex-date-calendar.md` - ex-date and dividend-income calendar.
- `2026-05-05-issue-27-portfolio-benchmark-vs-spy.md` - TWR, Sharpe, drawdown, benchmark comparison.
- `2026-05-05-issue-28-portfolio-future-outlook-monte-carlo.md` - probabilistic forward outlook.
- `2026-05-05-issue-34-realtime-stock-price-feeds.md` and `2026-05-05-issue-40-pre-market-after-hours-bell-buffer.md` - freshness / intraday feed behavior.
- `2026-05-05-issue-43-wire-insider-tracker.md` - insider tracker integration.

## Library Research Notes

Current library recommendation by role:

- `vectorbt` - best fit for high-volume parameter sweeps over RSI, breakout, rebalance, volatility, and cycle rules. Official docs describe a pandas/NumPy backtesting model designed to test many strategies quickly: https://vectorbt.dev/
- `backtesting.py` - best fit for readable single-strategy prototypes before promoting a rule to vectorized research. Official docs: https://kernc.github.io/backtesting.py/
- QuantConnect LEAN - best fit only if `assethold` later needs realistic broker/live-trading simulation. It is an open-source backtesting and live-trading engine: https://www.quantconnect.com/docs/v2/lean-engine/getting-started
- PyPortfolioOpt - best fit for allocation optimization experiments such as mean-variance, Black-Litterman, shrinkage, and HRP: https://pyportfolioopt.readthedocs.io/
- Existing `ta` dependency can stay for current indicators; evaluate TA-Lib only if candlestick patterns or wider indicator coverage become necessary.
- Use `QuantLib` or `py_vollib` if covered calls / cash-secured puts become first-class recommendations requiring Greeks and implied-volatility checks.
- Use `statsmodels`, `scipy.signal`, and possibly `arch` for cycle/regime detection instead of treating RSI alone as a cycle model.

## Trade Types To Model

The next design should distinguish candidate trades by intent:

- Rebalance buys and trims: deploy new money into underweight VOO/BRKB; trim overweight XOM/RIG only when target bands and tax rules allow.
- Mean-reversion buys: buy strong-fundamental names only after an adverse-event / oversold / recovery-confirmation setup.
- Covered calls: sell calls against overweight or overbought positions when assignment is acceptable; natural fit for XOM/RIG-style trim candidates, less natural for core VOO/BRKB unless tax and target policy allow assignment.
- Cash-secured puts: sell puts only at prices where the portfolio wants more shares anyway; more suitable for planned VOO/BRKB accumulation than for speculative yield.
- Collars/protective puts: apply to concentrated gains where downside protection is desired without a full sale.
- Tax-aware trims: sell only long-term lots by default; short-term lots should be downgraded to "wait" unless risk rules override.
- Dividend/DCA timing: ex-date information should only advance an already-planned buy, not create standalone dividend-capture trades.
- Regime/cycle trades: energy holdings like XOM should include oil/VIX/sector regime filters; VOO should mostly use DCA/rebalance bands; BRKB should behave like a core compounder with limited tactical churn.

## Recommended Next Artifact

File a new GitHub issue for a `trade_policy` layer before implementation. Proposed title:

`Trade Candidate Policy Engine for portfolio-aware stock and options actions`

Suggested scope:

```text
signals + allocation + tax lots + options chain + dividend calendar + regime state
  -> candidate action
```

Candidate actions:

- `BUY`
- `TRIM`
- `SELL_COVERED_CALL`
- `SELL_CASH_SECURED_PUT`
- `COLLAR`
- `HOLD`

Each recommendation should include:

- ticker and display ticker alias handling, especially BRKB -> BRK-B
- action type
- confidence / priority
- rationale lines
- violated or satisfied constraints
- tax-lot warning
- options liquidity / Greeks warning when relevant
- expected holding-period effect
- backtest evidence link or "not backtested" status

## Suggested Skills For Next Session

- `to-issues` if converting this handoff into GitHub implementation issues.
- `request-refactor-plan` if designing the trade-policy layer across existing modules.
- `tdd` for any implementation work.
- `review` for branch or PR review after implementation.
- `github:yeet` only after an approved issue/plan and implementation are complete.

## Repo And Operational State At Handoff Creation

- Repo: `/mnt/local-analysis/assethold`
- Branch: `main`
- Remote: `origin https://github.com/samdansk2/assethold`
- State before this handoff file: clean working tree, `main...origin/main`.
- Pre-existing stash: `stash@{Wed Mar 25 19:10:11 2026}: autostash`. It predates this session and was left untouched.
- Parallel process scan showed long-running Codex/Claude desktop processes on the machine, but no task-specific `assethold` process was identified.
- No tests were run because this was a research/documentation closeout, not code implementation.

## Closeout Caveats

This handoff is product and engineering research, not financial advice. Any future trade-recommendation implementation should show candidates and constraints, not place trades automatically.

Future implementation must follow the repo gates: GitHub issue, issue plan, adversarial review, user approval, TDD implementation, code/artifact review, then closeout.
