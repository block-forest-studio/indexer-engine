from __future__ import annotations

from collections.abc import Awaitable, Callable

from .evm_event_logs_task import index_evm_event_logs_task

TaskFn = Callable[[int, str, str], Awaitable[None]]

TASKS: dict[str, TaskFn] = {
    "evm_event_logs_task": index_evm_event_logs_task,
}
