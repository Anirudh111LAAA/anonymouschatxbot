from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Plan:
    label: str
    stars: int
    duration: timedelta


PLANS: dict[str, Plan] = {
    "day": Plan("1 Day", 39, timedelta(days=1)),
    "week": Plan("1 Week", 149, timedelta(weeks=1)),
    "month": Plan("1 Month", 349, timedelta(days=30)),
    "4month": Plan("4 Months", 999, timedelta(days=120)),
}
