# Cactus Routing Framework

The routing framework provides pluggable, policy-based routing for deciding whether to run inference locally or in the cloud.

## Quick Start

```python
from cactus.routing import (
    CactusRouter,
    RoutingContext,
    RoutingAction,
    RoutedCompletionHandler,
)
from cactus.routing.policies import ThresholdPolicy, BatteryAwarePolicy

# Create router with policies
router = CactusRouter()
router.register(ThresholdPolicy(confidence_threshold=0.7))
router.register(BatteryAwarePolicy(low_battery_threshold=20.0), weight=0.5)

# Route a query
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

Replicates current Cactus confidence-based routing:

```python
from cactus.routing.policies import ThresholdPolicy

policy = ThresholdPolicy(confidence_threshold=0.7)
# confidence >= 0.7 → LOCAL
# confidence < 0.7 → CLOUD
```

### BatteryAwarePolicy

Prefers local when battery is low:

```python
from cactus.routing.policies import BatteryAwarePolicy

policy = BatteryAwarePolicy(
    low_battery_threshold=20.0,
    critical_battery_threshold=5.0,
)
# battery <= 5% → always LOCAL
# battery <= 20% → prefer LOCAL
```

### LatencyBudgetPolicy

Routes local when network is slow or latency budget is tight:

```python
from cactus.routing.policies import LatencyBudgetPolicy

policy = LatencyBudgetPolicy(local_latency_ms=100)
# offline → LOCAL
# tight budget + slow network → LOCAL
```

### ClinicalPolicy

7-dimension policy for medical applications:

```python
from cactus.routing.policies import ClinicalPolicy

policy = ClinicalPolicy()

context = RoutingContext(
    query="Can I take ibuprofen?",
    confidence=0.8,
    metadata={
        "clinical_severity": "MAJOR",  # NONE, MINOR, MODERATE, MAJOR
        "pii_density": 0.3,
        "consent_tier": "standard",  # "standard" or "strict"
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
from cactus.routing import RoutingPolicy, RoutingContext, RoutingAction

class MyPolicy(RoutingPolicy):
    @property
    def name(self) -> str:
        return "my_policy"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {
            "confidence": context.confidence,
            "my_score": 0.5,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["confidence"] > 0.8:
            return RoutingAction.LOCAL
        return RoutingAction.CLOUD

router = CactusRouter()
router.register(MyPolicy())
```

## Integration Handler

For end-to-end routing with actual completion:

```python
from cactus.routing import RoutedCompletionHandler, PIIProfile

def my_local_complete(query: str) -> tuple[str, float]:
    # Returns (response, confidence)
    return ("Local answer", 0.85)

def my_cloud_complete(query: str) -> str:
    # Returns response
    return "Cloud answer"

handler = RoutedCompletionHandler(
    router=router,
    local_complete=my_local_complete,
    cloud_complete=my_cloud_complete,
)

# With PII stripping
profile = PIIProfile(
    patient_name="John Doe",
    medications=["lisinopril", "aspirin"],
)

result = handler.complete(
    "John Doe takes lisinopril 10mg",
    pii_profile=profile,
)

print(result.action)  # CLOUD_PII_STRIP
print(result.anonymized_query)  # "[PATIENT] takes [DRUG_A] [DOSE]"
```

## PII Stripping

Best-effort anonymization for cloud fallback:

```python
from cactus.routing import PIIStripper, PIIProfile

stripper = PIIStripper()
profile = PIIProfile(
    patient_name="Sarah Johnson",
    medications=["lisinopril", "atorvastatin"],
    supplements=["fish oil", "vitamin D"],
)

text = "Sarah Johnson, 62 years old, takes lisinopril 10mg at 8am"
anonymized = stripper.strip(text, profile)
# "[PATIENT], [AGE], takes [DRUG_A] [DOSE] at [TIME]"
```

**Note:** PII stripping is best-effort. Newly mentioned drugs not in the profile, conditions, or other identifying details may pass through.

## Signal Providers

Platform signal extraction for routing context:

```python
from cactus.routing import SignalProvider, default_signals

# Use defaults (macOS battery/network detection)
battery = default_signals.battery_pct()
network = default_signals.network_quality()  # "offline", "slow", "fast"

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

Register multiple policies with weights:

```python
router = CactusRouter()
router.register(ThresholdPolicy(), weight=0.6)
router.register(BatteryAwarePolicy(), weight=0.4)

# Each policy votes, weighted by its registration weight
# Most common action wins
```

## Backward Compatibility

Using `ThresholdPolicy` with the default threshold (0.7) exactly replicates current Cactus behavior. Apps without a router continue to work unchanged.
