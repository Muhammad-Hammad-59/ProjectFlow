"""Tests for the scheduling engine (backend/engine).

Project start is Monday 2026-11-02 in every test. Dates are inclusive:
a 3-day task that starts on Monday ends on Wednesday.
"""
from datetime import date

import pytest

from engine import Calendar, CycleError, Link, Task, schedule

MON = date(2026, 11, 2)
MON_TO_FRI = {0, 1, 2, 3, 4}


def cal(*holidays: date) -> Calendar:
    return Calendar(working_weekdays=MON_TO_FRI, holidays=set(holidays))


def link(predecessor: str, successor: str) -> Link:
    """`successor` waits for `predecessor`."""
    return Link(predecessor=predecessor, successor=successor)


# --- Worked example from docs/how-it-works.md --------------------------------


@pytest.fixture
def worked_example():
    tasks = [
        Task(id="design", duration=3),
        Task(id="build", duration=5),
        Task(id="docs", duration=2),
        Task(id="test", duration=2),
    ]
    links = [
        link("design", "build"),
        link("design", "docs"),
        link("build", "test"),
        link("docs", "test"),
    ]
    return schedule(tasks, links, project_start=MON, calendar=cal())


def test_worked_example_dates(worked_example):
    t = worked_example.tasks
    assert (t["design"].start, t["design"].end) == (date(2026, 11, 2), date(2026, 11, 4))
    assert (t["build"].start, t["build"].end) == (date(2026, 11, 5), date(2026, 11, 11))
    assert (t["docs"].start, t["docs"].end) == (date(2026, 11, 5), date(2026, 11, 6))
    assert (t["test"].start, t["test"].end) == (date(2026, 11, 12), date(2026, 11, 13))


def test_worked_example_takes_ten_working_days(worked_example):
    # 10 working days from Mon 2026-11-02 ends on the second Friday.
    assert worked_example.project_end == date(2026, 11, 13)


def test_worked_example_critical_path(worked_example):
    t = worked_example.tasks
    for task_id in ("design", "build", "test"):
        assert t[task_id].is_critical, task_id
        assert t[task_id].slack == 0, task_id


def test_worked_example_docs_has_three_days_slack(worked_example):
    docs = worked_example.tasks["docs"]
    assert docs.slack == 3
    assert not docs.is_critical


# --- Counting working days ----------------------------------------------------


def test_three_day_task_starting_monday_ends_wednesday():
    result = schedule([Task(id="a", duration=3)], [], project_start=MON, calendar=cal())
    assert result.tasks["a"].start == MON
    assert result.tasks["a"].end == date(2026, 11, 4)


def test_task_skips_weekend():
    # a: Mon-Wed. b starts Thu and runs Thu, Fri, Mon.
    tasks = [Task(id="a", duration=3), Task(id="b", duration=3)]
    result = schedule(tasks, [link("a", "b")], project_start=MON, calendar=cal())
    assert result.tasks["b"].start == date(2026, 11, 5)
    assert result.tasks["b"].end == date(2026, 11, 9)


def test_holiday_in_the_middle_of_a_task():
    # Tue 2026-11-03 is a holiday: the 3 days are Mon, Wed, Thu.
    result = schedule(
        [Task(id="a", duration=3)], [], project_start=MON, calendar=cal(date(2026, 11, 3))
    )
    assert result.tasks["a"].start == MON
    assert result.tasks["a"].end == date(2026, 11, 5)


def test_successor_starts_on_next_working_day_after_holiday():
    # a: Mon-Tue. Wed is a holiday, so b starts Thu.
    tasks = [Task(id="a", duration=2), Task(id="b", duration=1)]
    result = schedule(
        tasks, [link("a", "b")], project_start=MON, calendar=cal(date(2026, 11, 4))
    )
    assert result.tasks["a"].end == date(2026, 11, 3)
    assert result.tasks["b"].start == date(2026, 11, 5)
    assert result.tasks["b"].end == date(2026, 11, 5)


# --- Task with no links -------------------------------------------------------


def test_task_with_no_links_starts_on_project_start_and_has_slack_to_project_end():
    tasks = [
        Task(id="design", duration=3),
        Task(id="build", duration=5),
        Task(id="test", duration=2),
        Task(id="logo", duration=2),
    ]
    links = [link("design", "build"), link("build", "test")]
    result = schedule(tasks, links, project_start=MON, calendar=cal())

    logo = result.tasks["logo"]
    assert logo.start == MON
    assert logo.end == date(2026, 11, 3)
    # Project ends on working day 10; logo ends on day 2.
    assert result.project_end == date(2026, 11, 13)
    assert logo.slack == 8
    assert not logo.is_critical


# --- Loops --------------------------------------------------------------------


@pytest.mark.parametrize(
    "loop",
    [
        ["a"],  # task waits for itself
        ["a", "b"],
        ["a", "b", "c"],
        ["a", "b", "c", "d", "e"],
    ],
    ids=["self", "two", "three", "five"],
)
def test_loop_raises_error_naming_the_loop(loop):
    # "start" feeds into the loop but is not part of it.
    tasks = [Task(id="start", duration=1)] + [Task(id=t, duration=1) for t in loop]
    links = [link("start", loop[0])]
    links += [link(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]

    with pytest.raises(CycleError) as exc_info:
        schedule(tasks, links, project_start=MON, calendar=cal())

    err = exc_info.value
    assert err.cycle[0] == err.cycle[-1], "cycle should be closed, e.g. a -> b -> a"
    assert len(err.cycle) == len(loop) + 1
    assert set(err.cycle) == set(loop)
    message = str(err)
    for task_id in loop:
        assert task_id in message
    assert "start" not in message
