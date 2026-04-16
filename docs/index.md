# assethold

Asset analysis toolkit covering equities, real estate, and portfolio management.

See [Architecture](architecture.md) for the module dependency map and data flow.

## Modules

| Module | Description |
|--------|-------------|
| [daily_strategy](api/daily_strategy.md) | Daily trading signal pipeline |
| [fundamentals](api/fundamentals.md) | P/E, P/B, EV/EBITDA screening |
| [risk_metrics](api/risk_metrics.md) | VaR, Sharpe, Beta calculations |
| [signals](api/signals.md) | Realtime data, alerts, trend detection (complements `modules/stocks` batch analysis) |
| [portfolio](api/portfolio.md) | Position tracking, sector allocation |
| [net_lease](api/net_lease.md) | Single-tenant NNN property modeling |
