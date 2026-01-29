"""
Database Migration Script
Adds missing columns to users table
"""
import asyncio
import sys
sys.path.insert(0, 'C:/Users/subha/OneDrive/Desktop/simulator')

from backend.database import engine
from sqlalchemy import text

async def migrate():
    """Add last_login and last_active columns to users table"""
    async with engine.begin() as conn:
        try:
            # Check if columns exist
            result = await conn.execute(text(
                "SHOW COLUMNS FROM users WHERE Field IN ('last_login', 'last_active')"
            ))
            existing_columns = [row[0] for row in result]
            
            print(f"Existing columns: {existing_columns}")
            
            #Add last_login if missing
            if 'last_login' not in existing_columns:
                print("Adding last_login column...")
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN last_login DATETIME DEFAULT NULL"
                ))
                print("✅ last_login column added")
            else:
                print("last_login column already exists")
            
            # Add last_active if missing
            if 'last_active' not in existing_columns:
                print("Adding last_active column...")
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN last_active DATETIME DEFAULT CURRENT_TIMESTAMP"
                ))
                print("✅ last_active column added")
            else:
                print("last_active column already exists")
                
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(migrate())
