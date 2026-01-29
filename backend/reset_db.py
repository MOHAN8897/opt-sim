import asyncio
import sys
# Force using the WindowsSelectorEventLoopPolicy on Windows to avoid Proactor issues with aiosqlite/asyncpg if not needed for pipes
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from backend.database import engine, Base
from backend.models import User, UpstoxAccount, Trade

async def reset_database():
    """
    Complete database reset:
    1. Close all connections
    2. Drop all tables
    3. Recreate tables with fresh schema
    4. Verify table creation
    """
    try:
        print("=" * 60)
        print("DATABASE RESET - ALL DATA WILL BE DELETED")
        print("=" * 60)
        
        # Step 1: Dispose existing connections
        print("\n🔌 Closing all database connections...")
        await engine.dispose()
        print("✅ All connections closed")
        
        # Step 2: Drop all tables
        print("\n🗑️  Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ All tables dropped successfully")

        # Step 3: Create new tables
        print("\n✨ Creating fresh database schema...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ New tables created successfully")
        
        # Step 4: Verify table creation
        print("\n🔍 Verifying database schema...")
        from sqlalchemy import inspect
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            print(f"✅ Tables created: {', '.join(tables)}")
            
            # Verify each expected table
            expected_tables = ['users', 'upstox_accounts', 'trades']
            for table in expected_tables:
                if table in tables:
                    print(f"  ✓ {table}")
                else:
                    print(f"  ✗ {table} - MISSING!")
        
        print("\n" + "=" * 60)
        print("✅ DATABASE RESET COMPLETE")
        print("=" * 60)
        print("\nℹ️  All users must re-authenticate via Google OAuth")
        print("ℹ️  All broker connections must be reconfigured")
        print("ℹ️  All trade history has been cleared")
        
    except Exception as e:
        print(f"\n❌ Error during database reset: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await engine.dispose()
        print("\n✅ Database engine disposed")


if __name__ == "__main__":
    try:
        asyncio.run(reset_database())
    except RuntimeError as e:
        if str(e) == "Event loop is closed":
            pass
        else:
            raise e
