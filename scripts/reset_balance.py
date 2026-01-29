import asyncio
from backend.database import AsyncSessionLocal
from backend.models import User
from sqlalchemy import select, update

async def reset_balance():
    print("Connecting to database...")
    async with AsyncSessionLocal() as db:
        print("Resetting all users...")
        await db.execute(update(User).values(virtual_balance=50000.0))
        await db.commit()
        print("Balance reset to 50,000 successfully.")

if __name__ == "__main__":
    # Windows specific fix for asyncio loop
    if asyncio.get_event_loop_policy().__class__.__name__ == 'WindowsProactorEventLoopPolicy':
         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_balance())
