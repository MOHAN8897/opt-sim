import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from backend.models import User, UpstoxAccount
from backend.broker import decrypt
from datetime import datetime

DATABASE_URL = "mysql+aiomysql://root:Sai%401234@localhost/paper_trading"

async def check_token_status():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(select(UpstoxAccount))
        accounts = result.scalars().all()
        
        print(f"\n{'='*60}")
        print(f"UPSTOX ACCOUNT STATUS")
        print(f"{'='*60}\n")
        
        for acc in accounts:
            print(f"User ID: {acc.user_id}")
            print(f"Status: {acc.status}")
            print(f"Token Expiry: {acc.token_expiry}")
            print(f"Feed Entitlement: {acc.feed_entitlement}")
            print(f"Has Access Token: {bool(acc.access_token)}")
            
            if acc.access_token:
                try:
                    token = decrypt(acc.access_token)
                    print(f"Token Length: {len(token)}")
                    print(f"Token Preview: {token[:10]}...{token[-10:]}")
                except Exception as e:
                    print(f"Error decrypting token: {e}")
            
            if acc.token_expiry:
                now = datetime.utcnow()
                expiry = acc.token_expiry.replace(tzinfo=None) if acc.token_expiry.tzinfo else acc.token_expiry
                is_expired = expiry < now
                time_remaining = expiry - now if not is_expired else now - expiry
                print(f"Expired: {is_expired}")
                print(f"Time {'remaining' if not is_expired else 'since expiry'}: {time_remaining}")
            
            print(f"\n{'-'*60}\n")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_token_status())
