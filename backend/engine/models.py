"""Plain data objects passed into and out of the engine."""
from collections.abc import Hashable
from dataclasses import dataclass
from datetime import date

TaskId = Hashable


@dataclass(frozen=True)
class Task:
    id: TaskId
    duration: int  # working days; 0 means a milestone


@dataclass(frozen=True)
class Link:
    """`successor` cannot start until `predecessor` is done."""

    predecessor: TaskId
    successor: TaskId


@dataclass(frozen=True)
class TaskSchedule:
    start: date
    end: date  # inclusive: a 1-day task starts and ends on the same day
    slack: int  # working days the task can slip without moving the project end
    is_critical: bool


@dataclass(frozen=True)
class ScheduleResult:
    tasks: dict[TaskId, TaskSchedule]
    project_end: date
