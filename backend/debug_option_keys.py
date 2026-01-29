import asyncio
import sys
import os
sys.path.append(os.getcwd())
from instrument_manager import instrument_manager

async def main():
    print("Loading Instrument Manager...")
    await instrument_manager.initialize()
    
    symbol = "NIFTY"
    expiry = instrument_manager.get_expiry_dates(symbol)[0]
    print(f"Expiry: {expiry}")
    
    chain = instrument_manager.get_option_chain("NSE_INDEX|Nifty 50", expiry, 25000, count=2)
    
    print(f"Chain Rows: {len(chain)}")
    if chain:
        row = chain[0]
        print("--- CE ---")
        print(f"Key: {row['call_options']['instrument_key']}")
        print(f"Symbol: {row['call_options']['trading_symbol']}")
        print("--- PE ---")
        print(f"Key: {row['put_options']['instrument_key']}")
        print(f"Symbol: {row['put_options']['trading_symbol']}")

if __name__ == "__main__":
    asyncio.run(main())
