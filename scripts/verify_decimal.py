from decimal import Decimal

# Mock Market Data (String format from Redis)
md = {
    "ltp": "24350.55",
    "bid": "24350.00",
    "ask": "24351.00",
    "bid_qty": "500",
    "ask_qty": "500"
}

# Emulate Execution Engine Logic
try:
    if not md:
        print("FAIL: No MD")
        exit(1)
        
    current_ltp = Decimal(str(md.get('ltp', 0)))
    if current_ltp == 0:
        print("FAIL: LTP is 0")
        exit(1)
        
    bid = Decimal(str(md.get('bid', 0)))
    ask = Decimal(str(md.get('ask', 0)))
    
    print(f"SUCCESS: Parsed Decimals -> LTP={current_ltp} Bid={bid} Ask={ask}")
    
    # Test Arithmetic
    spread = ask - bid
    print(f"Spread: {spread} (Type: {type(spread)})")
    
except Exception as e:
    print(f"FAIL: Exception: {e}")
