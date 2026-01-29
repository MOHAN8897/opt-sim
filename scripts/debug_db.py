import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
import sys

# DATABASE_URL from .env (Verified via file read earlier)
# mysql+aiomysql://root:Sai%401234@localhost/paper_trading
DATABASE_URL = "mysql+aiomysql://root:Sai%401234@localhost/paper_trading"

async def test_db():
    print(f"Testing connection to: {DATABASE_URL}")
    try:
        engine = create_async_engine(DATABASE_URL, echo=True)
        async with engine.connect() as conn:
            print("Successfully connected to Database!")
            result = await conn.execute(text("SELECT 1"))
            print(f"Query Result: {result.scalar()}")
    except Exception as e:
        print(f"FAILED to connect: {e}")
        # Print detailed info
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_db())
