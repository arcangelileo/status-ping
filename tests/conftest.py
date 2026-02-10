import sys
import os

# Ensure src directory is in Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    """Create a user and return an authenticated client."""
    signup_data = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "testpassword123",
        "account_slug": "test-company",
    }
    response = await client.post("/auth/signup", json=signup_data)
    assert response.status_code == 201

    # Extract cookies from signup response
    cookies = response.cookies
    client.cookies.update(cookies)
    return client
