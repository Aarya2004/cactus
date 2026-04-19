from enum import Enum


class RoutingAction(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    CLOUD_PII_STRIP = "cloud_pii_strip"
    CASCADE = "cascade"
    REFUSE = "refuse"

    @property
    def requires_cloud(self) -> bool:
        return self in (
            RoutingAction.CLOUD,
            RoutingAction.CLOUD_PII_STRIP,
            RoutingAction.CASCADE,
        )

    @property
    def requires_pii_strip(self) -> bool:
        return self == RoutingAction.CLOUD_PII_STRIP
