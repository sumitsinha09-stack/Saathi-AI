import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set testing environment variables before importing app
os.environ["APP_ENV"] = "testing"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token_123"
os.environ["WHATSAPP_APP_SECRET"] = "test_secret_key_456"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "test_access_token_789"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "1000123456789"
os.environ["WHATSAPP_API_VERSION"] = "v21.0"

from backend.app.config import settings
settings.WHATSAPP_VERIFY_TOKEN = "test_verify_token_123"
settings.WHATSAPP_APP_SECRET = "test_secret_key_456"
settings.WHATSAPP_ACCESS_TOKEN = "test_access_token_789"
settings.WHATSAPP_PHONE_NUMBER_ID = "1000123456789"
settings.WHATSAPP_API_VERSION = "v21.0"

from backend.app.database import Base, get_db
from backend.app.main import app

# Isolated in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
