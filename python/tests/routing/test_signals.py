import unittest
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.signals import (
    SignalProvider,
    get_battery_pct,
    get_network_quality,
    get_latency_budget_ms,
)


class TestSignalProvider(unittest.TestCase):

    def test_default_signals(self):
        provider = SignalProvider()
        battery = provider.battery_pct()
        network = provider.network_quality()
        latency = provider.latency_budget_ms()

        self.assertIsInstance(battery, float)
        self.assertIn(network, ["offline", "slow", "fast"])
        self.assertIsInstance(latency, int)

    def test_custom_signals(self):
        provider = SignalProvider(
            battery_fn=lambda: 42.0,
            network_fn=lambda: "slow",
            latency_fn=lambda: 500,
        )
        self.assertEqual(provider.battery_pct(), 42.0)
        self.assertEqual(provider.network_quality(), "slow")
        self.assertEqual(provider.latency_budget_ms(), 500)

    def test_battery_returns_valid_range(self):
        battery = get_battery_pct()
        self.assertGreaterEqual(battery, 0.0)
        self.assertLessEqual(battery, 100.0)

    def test_latency_from_env(self):
        os.environ["CACTUS_LATENCY_BUDGET_MS"] = "250"
        try:
            latency = get_latency_budget_ms()
            self.assertEqual(latency, 250)
        finally:
            del os.environ["CACTUS_LATENCY_BUDGET_MS"]

    def test_latency_invalid_env_returns_default(self):
        os.environ["CACTUS_LATENCY_BUDGET_MS"] = "invalid"
        try:
            latency = get_latency_budget_ms()
            self.assertEqual(latency, 1000)
        finally:
            del os.environ["CACTUS_LATENCY_BUDGET_MS"]

    def test_offline_mode_from_env(self):
        os.environ["CACTUS_OFFLINE_MODE"] = "1"
        try:
            network = get_network_quality()
            self.assertEqual(network, "offline")
        finally:
            del os.environ["CACTUS_OFFLINE_MODE"]


if __name__ == "__main__":
    unittest.main()
