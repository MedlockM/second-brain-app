"""
Database fixtures for tests.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@pytest_asyncio.fixture
async def test_db_engine():
    """
    Create an in-memory SQLite database engine for testing.
    
    Returns:
        An async SQLAlchemy engine
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine):
    """
    Create a test database session with tables created.
    
    Args:
        test_db_engine: The test database engine
        
    Returns:
        An async SQLAlchemy session
    """
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy import MetaData
    
    # Import your models here to create tables
    # from media_summarizer.core.models import Base
    
    # For now, we'll create a simple metadata object
    metadata = MetaData()
    
    # Create all tables
    async with test_db_engine.begin() as conn:
        # await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Yield session
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_db_transaction(test_db_session):
    """
    Create a database transaction that will be rolled back after the test.
    
    Args:
        test_db_session: The test database session
        
    Returns:
        The same session with an active transaction
    """
    async with test_db_session.begin():
        yield test_db_session