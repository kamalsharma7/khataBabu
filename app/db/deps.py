from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

# Re-export for FastAPI Depends() in future route modules.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session
