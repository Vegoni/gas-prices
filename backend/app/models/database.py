"""
Database engine and session setup.

WHY async?
FastAPI is async-first, so our DB layer should be too. SQLAlchemy 2.0
supports async natively via create_async_engine. For SQLite this uses
the aiosqlite driver under the hood.

WHY a sessionmaker?
Each API request (or ingestion run) should get its own database session
with a clear begin/commit/rollback lifecycle. The sessionmaker factory
gives us that without re-creating the engine every time.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings

# The engine is the connection pool. For SQLite, there's only one
# connection, but this same pattern scales to PostgreSQL later.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True to see SQL statements in the console (noisy but useful for debugging)
)

# Factory that produces new AsyncSession instances
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Lets us read attributes after commit without a new query
)


async def init_db():
    """Create all tables. Called once at app startup."""
    from app.models.gas_price import Base  # import here to avoid circular imports

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    Dependency for FastAPI routes.

    Usage in a route:
        async def my_route(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session() as session:
        yield session
