"""SnapshotProvider ABC — N1.

Thin interface so Firecrawl-self-hosted, Firecrawl-Cloud, and Jina
are interchangeable without touching caller code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ai_agent_system.snapshot.models import PageSnapshot, Viewport


class SnapshotProvider(ABC):
    name: str

    @abstractmethod
    async def snapshot(
        self,
        url: str,
        viewport: Viewport = Viewport.DESKTOP,
        wait_for_ms: int | None = None,
        actions: list[dict] | None = None,
    ) -> PageSnapshot: ...

    async def health_check(self) -> bool:
        """Optional liveness probe. Override in providers that support it."""
        return True
