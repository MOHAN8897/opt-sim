"""
Run database migration to add feed_entitlement column
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from backend.database import engine

async def run_migration():
    print("=" * 60)
    print("Running Migration: Add Execution Realism columns (Order table)")
    print("=" * 60)
    
    async with engine.begin() as conn:
        # Check if columns already exist
        check_query = text("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'orders'
            AND COLUMN_NAME IN ('expected_price', 'slippage')
        """)
        
        result = await conn.execute(check_query)
        existing_cols = [row[0] for row in result.fetchall()]
        
        if 'expected_price' in existing_cols and 'slippage' in existing_cols:
            print("✅ Columns 'expected_price' and 'slippage' already exist. Skipping.")
            return

        print("📝 Adding new columns to 'orders' table...")
        
        if 'expected_price' not in existing_cols:
            await conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN expected_price DECIMAL(18,4) NULL
                COMMENT 'Price user saw when placing order'
            """))
            print("  ✓ Added expected_price")
            
        if 'slippage' not in existing_cols:
            await conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN slippage DECIMAL(18,4) NULL
                COMMENT 'Difference between expected and fill price'
            """))
            print("  ✓ Added slippage")

        print("✅ Migration applied successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())
