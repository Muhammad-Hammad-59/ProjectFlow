"""Forward and backward pass over the task graph.

Internally a task occupies working-day numbers [early_start, early_start + duration),
where 0 is the first working day on or after the project start.
"""
from collections.abc import Iterable
from datetime import date

from engine.calendar import Calendar
from engine.graph import topological_order
from engine.models import Link, ScheduleResult, Task, TaskId, TaskSchedule


def schedule(
    tasks: Iterable[Task],
    links: Iterable[Link],
    project_start: date,
    calendar: Calendar,
) -> ScheduleResult:
    duration = _durations(tasks)
    task_ids = list(duration)
    preds, succs = _adjacency(task_ids, links)
    order = topological_order(task_ids, succs)

    # Forward pass: a task starts right after its latest-finishing predecessor.
    early_start: dict[TaskId, int] = {}
    early_finish: dict[TaskId, int] = {}
    for task_id in order:
        early_start[task_id] = max((early_finish[p] for p in preds[task_id]), default=0)
        early_finish[task_id] = early_start[task_id] + duration[task_id]
    finish = max(early_finish.values(), default=0)

    # Backward pass: a task must finish before its earliest-starting successor begins.
    late_start: dict[TaskId, int] = {}
    late_finish: dict[TaskId, int] = {}
    for task_id in reversed(order):
        late_finish[task_id] = min((late_start[s] for s in succs[task_id]), default=finish)
        late_start[task_id] = late_finish[task_id] - duration[task_id]

    days = calendar.working_days_from(project_start, max(finish, 1))
    result: dict[TaskId, TaskSchedule] = {}
    for task_id in task_ids:
        start, end = _dates(days, early_start[task_id], duration[task_id])
        slack = late_finish[task_id] - early_finish[task_id]
        result[task_id] = TaskSchedule(start=start, end=end, slack=slack, is_critical=slack == 0)

    return ScheduleResult(tasks=result, project_end=days[max(finish, 1) - 1])


def _durations(tasks: Iterable[Task]) -> dict[TaskId, int]:
    duration: dict[TaskId, int] = {}
    for task in tasks:
        if task.id in duration:
            raise ValueError(f"Duplicate task id: {task.id}")
        if task.duration < 0:
            raise ValueError(f"Task {task.id} has a negative duration.")
        duration[task.id] = task.duration
    return duration


def _adjacency(
    task_ids: list[TaskId], links: Iterable[Link]
) -> tuple[dict[TaskId, list[TaskId]], dict[TaskId, list[TaskId]]]:
    preds: dict[TaskId, list[TaskId]] = {t: [] for t in task_ids}
    succs: dict[TaskId, list[TaskId]] = {t: [] for t in task_ids}
    seen: set[tuple[TaskId, TaskId]] = set()
    for link in links:
        for task_id in (link.predecessor, link.successor):
            if task_id not in preds:
                raise ValueError(f"Link refers to unknown task: {task_id}")
        pair = (link.predecessor, link.successor)
        if pair in seen:
            continue
        seen.add(pair)
        succs[link.predecessor].append(link.successor)
        preds[link.successor].append(link.predecessor)
    return preds, succs


def _dates(days: list[date], start_index: int, duration: int) -> tuple[date, date]:
    if duration == 0:
        # A milestone sits on the last day of its latest predecessor
        # (or on the first working day if it has none).
        day = days[max(start_index - 1, 0)]
        return day, day
    return days[start_index], days[start_index + duration - 1]
