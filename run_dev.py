"""Dev server launcher — Windows-compatible (explicit SelectorEventLoop для psycopg3)."""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from uvicorn import Config, Server  # noqa: E402


async def serve():
    config = Config(
        app="ai_agent_system.main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=False,
    )
    server = Server(config=config)
    await server.serve()


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(serve())
    else:
        asyncio.run(serve())
