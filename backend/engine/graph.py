"""Ordering tasks by their links, and finding loops."""
from collections.abc import Mapping, Sequence

from engine.models import TaskId


class CycleError(ValueError):
    """The links form a loop. `cycle` is closed, e.g. [a, b, c, a]."""

    def __init__(self, cycle: Sequence[TaskId]) -> None:
        self.cycle = list(cycle)
        path = " -> ".join(str(task_id) for task_id in self.cycle)
        super().__init__(f"Dependency loop: {path}")


def topological_order(
    task_ids: Sequence[TaskId], successors: Mapping[TaskId, Sequence[TaskId]]
) -> list[TaskId]:
    """Every task after all of its predecessors (Kahn's algorithm). Raises CycleError."""
    in_degree = {task_id: 0 for task_id in task_ids}
    for task_id in task_ids:
        for succ in successors[task_id]:
            in_degree[succ] += 1

    ready = [task_id for task_id in task_ids if in_degree[task_id] == 0]
    order: list[TaskId] = []
    while ready:
        task_id = ready.pop()
        order.append(task_id)
        for succ in successors[task_id]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                ready.append(succ)

    if len(order) < len(task_ids):
        stuck = [task_id for task_id in task_ids if in_degree[task_id] > 0]
        raise CycleError(_find_cycle(stuck, successors))
    return order


def _find_cycle(
    candidates: Sequence[TaskId], successors: Mapping[TaskId, Sequence[TaskId]]
) -> list[TaskId]:
    """Iterative depth-first search among the tasks that could not be ordered.

    Those tasks are either in a loop or downstream of one, so a back edge exists.
    """
    allowed = set(candidates)
    done: set[TaskId] = set()
    for root in candidates:
        if root in done:
            continue
        path = [root]
        on_path = {root}
        stack = [iter(successors[root])]
        while stack:
            succ = next(stack[-1], None)
            if succ is None:
                stack.pop()
                finished = path.pop()
                on_path.discard(finished)
                done.add(finished)
            elif succ in on_path:
                return path[path.index(succ):] + [succ]
            elif succ in allowed and succ not in done:
                path.append(succ)
                on_path.add(succ)
                stack.append(iter(successors[succ]))
    raise AssertionError("unordered tasks without a loop")  # cannot happen
