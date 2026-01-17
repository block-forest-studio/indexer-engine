from __future__ import annotations

from collections.abc import Awaitable, Callable

from .staging.evm_event_logs_task import index_evm_event_logs_task as staging__index_evm_event_logs_task
from .analytics.evm_events_task import index_evm_events_task as analytics__index_evm_events_task

TaskFn = Callable[[int, str, str], Awaitable[None]]

TASKS: dict[str, TaskFn] = {
    "staging__index_evm_event_logs_task": staging__index_evm_event_logs_task,
    "analytics__index_evm_events_task": analytics__index_evm_events_task,
}
