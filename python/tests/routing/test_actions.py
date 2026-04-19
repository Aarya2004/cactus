import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.actions import RoutingAction


class TestRoutingAction(unittest.TestCase):

    def test_local_action(self):
        self.assertEqual(RoutingAction.LOCAL.value, "local")

    def test_cloud_action(self):
        self.assertEqual(RoutingAction.CLOUD.value, "cloud")

    def test_cloud_pii_strip_action(self):
        self.assertEqual(RoutingAction.CLOUD_PII_STRIP.value, "cloud_pii_strip")

    def test_cascade_action(self):
        self.assertEqual(RoutingAction.CASCADE.value, "cascade")

    def test_refuse_action(self):
        self.assertEqual(RoutingAction.REFUSE.value, "refuse")

    def test_all_actions_unique(self):
        values = [a.value for a in RoutingAction]
        self.assertEqual(len(values), len(set(values)))

    def test_from_string(self):
        self.assertEqual(RoutingAction("local"), RoutingAction.LOCAL)
        self.assertEqual(RoutingAction("cloud"), RoutingAction.CLOUD)

    def test_requires_cloud(self):
        self.assertTrue(RoutingAction.CLOUD.requires_cloud)
        self.assertTrue(RoutingAction.CLOUD_PII_STRIP.requires_cloud)
        self.assertTrue(RoutingAction.CASCADE.requires_cloud)
        self.assertFalse(RoutingAction.LOCAL.requires_cloud)
        self.assertFalse(RoutingAction.REFUSE.requires_cloud)

    def test_requires_pii_strip(self):
        self.assertTrue(RoutingAction.CLOUD_PII_STRIP.requires_pii_strip)
        self.assertFalse(RoutingAction.CLOUD.requires_pii_strip)
        self.assertFalse(RoutingAction.LOCAL.requires_pii_strip)


if __name__ == "__main__":
    unittest.main()
