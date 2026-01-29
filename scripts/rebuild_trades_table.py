import pymysql

# Config from .env
HOST = "localhost"
USER = "root"
PASS = "Sai@1234"
DB_NAME = "paper_trading"

try:
    conn = pymysql.connect(host=HOST, user=USER, password=PASS, database=DB_NAME)
    cursor = conn.cursor()
    
    print(f"Connected to {DB_NAME}")
    
    # 1. DROP Table
    try:
        print("Dropping 'trades' table...")
        cursor.execute("DROP TABLE IF EXISTS trades;")
        print("✅ Dropped 'trades' table.")
    except Exception as e:
        print(f"⚠️ Drop Error: {e}")

    # 2. CREATE Table (Matching models.py)
    # Note: Using DECIMAL(18, 4) just like models.py
    create_sql = """
    CREATE TABLE trades (
        id int NOT NULL AUTO_INCREMENT,
        user_id int NOT NULL,
        order_id int NOT NULL,
        instrument_key varchar(100) NOT NULL,
        side enum('BUY','SELL') NOT NULL,
        qty int NOT NULL,
        entry_price decimal(18,4) NOT NULL,
        exit_price decimal(18,4),
        exit_order_id int,
        status enum('OPEN','CLOSED') NOT NULL,
        realized_pnl decimal(18,4),
        closed_at datetime,
        created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY ix_trades_user_id (user_id),
        KEY ix_trades_order_id (order_id),
        KEY ix_trades_instrument_key (instrument_key),
        KEY idx_user_status (user_id, status),
        CONSTRAINT fk_trades_users FOREIGN KEY (user_id) REFERENCES users (id),
        CONSTRAINT fk_trades_orders FOREIGN KEY (order_id) REFERENCES orders (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """
    
    try:
        print("Creating 'trades' table...")
        cursor.execute(create_sql)
        print("✅ Created 'trades' table with correct schema.")
    except Exception as e:
        print(f"❌ Create Error: {e}")

    conn.commit()
    conn.close()
    print("Rebuild complete.")

except Exception as e:
    print(f"Connection Error: {e}")
