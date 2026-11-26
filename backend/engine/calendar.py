"""Working-day calendar: turns working-day numbers into real dates."""
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass(frozen=True)
class Calendar:
    working_weekdays: AbstractSet[int] = frozenset({0, 1, 2, 3, 4})  # Mon=0, like date.weekday()
    holidays: AbstractSet[date] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.working_weekdays:
            raise ValueError("Calendar needs at least one working weekday.")
        if not set(self.working_weekdays) <= set(range(7)):
            raise ValueError("Working weekdays must be numbers 0 (Mon) to 6 (Sun).")

    def is_working_day(self, day: date) -> bool:
        return day.weekday() in self.working_weekdays and day not in self.holidays

    def working_days_from(self, start: date, count: int) -> list[date]:
        """The first `count` working days on or after `start`."""
        days: list[date] = []
        day = start
        while len(days) < count:
            if self.is_working_day(day):
                days.append(day)
            day += timedelta(days=1)
        return days
