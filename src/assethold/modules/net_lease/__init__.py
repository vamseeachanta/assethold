"""net_lease — Single-tenant net lease (NN/NNN) property models and analysis."""

from assethold.modules.net_lease.analysis import (
    CapRateScenario,
    ExpenseEstimates,
    ExpirationEvent,
    LeaseExpirationTimeline,
    LeaseInput,
    LeaseStructureResult,
    NNNvsModifiedGrossComparison,
    YearlyRentAtRisk,
    cap_rate_sensitivity,
    compare_nnn_vs_modified_gross,
    lease_expiration_timeline,
)
from assethold.modules.net_lease.net_lease_model import (
    LeaseType,
    NNLeaseDemographics,
    NNLeaseFinancials,
    NNLeaseOwnerPnL,
    NNLeaseProperty,
    NNLeaseRenewalOption,
    NNLeaseSalesHistory,
    NNLeaseTenant,
)

__all__ = [
    # Model classes
    "LeaseType",
    "NNLeaseDemographics",
    "NNLeaseFinancials",
    "NNLeaseOwnerPnL",
    "NNLeaseProperty",
    "NNLeaseRenewalOption",
    "NNLeaseSalesHistory",
    "NNLeaseTenant",
    # Analysis dataclasses
    "CapRateScenario",
    "ExpenseEstimates",
    "ExpirationEvent",
    "LeaseExpirationTimeline",
    "LeaseInput",
    "LeaseStructureResult",
    "NNNvsModifiedGrossComparison",
    "YearlyRentAtRisk",
    # Analysis functions
    "cap_rate_sensitivity",
    "compare_nnn_vs_modified_gross",
    "lease_expiration_timeline",
]
