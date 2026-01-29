from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# ✅ MEDIUM FIX: Connection pooling for better performance
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=True,
    pool_size=20,           # Max connections in pool
    max_overflow=10,        # Extra connections if pool exhausted
    pool_pre_ping=True,     # Health check before using connection
    pool_recycle=3600       # Recycle connections after 1 hour
)

AsyncSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
