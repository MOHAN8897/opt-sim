import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from backend.models import Base, User, UpstoxAccount, Trade
import pymysql

# Install pymysql as MySQLdb if needed by sqlalchemy
pymysql.install_as_MySQLdb()

# Sync URL derived from .env (mysql+aiomysql -> mysql+pymysql)
DATABASE_URL = "mysql+pymysql://root:Sai%401234@localhost/paper_trading"

def reset_database():
    from sqlalchemy import text
    
    # Root connection (no DB selected)
    ROOT_URL = "mysql+pymysql://root:Sai%401234@localhost/"
    root_engine = create_engine(ROOT_URL, echo=True)
    
    with root_engine.connect() as conn:
        print("🔥 Dropping Database 'paper_trading'...")
        conn.execute(text("DROP DATABASE IF EXISTS paper_trading"))
        print("✨ Creating Database 'paper_trading'...")
        conn.execute(text("CREATE DATABASE paper_trading"))
    
    # Dispose root engine
    root_engine.dispose()
    
    # Now connect to new DB and create tables
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL, echo=True)
    
    print("✨ Creating new tables...")
    Base.metadata.create_all(engine)
    print("✅ New tables created.")

if __name__ == "__main__":
    reset_database()
