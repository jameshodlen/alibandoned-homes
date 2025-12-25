"""Async database session management.

This module provides the async SQLAlchemy engine and session
factory for non-blocking database operations.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Create async engine with connection pooling
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory for creating async sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session.

    This is a FastAPI dependency that yields an async session
    and ensures proper cleanup after the request completes.

    Yields:
        AsyncSession: SQLAlchemy async session for database operations.

    Example:
        ```python
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
