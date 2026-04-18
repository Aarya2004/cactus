import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext
from src.routing.actions import RoutingAction
from src.routing.policy import RoutingPolicy, PolicyResult


class MockPolicy(RoutingPolicy):
    def __init__(self, fixed_action: RoutingAction):
        self._action = fixed_action

    @property
    def name(self) -> str:
        return "mock"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"mock_score": 0.5}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        return self._action


class TestRoutingPolicy(unittest.TestCase):

    def test_policy_has_name(self):
        policy = MockPolicy(RoutingAction.LOCAL)
        self.assertEqual(policy.name, "mock")

    def test_score_returns_dict(self):
        policy = MockPolicy(RoutingAction.LOCAL)
        ctx = RoutingContext(query="test", confidence=0.8)
        scores = policy.score(ctx)
        self.assertIsInstance(scores, dict)
        self.assertIn("mock_score", scores)

    def test_decide_returns_action(self):
        policy = MockPolicy(RoutingAction.CLOUD)
        action = policy.decide({"mock_score": 0.5})
        self.assertEqual(action, RoutingAction.CLOUD)


class TestPolicyResult(unittest.TestCase):

    def test_creates_result(self):
        result = PolicyResult(
            action=RoutingAction.LOCAL,
            scores={"confidence": 0.9, "battery": 0.7},
            policy_name="threshold",
        )
        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertEqual(result.scores["confidence"], 0.9)
        self.assertEqual(result.policy_name, "threshold")

    def test_result_has_reason(self):
        result = PolicyResult(
            action=RoutingAction.CLOUD,
            scores={"confidence": 0.3},
            policy_name="threshold",
            reason="Low confidence triggered cloud handoff",
        )
        self.assertEqual(result.reason, "Low confidence triggered cloud handoff")

    def test_result_default_reason(self):
        result = PolicyResult(
            action=RoutingAction.LOCAL,
            scores={},
            policy_name="test",
        )
        self.assertIsNone(result.reason)


if __name__ == "__main__":
    unittest.main()
