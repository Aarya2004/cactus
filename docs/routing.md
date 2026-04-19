# Cactus Routing Framework

Pluggable, policy-based routing for deciding whether to run inference locally
or in the cloud. Built as a Python add-on to the existing engine: opt in by
calling `routed_complete` instead of `cactus_complete`. No C++ changes, no
behavior change for callers that don't opt in.

> **Import paths.** This page uses `src.routing.*` imports to match the
> in-repo Python package layout (see `python/README.md`, which uses
> `from src.cactus import ...`). The public `cactus` namespace shipped by
> the installer re-exports these — once this module is added to the public
> surface, `from cactus.routing import ...` will also work.

## Quick Start

```python
from src.routing import (
    CactusRouter,
    RoutingContext,
    RoutingAction,
    RoutedCompletionHandler,
)
from src.routing.policies import ThresholdPolicy, BatteryAwarePolicy

router = CactusRouter()
router.register(ThresholdPolicy(confidence_threshold=0.7))
router.register(BatteryAwarePolicy(low_battery_threshold=20.0), weight=0.5)

context = RoutingContext(
    query="What is 2+2?",
    confidence=0.85,
    battery_pct=72.0,
    network_quality="fast",
)

result = router.route(context)
print(f"Action: {result.action.value}")  # "local"
```

## Routing Actions

| Action | Description |
|--------|-------------|
| `LOCAL` | Run entirely on-device |
| `CLOUD` | Send query to cloud as-is |
| `CLOUD_PII_STRIP` | Strip PII, then send to cloud |
| `CASCADE` | Run local first, verify with cloud |
| `REFUSE` | Don't answer (too risky or disallowed) |

## Built-in Policies

### ThresholdPolicy

Matches the engine's cloud-handoff gate. Accepts either a fixed threshold or
`None` to defer to the model-specific default the engine uses internally:

```python
from src.routing.policies import ThresholdPolicy

ThresholdPolicy(confidence_threshold=0.7)   # fixed threshold
ThresholdPolicy(confidence_threshold=None)  # defer to model default
```

When `None`, the policy reads
`context.metadata["model_default_confidence_threshold"]` at score time. The
`routed_complete` shim forwards that value from the engine's response, so
threshold behavior stays in lockstep with the engine across models. Falls
back to 0.7 if no model default is available.

### BatteryAwarePolicy

```python
from src.routing.policies import BatteryAwarePolicy

BatteryAwarePolicy(low_battery_threshold=20.0, critical_battery_threshold=5.0)
# battery <= 5%  -> always LOCAL
# battery <= 20% -> prefer LOCAL
```

### LatencyBudgetPolicy

Compares estimated local inference latency and estimated cloud round-trip
latency against the caller's `latency_budget_ms`. Picks the one that fits;
falls back to confidence when both (or neither) fit.

```python
from src.routing.policies import LatencyBudgetPolicy

LatencyBudgetPolicy(local_latency_ms=100)
# offline                        -> LOCAL
# local exceeds budget, cloud OK -> CLOUD
# neither fits                   -> LOCAL (network cost on a failing call is worse)
# both fit                       -> confidence-based
```

### ClinicalPolicy

7-dimension policy for medical applications:

```python
from src.routing.policies import ClinicalPolicy

policy = ClinicalPolicy()

context = RoutingContext(
    query="Can I take ibuprofen?",
    confidence=0.8,
    metadata={
        "clinical_severity": "MAJOR",
        "pii_density": 0.3,
        "consent_tier": "standard",
    },
)
```

Decision logic:

- High confidence + no MAJOR interaction → `LOCAL`
- Low confidence or ambiguous → `CLOUD_PII_STRIP`
- MAJOR interaction + confident → `CASCADE`
- Offline or critical battery → `LOCAL`
- Strict consent + low confidence → `REFUSE`

## Custom Policies

Implement the `RoutingPolicy` protocol:

```python
from src.routing import RoutingPolicy, RoutingContext, RoutingAction

class MyPolicy(RoutingPolicy):
    @property
    def name(self) -> str:
        return "my_policy"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"confidence": context.confidence, "my_score": 0.5}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["confidence"] > 0.8:
            return RoutingAction.LOCAL
        return RoutingAction.CLOUD
```

## Engine Integration (opt-in)

`routed_complete` wraps `cactus_complete` and lets the router own the
local/cloud decision. The engine's internal threshold-based handoff is
disabled on the routed call, so the router's decision is authoritative.

```python
from src.cactus import cactus_complete
from src.routing import routed_complete, CactusRouter
from src.routing.policies import ThresholdPolicy

router = CactusRouter()
router.register(ThresholdPolicy(confidence_threshold=None))  # match model default

def my_cloud_complete(messages_json: str, query: str) -> str:
    # Your cloud call — could be cactus cloud, OpenAI, Anthropic, etc.
    return call_my_cloud_api(messages_json)

result = routed_complete(
    model=model_handle,
    messages_json=messages_json,
    router=router,
    complete_fn=cactus_complete,
    cloud_complete_fn=my_cloud_complete,
)

print(result.action)         # RoutingAction.LOCAL | CLOUD | ...
print(result.response)       # final response text
print(result.engine_stats)   # raw engine telemetry: total_time_ms, tps, tokens, ...
print(result.cloud_payload_mode)  # "raw" | "stripped" | None
```

## RoutedCompletionHandler (standalone)

If you're not driving `cactus_complete` (e.g. a REST service wrapping a
different local model), use `RoutedCompletionHandler`:

```python
from src.routing import RoutedCompletionHandler, PIIProfile

def local_complete(query: str) -> tuple[str, float]:
    return ("Local answer", 0.85)

def cloud_complete(query: str) -> str:
    return "Cloud answer"

handler = RoutedCompletionHandler(
    router=router,
    local_complete=local_complete,
    cloud_complete=cloud_complete,
)

result = handler.complete(
    "John Doe takes lisinopril 10mg",
    pii_profile=PIIProfile(patient_name="John Doe", medications=["lisinopril"]),
)
print(result.action)             # CLOUD_PII_STRIP
print(result.anonymized_query)   # "[PATIENT] takes lisinopril 10mg"
print(result.cloud_payload_mode) # "stripped"
```

## Cloud Payload Mode

Routing decides *where* to run; payload mode decides *what text* to send to
the cloud. They're separate so apps can tighten privacy without changing
routing behavior.

| Action | Default payload |
|--------|-----------------|
| `CLOUD` | `RAW` |
| `CLOUD_PII_STRIP` | `STRIPPED` |
| `CASCADE` | `RAW` (verifier sees the actual query) |

Override per-action when privacy policy requires it:

```python
from src.routing import CloudPayloadMode, RoutingAction

handler = RoutedCompletionHandler(
    router=router,
    local_complete=local_complete,
    cloud_complete=cloud_complete,
    cloud_payload_mode_by_action={
        RoutingAction.CASCADE: CloudPayloadMode.STRIPPED,  # strip even on verification
    },
)
```

`routed_complete` accepts the same `cloud_payload_mode_by_action` argument.
The chosen mode is recorded on the result as `cloud_payload_mode` for
auditability.

## PII Stripping

Best-effort anonymization for cloud fallback. Strips **identity** info and
preserves **medically relevant** info so the cloud model can give useful
answers.

**Stripped** (identity PII):
- Patient name, additional names (family, doctors)
- Fine-grained locations (clinics, hospitals — via `PIIProfile.fine_locations`)
- Street addresses, phone numbers (E.164 + North American), emails, SSNs

**Preserved** (medically relevant):
- Medications, supplements (general drug names)
- Dosages, age, times (critical for medical advice)
- City/state (regional formularies, altitude, climate — too coarse to identify)

```python
from src.routing import PIIStripper, PIIProfile

stripper = PIIStripper()
profile = PIIProfile(
    patient_name="Sarah Johnson",
    medications=["lisinopril", "atorvastatin"],
    supplements=["fish oil", "vitamin D"],
    fine_locations=["St. Michael's Hospital"],
)

text = "Sarah Johnson at St. Michael's Hospital in Toronto, 62 years old, takes lisinopril 10mg at 8am"
anonymized = stripper.strip(text, profile)
# "[PATIENT] at [FACILITY_A] in Toronto, 62 years old, takes lisinopril 10mg at 8am"
```

PII stripping is best-effort. Facilities not listed in the profile and
other identifying details may pass through — treat `STRIPPED` as
defense-in-depth, not a guarantee.

## Signal Providers

Platform signal extraction for routing context:

```python
from src.routing import SignalProvider, default_signals

battery = default_signals.battery_pct()
network = default_signals.network_quality()  # "offline" | "slow" | "fast"

# Custom signals for testing or other platforms
signals = SignalProvider(
    battery_fn=lambda: 42.0,
    network_fn=lambda: "slow",
    latency_fn=lambda: 500,
)
```

Environment variables:

- `CACTUS_OFFLINE_MODE=1` — Force offline routing
- `CACTUS_LATENCY_BUDGET_MS=500` — Set latency budget

## Weighted Ensemble

Register multiple policies with weights. Weights must be positive — zero or
negative values raise `ValueError`, since they'd silently disable a policy's
vote or invert it.

```python
router = CactusRouter()
router.register(ThresholdPolicy(), weight=0.6)
router.register(BatteryAwarePolicy(), weight=0.4)
# Each policy votes; the action with the highest total weight wins.
```

## Compatibility

- **Existing callers**: unchanged. `cactus_complete` keeps its threshold-based
  internal handoff. Routing only runs when you call `routed_complete` or
  drive `RoutedCompletionHandler` yourself.
- **Replicating engine behavior via a router**: use
  `ThresholdPolicy(confidence_threshold=None)` with `routed_complete` — the
  shim forwards the engine's per-model default, matching the engine's three
  step fallback (caller → model default → 0.7). `ThresholdPolicy(0.7)` only
  matches models whose default is 0.7.
