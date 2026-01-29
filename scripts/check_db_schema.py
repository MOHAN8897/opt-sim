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
    
    # Check TRADES table columns
    cursor.execute("DESCRIBE trades;")
    columns = cursor.fetchall()
    
    print("\n[TRADES TABLE SCHEMA]")
    found_order_id = False
    for col in columns:
        print(col)
        if col[0] == 'order_id':
            found_order_id = True
            
    if not found_order_id:
        print("\n❌ CRITICAL: 'order_id' column MISSING in trades table!")
    else:
        print("\n✅ 'order_id' column matches.")

    # Check ORDERS table just in case
    cursor.execute("DESCRIBE orders;")
    columns = cursor.fetchall()
    print("\n[ORDERS TABLE SCHEMA]")
    for col in columns:
        print(col)

    conn.close()

except Exception as e:
    print(f"Error: {e}")
