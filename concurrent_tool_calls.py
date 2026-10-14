#this code to handle concurrent tool calls

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolRequest:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class ToolResult:
    id: str
    success: bool
    output: Any | None
    error: str | None
    elapsed_ms: float

class ToolExecutor:
    def __init__(
        self,
        registry,
        max_concurrency: int = 3,
        tool_timeout: float = 10.0,
    ):
        # Registry hides how tools are looked up/executed.
        # Executor only owns concurrency, timeout, ordering, and result capture.
        self.registry = registry
        self.max_concurrency = max_concurrency
        self.tool_timeout = tool_timeout

    async def execute_batch(
        self,
        requests: list[ToolRequest],
    ) -> list[ToolResult]:
        # Edge case: empty input should return empty output immediately.
        if not requests:
            return []

        # Semaphore enforces max concurrency.
        # Even if there are 100 requests, only N execute at once.
        semaphore = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            asyncio.create_task(
                self._execute_one(request, semaphore)
            )
            for request in requests
        ]

        try:
            # asyncio.gather preserves input ordering.
            # Result i corresponds to request i, even if tasks finish out of order.
            return await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            # Parent-task cancellation should propagate.
            # But first, cancel children to avoid leaked work.
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

            raise

    async def _execute_one(
        self,
        request: ToolRequest,
        semaphore: asyncio.Semaphore,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            # The semaphore slot is held only while this tool is executing.
            async with semaphore:
                output = await asyncio.wait_for(
                    self.registry.execute(
                        request.name,
                        request.arguments,
                    ),
                    timeout=self.tool_timeout,
                )

            elapsed_ms = (time.perf_counter() - start) * 1000

            return ToolResult(
                id=request.id,
                success=True,
                output=output,
                error=None,
                elapsed_ms=elapsed_ms,
            )

        except asyncio.CancelledError:
            # Do not swallow cancellation.
            # Cancellation usually means the caller no longer wants this batch.
            raise

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000

            return ToolResult(
                id=request.id,
                success=False,
                output=None,
                error=f"Tool timed out after {self.tool_timeout} seconds",
                elapsed_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000

            return ToolResult(
                id=request.id,
                success=False,
                output=None,
                error=f"{type(exc).__name__}: {exc}",
                elapsed_ms=elapsed_ms,
            )