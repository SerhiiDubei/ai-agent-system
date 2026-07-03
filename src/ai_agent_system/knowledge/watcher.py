"""Watchdog file watcher for Obsidian vault — N3.

Per N3 research:
- Watchdog runs in a daemon thread; events bridged to asyncio via queue
- 1.5s debounce minimum (Obsidian fires 2-3 Modified events per save on Windows)
- .obsidian/ and .git/ dirs skipped
- on_moved handled (Obsidian Sync writes via temp file + rename)
- PollingObserver available as fallback for network drives / Obsidian Sync
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Coroutine

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

log = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 1.5
IngestFn = Callable[[Path], Coroutine]


class _VaultHandler(FileSystemEventHandler):
    """Watchdog event handler: filters .md files, bridges to asyncio queue."""

    def __init__(self, queue: asyncio.Queue, vault_root: Path, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._queue = queue
        self._vault_root = vault_root
        self._loop = loop

    def _enqueue(self, path_str: str) -> None:
        p = Path(path_str)
        # Only process .md files outside special dirs
        if p.suffix != ".md":
            return
        if ".obsidian" in p.parts or ".git" in p.parts:
            return
        asyncio.run_coroutine_threadsafe(self._queue.put(p), self._loop)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event) -> None:
        # Obsidian Sync: temp file → real file via rename. Watch dest.
        if not event.is_directory:
            self._enqueue(event.dest_path)


async def _consume(
    queue: asyncio.Queue,
    ingest_fn: IngestFn,
    debounce_s: float = DEBOUNCE_SECONDS,
) -> None:
    """Consume file events from the queue with per-file debouncing.

    Coalesces burst writes (Obsidian saves several Modified events in quick
    succession). Only triggers ingest after the file has been stable for
    debounce_s seconds.
    """
    pending: dict[Path, asyncio.TimerHandle] = {}
    loop = asyncio.get_running_loop()

    async def _run(path: Path) -> None:
        pending.pop(path, None)
        log.debug("watcher: triggering ingest for %s", path)
        try:
            await ingest_fn(path)
        except Exception as exc:
            log.error("watcher: ingest error for %s: %s", path, exc)

    while True:
        path: Path = await queue.get()

        if path in pending:
            pending[path].cancel()

        pending[path] = loop.call_later(
            debounce_s,
            lambda p=path: asyncio.create_task(_run(p)),
        )


class VaultWatcher:
    """Manages the watchdog Observer + asyncio consumer for the Obsidian vault.

    Usage (inside FastAPI lifespan):
        watcher = VaultWatcher(vault_root, ingest_fn, use_polling=False)
        await watcher.start()
        yield
        await watcher.stop()
    """

    def __init__(
        self,
        vault_root: Path,
        ingest_fn: IngestFn,
        *,
        use_polling: bool = False,
        debounce_s: float = DEBOUNCE_SECONDS,
    ) -> None:
        self._vault_root = vault_root
        self._ingest_fn = ingest_fn
        self._use_polling = use_polling
        self._debounce_s = debounce_s

        self._observer: Observer | None = None
        self._consumer_task: asyncio.Task | None = None
        self._queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        handler = _VaultHandler(self._queue, self._vault_root, loop)
        cls = PollingObserver if self._use_polling else Observer
        self._observer = cls()
        self._observer.schedule(handler, str(self._vault_root), recursive=True)
        self._observer.start()

        self._consumer_task = asyncio.create_task(
            _consume(self._queue, self._ingest_fn, self._debounce_s),
            name="knowledge-etl-consumer",
        )
        log.info(
            "vault watcher started: %s (polling=%s)", self._vault_root, self._use_polling
        )

    async def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        log.info("vault watcher stopped")
