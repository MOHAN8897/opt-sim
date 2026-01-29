"""
Standalone database migration to add feed_entitlement column
Run this directly: python migrate_feed_entitlement.py
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:Sai%401234@localhost/paper_trading"
)

async def run_migration():
    print("=" * 60)
    print("Migration: Add feed_entitlement column")
    print("=" * 60)
    print(f"Database: {DATABASE_URL.replace(':1234', ':****')}")
    print()
    
    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check if column already exists
            print("🔍 Checking if column exists...")
            check_query = text("""
                SELECT COUNT(*) as col_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'upstox_accounts'
                AND COLUMN_NAME = 'feed_entitlement'
            """)
            
            result = await conn.execute(check_query)
            exists = result.scalar()
            
            if exists:
                print("✅ Column 'feed_entitlement' already exists. Skipping migration.")
                return
            
            print("📝 Adding 'feed_entitlement' column...")
            
            # Add the column
            alter_query = text("""
                ALTER TABLE upstox_accounts
                ADD COLUMN feed_entitlement TINYINT(1) NOT NULL DEFAULT 0
                COMMENT 'WebSocket feed entitlement: 0=unavailable/unverified, 1=verified and available'
            """)
            
            await conn.execute(alter_query)
            print("✅ Column added successfully!")
            
            # Verify
            print("\n🔍 Verifying column was added...")
            verify_query = text("""
                SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'upstox_accounts'
                AND COLUMN_NAME = 'feed_entitlement'
            """)
            
            result = await conn.execute(verify_query)
            row = result.fetchone()
            
            if row:
                print("\n📋 Column Details:")
                print(f"  Name:     {row[0]}")
                print(f"  Type:     {row[1]}")
                print(f"  Default:  {row[2]}")
                print(f"  Nullable: {row[3]}")
                print(f"  Comment:  {row[4]}")
            
            print("\n")
    finally:
        await engine.dispose()
    
    print("=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    print("\nYou can now restart the backend server.")

if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
