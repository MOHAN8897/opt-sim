
import asyncio
import sys
import os

# Ensure backend can be imported
sys.path.append(os.getcwd())

from sqlalchemy import text
from backend.database import engine

async def verify_schema():
    print("Verifying 'orders' table schema...")
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(orders)"))
        columns = [row[1] for row in result.fetchall()]
        
        missing = []
        if 'expected_price' not in columns: missing.append('expected_price')
        if 'slippage' not in columns: missing.append('slippage')
        
        if missing:
            print(f"❌ MISSING COLUMNS: {missing}")
            # If missing, we can try to run migration right here or exit
        else:
            print("✅ 'expected_price' column FOUND")
            print("✅ 'slippage' column FOUND")
            print("Database schema is UP TO DATE.")

if __name__ == "__main__":
    try:
        asyncio.run(verify_schema())
    except Exception as e:
        print(f"Error: {e}")
