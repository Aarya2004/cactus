"""Wire CactusRouter into the engine completion flow.

The engine (``cactus_complete``) has its own threshold-gated cloud-handoff path
driven by ``options.confidence_threshold``. When routing is enabled, we want
the router — not the engine — to own the handoff decision, so this shim:

1. Overrides the caller's options with a floor-zero threshold so the engine
   never triggers its internal handoff.
2. Calls the engine and parses its JSON result.
3. Forwards the engine's ``confidence`` and model-default threshold into a
   ``RoutingContext`` so policies can vote.
4. Dispatches LOCAL / CLOUD / CLOUD_PII_STRIP / CASCADE / REFUSE per the
   router's decision, invoking the caller-supplied cloud function when needed.

This is opt-in: callers who don't import this module keep the current
threshold-based engine behavior unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from .actions import RoutingAction
from .context import RoutingContext
from .integration import CloudPayloadMode, DEFAULT_CLOUD_PAYLOAD_MODE
from .pii import PIIProfile, PIIStripper
from .policy import PolicyResult
from .router import CactusRouter
from .signals import SignalProvider, default_signals

EngineCompleteFn = Callable[..., str]
CloudCompleteFn = Callable[[str, str], str]

_ENGINE_HANDOFF_DISABLED_THRESHOLD = 0.0


@dataclass
class RoutedEngineCompletion:
    """Result of a router-gated engine completion call.

    ``engine_stats`` carries the raw metrics the engine returned (time_to_first
    _token_ms, total_time_ms, prefill_tps, decode_tps, ram_usage_mb, token
    counts, confidence) so callers can log / compare routes without re-parsing
    the engine JSON.
    """

    response: str
    action: RoutingAction
    policy_name: str
    scores: dict[str, float]
    engine_stats: dict[str, Any]
    reason: Optional[str] = None
    anonymized_query: Optional[str] = None
    cloud_payload_mode: Optional[str] = None
    function_calls: list[str] = field(default_factory=list)
    thinking: Optional[str] = None


def _merge_options(
    options_json: Optional[str], overrides: Mapping[str, Any]
) -> str:
    if options_json:
        try:
            base = json.loads(options_json)
            if not isinstance(base, dict):
                base = {}
        except json.JSONDecodeError:
            base = {}
    else:
        base = {}
    base.update(overrides)
    return json.dumps(base)


def _extract_query(messages_json: str) -> str:
    """Best-effort pull of the most recent user message for PII stripping.

    Falls back to an empty string if the shape is unexpected — the router still
    runs, just without a query payload to strip.
    """
    try:
        msgs = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(msgs, list):
        return ""
    for msg in reversed(msgs):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
    return ""


def _payload_for(
    action: RoutingAction,
    query: str,
    anonymized: str,
    payload_modes: Mapping[RoutingAction, CloudPayloadMode],
) -> tuple[str, CloudPayloadMode]:
    mode = payload_modes.get(action, CloudPayloadMode.RAW)
    return (query if mode == CloudPayloadMode.RAW else anonymized), mode


def routed_complete(
    model: int,
    messages_json: str,
    router: CactusRouter,
    complete_fn: EngineCompleteFn,
    options_json: Optional[str] = None,
    tools_json: Optional[str] = None,
    callback: Optional[Callable[[str, int], None]] = None,
    pcm_data: Optional[list[int]] = None,
    cloud_complete_fn: Optional[CloudCompleteFn] = None,
    pii_profile: Optional[PIIProfile] = None,
    pii_stripper: Optional[PIIStripper] = None,
    signal_provider: Optional[SignalProvider] = None,
    routing_metadata: Optional[dict[str, Any]] = None,
    cloud_payload_mode_by_action: Optional[
        Mapping[RoutingAction, CloudPayloadMode]
    ] = None,
) -> RoutedEngineCompletion:
    """Run ``complete_fn`` with router-gated cloud handoff.

    ``complete_fn`` is usually ``src.cactus.cactus_complete`` but is injectable
    so tests can run without the native library. Signature matches
    ``cactus_complete(model, messages_json, options_json, tools_json, callback,
    pcm_data)`` and must return the engine's JSON response string.

    ``cloud_complete_fn`` is invoked as ``cloud_complete_fn(messages_json,
    query)`` when the router picks CLOUD / CLOUD_PII_STRIP / CASCADE. If not
    supplied, the handler falls back to the local response and records the
    reason.
    """
    options_with_disabled_handoff = _merge_options(
        options_json,
        {"confidence_threshold": _ENGINE_HANDOFF_DISABLED_THRESHOLD},
    )

    raw = complete_fn(
        model,
        messages_json,
        options_with_disabled_handoff,
        tools_json,
        callback,
        pcm_data,
    )

    try:
        engine_result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Engine returned non-JSON response: {e}") from e

    if not engine_result.get("success", False):
        err = engine_result.get("error") or "unknown engine error"
        raise RuntimeError(f"cactus_complete failed: {err}")

    local_response = engine_result.get("response", "")
    confidence = float(engine_result.get("confidence", 0.0))
    query = _extract_query(messages_json)

    signals = signal_provider or default_signals
    metadata: dict[str, Any] = {
        "engine_total_time_ms": engine_result.get("total_time_ms"),
        "engine_time_to_first_token_ms": engine_result.get("time_to_first_token_ms"),
    }
    model_default = engine_result.get("model_default_confidence_threshold")
    if isinstance(model_default, (int, float)):
        metadata["model_default_confidence_threshold"] = float(model_default)
    if routing_metadata:
        metadata.update(routing_metadata)

    context = RoutingContext(
        query=query,
        confidence=confidence,
        battery_pct=signals.battery_pct(),
        network_quality=signals.network_quality(),
        latency_budget_ms=signals.latency_budget_ms(),
        metadata=metadata,
    )
    decision: PolicyResult = router.route(context)

    payload_modes = dict(DEFAULT_CLOUD_PAYLOAD_MODE)
    if cloud_payload_mode_by_action:
        payload_modes.update(cloud_payload_mode_by_action)

    base = RoutedEngineCompletion(
        response=local_response,
        action=decision.action,
        policy_name=decision.policy_name,
        scores=decision.scores,
        engine_stats=engine_result,
        reason=decision.reason,
        function_calls=list(engine_result.get("function_calls", []) or []),
        thinking=engine_result.get("thinking"),
    )

    if decision.action == RoutingAction.LOCAL:
        return base

    if decision.action == RoutingAction.REFUSE:
        base.response = "I cannot answer this question with the current settings."
        return base

    stripper = pii_stripper or PIIStripper()
    anonymized = stripper.strip(query, pii_profile or PIIProfile()) if query else ""

    if decision.action in (
        RoutingAction.CLOUD,
        RoutingAction.CLOUD_PII_STRIP,
        RoutingAction.CASCADE,
    ):
        cloud_query, mode = _payload_for(
            decision.action, query, anonymized, payload_modes
        )
        base.cloud_payload_mode = mode.value
        if mode == CloudPayloadMode.STRIPPED:
            base.anonymized_query = anonymized

        if cloud_complete_fn is None:
            base.action = RoutingAction.LOCAL
            base.reason = "Cloud unavailable, falling back to local"
            return base

        cloud_response = cloud_complete_fn(messages_json, cloud_query)

        if decision.action == RoutingAction.CASCADE:
            base.response = (
                f"{local_response}\n\n[Verified by cloud: {cloud_response}]"
            )
        else:
            base.response = cloud_response
        return base

    base.action = RoutingAction.LOCAL
    base.reason = "Unknown action, defaulted to local"
    return base
