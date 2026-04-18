"""Platform signal extraction for routing decisions.

These helpers extract battery, network, and other platform signals.
On platforms where the signal isn't available, sensible defaults are returned.
"""

import os
import subprocess
from typing import Literal

NetworkQuality = Literal["offline", "slow", "fast"]


def get_battery_pct() -> float:
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        for line in result.stdout.split("\n"):
            if "%" in line:
                import re
                match = re.search(r"(\d+)%", line)
                if match:
                    return float(match.group(1))
    except Exception:
        pass
    return 100.0


def get_network_quality() -> NetworkQuality:
    if os.environ.get("CACTUS_OFFLINE_MODE"):
        return "offline"

    try:
        result = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if "not associated" in result.stdout.lower():
            return "offline"

        if "error" in result.stderr.lower():
            return "slow"

        return "fast"
    except Exception:
        pass

    return "fast"


def get_latency_budget_ms() -> int:
    budget = os.environ.get("CACTUS_LATENCY_BUDGET_MS")
    if budget:
        try:
            return int(budget)
        except ValueError:
            pass
    return 1000


class SignalProvider:
    def __init__(
        self,
        battery_fn=get_battery_pct,
        network_fn=get_network_quality,
        latency_fn=get_latency_budget_ms,
    ):
        self._battery_fn = battery_fn
        self._network_fn = network_fn
        self._latency_fn = latency_fn

    def battery_pct(self) -> float:
        return self._battery_fn()

    def network_quality(self) -> NetworkQuality:
        return self._network_fn()

    def latency_budget_ms(self) -> int:
        return self._latency_fn()


default_signals = SignalProvider()
