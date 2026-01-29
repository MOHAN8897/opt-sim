import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import AsyncSessionLocal
from backend.models import UpstoxAccount, UpstoxStatus
from sqlalchemy.future import select

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UpstoxAccount))
        acc = result.scalars().first()
        
        if not acc:
            print("❌ No Upstox account found in database")
        else:
            print(f"✅ Account found for user_id: {acc.user_id}")
            print(f"   Status: {acc.status}")
            print(f"   Has access_token: {bool(acc.access_token)}")
            print(f"   Token expiry: {acc.token_expiry}")
            
            # Check the condition from socket_manager
            is_valid = (acc.status == UpstoxStatus.TOKEN_VALID and bool(acc.access_token))
            print(f"\n   Will WebSocket connect? {is_valid}")
            
            if not is_valid:
                if acc.status != UpstoxStatus.TOKEN_VALID:
                    print(f"   ❌ Status is {acc.status}, not TOKEN_VALID")
                if not acc.access_token:
                    print(f"   ❌ No access_token in database")

if __name__ == "__main__":
    asyncio.run(check())
