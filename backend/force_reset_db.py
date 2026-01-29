from sqlalchemy import create_engine, text
from backend.models import Base, User, UpstoxAccount, Trade
import pymysql

# Install pymysql
pymysql.install_as_MySQLdb()

DATABASE_URL = "mysql+pymysql://root:Sai%401234@localhost/paper_trading"

def reset_database():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL) # echo=False to reduce noise
    
    print("🔧 Disabling Foreign Key Checks...")
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.commit()
    
    print("🗑️  Dropping all tables defined in models...")
    Base.metadata.drop_all(engine)
    
    print("🗑️  Dropping extra tables (sessions)...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS sessions"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version")) # Just in case
        conn.commit()

    print("✅ Tables dropped.")

    print("✨ Creating new tables...")
    Base.metadata.create_all(engine)
    
    print("🔧 Enabling Foreign Key Checks...")
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()
        
    print("✅ Database reset successfully!")

if __name__ == "__main__":
    reset_database()
