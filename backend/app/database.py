from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from backend.app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def init_db() -> None:
    """Initialize database tables and apply safe schema updates."""
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Safe migrations for Phase 6 columns if tables already exist
            try:
                await conn.execute(text("ALTER TABLE complaint_status_history ADD COLUMN IF NOT EXISTS action_type VARCHAR(32);"))
                await conn.execute(text("ALTER TABLE complaint_status_history ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE;"))
                await conn.execute(text("ALTER TABLE complaint_status_history ADD COLUMN IF NOT EXISTS extra_data TEXT;"))
            except Exception as mig_err:
                logger.debug(f"Schema migration statement non-fatal check: {mig_err}")
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning(f"Database table initialization skipped (database connection unavailable): {e}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
