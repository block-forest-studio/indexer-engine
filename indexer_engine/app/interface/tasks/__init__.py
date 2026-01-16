from __future__ import annotations

from collections.abc import Awaitable, Callable

from .staging_evm_event_logs_task import index_staging_evm_event_logs_task
from .analytics_evm_events_task import index_analytics_evm_events_task

TaskFn = Callable[[int, str, str], Awaitable[None]]

TASKS: dict[str, TaskFn] = {
    "index_staging_evm_event_logs_task": index_staging_evm_event_logs_task,
    "index_analytics_evm_events_task": index_analytics_evm_events_task,
}
