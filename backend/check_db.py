import asyncio
from backend.database import engine
from sqlalchemy import inspect

async def check_tables():
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        print(f"Tables found: {tables}")
        
        if 'users' in tables:
            columns = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns('users')])
            print(f"User columns: {columns}")
        
        if 'upstox_accounts' in tables:
            columns = await conn.run_sync(lambda sync_conn: [c['name'] for c in inspect(sync_conn).get_columns('upstox_accounts')])
            print(f"UpstoxAccount columns: {columns}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_tables())
