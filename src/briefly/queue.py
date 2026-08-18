import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


@dataclass
class WorkerQueue(Generic[TIn, TOut]):
    process: Callable[[TIn], Awaitable[TOut]]
    on_start: Callable[[TIn], None] | None = None
    on_result: Callable[[TOut], None] | None = None
    on_error: Callable[[TIn, BaseException], None] | None = None
    max_workers: int = 4

    _queue: asyncio.Queue[TIn] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue()

    async def run(self, items: list[TIn]) -> list[TOut]:
        for item in items:
            self._queue.put_nowait(item)

        results: list[TOut] = []
        workers = [
            asyncio.create_task(self._worker(results))
            for _ in range(min(self.max_workers, len(items)))
        ]

        await self._queue.join()
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        return results

    async def _worker(self, results: list[TOut]) -> None:
        while True:
            item = await self._queue.get()
            if self.on_start:
                self.on_start(item)
            try:
                result = await self.process(item)
                results.append(result)
                if self.on_result:
                    self.on_result(result)
            except Exception as exc:
                if self.on_error:
                    self.on_error(item, exc)

            finally:
                self._queue.task_done()
