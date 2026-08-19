import asyncio

from briefly.queue import WorkerQueue


def test_worker_queue_reports_error_without_losing_other_items():
    async def process(item: str) -> str:
        if item == "bad":
            raise ValueError("boom")
        return item.upper()

    results: list[str] = []
    errors: list[tuple[str, BaseException]] = []
    queue = WorkerQueue(
        process=process,
        on_result=results.append,
        on_error=lambda item, exc: errors.append((item, exc)),
    )

    asyncio.run(queue.run(["a", "bad", "b"]))

    assert sorted(results) == ["A", "B"]
    assert [item for item, _ in errors] == ["bad"]
