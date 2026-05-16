"""Simulated calendar — tracks day-tick, paydays, holidays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SimCalendar:
    start_date: date
    current_day: int = 0  # zero-indexed day offset from start_date

    @property
    def today(self) -> date:
        return self.start_date + timedelta(days=self.current_day)

    def advance(self, days: int = 1) -> None:
        self.current_day += days

    def is_payday(self) -> bool:
        """Bi-monthly payday: 15th and last day of each month."""
        t = self.today
        if t.day == 15:
            return True
        nxt = t + timedelta(days=1)
        return nxt.month != t.month

    def is_first_of_month(self) -> bool:
        return self.today.day == 1

    def day_of_week(self) -> int:
        """0 = Monday, 6 = Sunday."""
        return self.today.weekday()

    def is_weekend(self) -> bool:
        return self.day_of_week() >= 5

    def week_index(self) -> int:
        """Integer week count from start. Used for weekly reflection cycle."""
        return self.current_day // 7
