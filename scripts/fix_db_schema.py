import pymysql

# Config from .env
HOST = "localhost"
USER = "root"
PASS = "Sai@1234"
DB_NAME = "paper_trading"

try:
    conn = pymysql.connect(host=HOST, user=USER, password=PASS, database=DB_NAME)
    cursor = conn.cursor()
    
    # 1. Add order_id column
    try:
        print("Attempting to add 'order_id' column...")
        cursor.execute("ALTER TABLE trades ADD COLUMN order_id INT NOT NULL AFTER user_id;")
        print("✅ Added 'order_id' column.")
    except Exception as e:
        print(f"⚠️ Add Column Error (might exist): {e}")

    # 2. Add Foreign Key
    try:
        print("Attempting to add FK constraint...")
        cursor.execute("ALTER TABLE trades ADD CONSTRAINT fk_trades_orders FOREIGN KEY (order_id) REFERENCES orders(id);")
        print("✅ Added FK constraint.")
    except Exception as e:
        print(f"⚠️ Add FK Error: {e}")

    conn.commit()
    conn.close()
    print("Migration attempt complete.")

except Exception as e:
    print(f"Connection Error: {e}")
