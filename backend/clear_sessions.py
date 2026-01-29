"""
Session Clearing Script
This script clears all active sessions by forcing session expiration for all users
without dropping the database tables.
"""
import asyncio
import sys
from datetime import datetime, timedelta

# Force using the WindowsSelectorEventLoopPolicy on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from backend.database import engine, SessionLocal
from backend.models import User
from sqlalchemy.future import select

async def clear_all_sessions():
    """Clear all active sessions by setting last_active to a time in the past"""
    try:
        print("🔄 Clearing all active sessions...")
        
        async with SessionLocal() as db:
            # Get all users
            result = await db.execute(select(User))
            users = result.scalars().all()
            
            if not users:
                print("ℹ️  No users found in database")
                return
            
            # Set last_active to 25 hours ago (beyond 24h session timeout)
            past_time = datetime.utcnow() - timedelta(hours=25)
            
            session_count = 0
            for user in users:
                user.last_active = past_time
                session_count += 1
                print(f"  ✓ Cleared session for: {user.email}")
            
            await db.commit()
            print(f"\n✅ Successfully cleared {session_count} session(s)")
            print("ℹ️  All users will need to re-authenticate on next request")
            
    except Exception as e:
        print(f"❌ Error clearing sessions: {e}")
        raise
    finally:
        await engine.dispose()
        print("✅ Database connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(clear_all_sessions())
    except RuntimeError as e:
        if str(e) == "Event loop is closed":
            pass
        else:
            raise e
