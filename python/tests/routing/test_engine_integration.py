"""Tests for wiring CactusRouter into the cactus_complete engine flow.

These exercise the Python-level shim (routed_complete) that wraps the engine
call, disables its built-in cloud-handoff gate, and lets the router make the
routing decision based on the engine's confidence + timing output.
"""

import json
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.actions import RoutingAction
from src.routing.router import CactusRouter
from src.routing.policies.threshold import ThresholdPolicy
from src.routing.engine_integration import routed_complete


def _engine_result(
    response: str = "Local answer",
    confidence: float = 0.9,
    extra: dict | None = None,
) -> str:
    base = {
        "success": True,
        "error": None,
        "cloud_handoff": False,
        "response": response,
        "function_calls": [],
        "segments": [],
        "confidence": confidence,
        "time_to_first_token_ms": 45.2,
        "total_time_ms": 163.7,
        "prefill_tps": 619.5,
        "decode_tps": 168.4,
        "ram_usage_mb": 512.3,
        "prefill_tokens": 28,
        "decode_tokens": 12,
        "total_tokens": 40,
    }
    if extra:
        base.update(extra)
    return json.dumps(base)


class TestRoutedComplete(unittest.TestCase):

    def test_high_confidence_keeps_local_response(self):
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        complete_fn = MagicMock(return_value=_engine_result(confidence=0.9))
        cloud_fn = MagicMock()

        result = routed_complete(
            model=1234,
            messages_json="[]",
            router=router,
            complete_fn=complete_fn,
            cloud_complete_fn=cloud_fn,
        )

        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertEqual(result.response, "Local answer")
        cloud_fn.assert_not_called()

    def test_low_confidence_triggers_cloud(self):
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        complete_fn = MagicMock(return_value=_engine_result(confidence=0.3))
        cloud_fn = MagicMock(return_value="Cloud says this")

        result = routed_complete(
            model=1234,
            messages_json='[{"role":"user","content":"hi"}]',
            router=router,
            complete_fn=complete_fn,
            cloud_complete_fn=cloud_fn,
        )

        self.assertEqual(result.action, RoutingAction.CLOUD)
        self.assertEqual(result.response, "Cloud says this")
        cloud_fn.assert_called_once()

    def test_disables_engine_cloud_handoff(self):
        """The router owns handoff, so the engine's threshold-based gate must
        not fire. Assert that routed_complete patches the options to disable it."""
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        captured = {}

        def capturing_complete(model, messages_json, options_json, tools_json, callback, pcm_data=None):
            captured["options_json"] = options_json
            return _engine_result(confidence=0.9)

        routed_complete(
            model=1234,
            messages_json="[]",
            router=router,
            complete_fn=capturing_complete,
        )

        # Engine saw an options_json with confidence_threshold driven very low
        # so it never triggers its internal cloud_handoff path.
        self.assertIsNotNone(captured["options_json"])
        options = json.loads(captured["options_json"])
        self.assertLess(options.get("confidence_threshold", 1.0), 0.01)

    def test_preserves_engine_telemetry_on_local(self):
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        complete_fn = MagicMock(
            return_value=_engine_result(confidence=0.9)
        )

        result = routed_complete(
            model=1234,
            messages_json="[]",
            router=router,
            complete_fn=complete_fn,
        )

        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertIn("total_time_ms", result.engine_stats)
        self.assertEqual(result.engine_stats["confidence"], 0.9)
        self.assertEqual(result.engine_stats["total_tokens"], 40)

    def test_passes_model_default_threshold_to_router(self):
        """When the caller doesn't set a threshold, the engine falls back to
        a per-model default. The router shim must forward that default via
        context metadata so ThresholdPolicy(None) can match engine behavior."""
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=None))

        complete_fn = MagicMock(
            return_value=_engine_result(
                confidence=0.75,
                extra={"model_default_confidence_threshold": 0.8},
            )
        )
        cloud_fn = MagicMock(return_value="Cloud answer")

        result = routed_complete(
            model=1234,
            messages_json="[]",
            router=router,
            complete_fn=complete_fn,
            cloud_complete_fn=cloud_fn,
        )

        # Engine reported 0.75, model default is 0.8 -> below threshold -> cloud.
        self.assertEqual(result.action, RoutingAction.CLOUD)

    def test_no_cloud_function_falls_back_to_local(self):
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        complete_fn = MagicMock(return_value=_engine_result(confidence=0.3))

        result = routed_complete(
            model=1234,
            messages_json="[]",
            router=router,
            complete_fn=complete_fn,
            cloud_complete_fn=None,
        )

        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertIn("Cloud unavailable", result.reason or "")

    def test_engine_error_propagates(self):
        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        complete_fn = MagicMock(
            return_value=json.dumps({
                "success": False,
                "error": "Tokenizer unavailable",
                "response": "",
            })
        )

        with self.assertRaises(RuntimeError) as cm:
            routed_complete(
                model=1234,
                messages_json="[]",
                router=router,
                complete_fn=complete_fn,
            )
        self.assertIn("Tokenizer unavailable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
