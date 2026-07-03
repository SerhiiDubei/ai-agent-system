"""FastAPI application entrypoint.

Skeleton phase: тільки /health endpoint + skeleton router placeholders.
Node-specific routers будуть imported по мірі implementation per node.
"""

import logging
import sys
from contextlib import asynccontextmanager

# Windows: psycopg3 async несумісний з ProactorEventLoop (default на Windows).
# Встановлюємо SelectorEventLoop до будь-яких інших імпортів.
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_agent_system import __version__
from ai_agent_system.config import settings

# ── Logging setup ────────────────────────────────────────
logging.basicConfig(
    level=settings.app_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ai_agent_system")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown hooks."""
    log.info("startup env=%s version=%s port=%s", settings.app_env, __version__, settings.app_port)

    # ── Knowledge service + vault watcher (N3) ──
    from openai import AsyncOpenAI
    from ai_agent_system.knowledge.service import KnowledgeService
    from ai_agent_system.knowledge.watcher import VaultWatcher
    from ai_agent_system.db.session import async_session_factory

    openai_client = AsyncOpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.openrouter_base_url,
    )
    knowledge_svc = KnowledgeService(openai_client)
    app.state.knowledge_service = knowledge_svc
    app.state.vault_root = settings.obsidian_vault_path

    # ── Snapshot provider (N1) ──
    from ai_agent_system.snapshot.providers.firecrawl_provider import FirecrawlProvider
    from ai_agent_system.snapshot.providers.jina_provider import JinaReaderProvider

    app.state.snapshot_provider = FirecrawlProvider(
        api_key=settings.firecrawl_api_key,
        base_url=settings.firecrawl_base_url,
        timeout_s=settings.firecrawl_timeout_seconds,
    )
    app.state.snapshot_fallback_provider = JinaReaderProvider()

    watcher: VaultWatcher | None = None
    if settings.knowledge_etl_watch_enabled and settings.obsidian_vault_path.exists():
        async def _ingest(path):
            async with async_session_factory() as session:
                await knowledge_svc.ingest_file(session, path, settings.obsidian_vault_path)
                await session.commit()

        watcher = VaultWatcher(settings.obsidian_vault_path, _ingest)
        await watcher.start()
    else:
        log.info("vault watcher disabled (path=%s exists=%s)",
                 settings.obsidian_vault_path, settings.obsidian_vault_path.exists())

    yield

    if watcher is not None:
        await watcher.stop()
    await openai_client.close()
    log.info("shutdown")


app = FastAPI(
    title="ai-agent-system",
    version=__version__,
    description="Multi-agent AI for A/B-test hypothesis generation on lead-gen landing pages",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,  # disable Swagger in prod
    redoc_url="/redoc" if settings.is_dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe. Used by Docker healthcheck and orchestrators."""
    return {
        "status": "ok",
        "service": "ai-agent-system",
        "version": __version__,
        "env": settings.app_env,
    }


@app.get("/version", tags=["meta"])
async def version() -> dict[str, str]:
    """Expose version + build metadata."""
    return {"version": __version__, "env": settings.app_env}


# ── Routers ──────────────────────────────────────────────
from ai_agent_system.api import admin_cost  # noqa: E402

app.include_router(
    admin_cost.router,
    prefix="/api/v1/admin/cost",
    tags=["admin:cost"],
)

from ai_agent_system.api import knowledge, marketing, semantic, snapshot  # noqa: E402

app.include_router(
    knowledge.router,
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
)
app.include_router(
    snapshot.router,
    prefix="/api/v1/snapshots",
    tags=["snapshot"],
)
app.include_router(
    semantic.router,
    prefix="/api/v1/semantic",
    tags=["semantic"],
)
app.include_router(
    marketing.router,
    prefix="/api/v1/marketing/contexts",
    tags=["marketing"],
)

# ── Future per-node routers (uncomment у відповідних спринтах) ──
# from ai_agent_system.api import snapshot, agents, decisions, proposals, learnings
# app.include_router(snapshot.router, prefix="/api/v1/snapshots", tags=["snapshot"])     # N1
# app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])           # N5
# app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])  # N6
# app.include_router(proposals.router, prefix="/api/v1/proposals", tags=["proposals"])  # N7
# app.include_router(learnings.router, prefix="/api/v1/learnings", tags=["learnings"])  # N8
