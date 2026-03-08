"""Database Configuration"""

import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/aladdin_parser"
)

# For async operations
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# SQLAlchemy declarative base
Base = declarative_base()


def get_sync_engine():
    """Get synchronous database engine"""
    return create_engine(
        DATABASE_URL,
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        pool_size=5,
        max_overflow=10
    )


def get_async_engine():
    """Get asynchronous database engine"""
    return create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        pool_size=5,
        max_overflow=10
    )


# Session makers
SessionLocal = sessionmaker(bind=get_sync_engine(), expire_on_commit=False)
AsyncSessionLocal = sessionmaker(
    bind=get_async_engine(),
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session() -> AsyncSession:
    """Get async database session"""
    async_session = AsyncSessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()


def get_sync_session():
    """Get sync database session"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
