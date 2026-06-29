# ABOUTME: data_as_of provenance for assethold MARKET inputs (workspace-hub#3287 AC#3).
"""Market data-as-of provenance for assethold workflows.

Reproducing a financial answer requires the as-of date of the market inputs it
consumed. assethold's offline portfolio prices carry no intrinsic date, so the
as-of date is a DECLARED convention read (in precedence order) from:

1. ``cfg["portfolio"]["prices_as_of"]`` -- workflow-scoped declaration.
2. ``cfg["Analysis"]["data_as_of"]`` -- engine-scoped cross-workflow convention.
3. ``row["market_data_as_of"]`` -- the registry-row hint.

Fail-SOFT, never silent: when a workflow declares market ``prices`` but no
as-of date is found anywhere, ``provenance.data_as_of`` is ``None`` AND a
warning is emitted so the gap is visible in the envelope.
"""

from __future__ import annotations


def _deep_get(cfg, *keys, default=None):
    cur = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def market_data_as_of(cfg: dict, row: dict | None = None):
    """Return ``(data_as_of, warnings)`` for the market inputs in ``cfg``.

    ``data_as_of`` is the declared as-of date string or ``None``. ``warnings``
    is non-empty only when market ``prices`` exist without any declared date.
    """
    as_of = (
        _deep_get(cfg, "portfolio", "prices_as_of")
        or _deep_get(cfg, "Analysis", "data_as_of")
        or (row or {}).get("market_data_as_of")
    )
    has_market_inputs = bool(_deep_get(cfg, "portfolio", "prices"))
    if has_market_inputs and not as_of:
        return None, [
            "workflow declares market 'prices' but no data_as_of "
            "-> provenance.data_as_of is null"
        ]
    return as_of, []
