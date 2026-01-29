
import asyncio
import logging
import sys
import os

# Setup path
sys.path.append(os.getcwd())

# Logging
logging.basicConfig(level=logging.INFO)

from backend.instrument_manager import instrument_manager

async def debug():
    print("--- Initializing Instrument Manager ---")
    await instrument_manager.initialize()
    print(f"Loaded: {instrument_manager.is_loaded}")
    
    # 1. Check NIFTY
    key_nifty = "NSE_INDEX|Nifty 50"
    symbol_nifty = instrument_manager._resolve_to_option_symbol(key_nifty)
    print(f"\n[NIFTY] Key: {key_nifty} -> Symbol: {symbol_nifty}")
    expiries = instrument_manager.get_expiry_dates(key_nifty)
    print(f"Expiries for NIFTY: {expiries}")
    
    # 2. Check HDFCBANK 
    # (We need the correct instrument key for HDFCBANK, searching for it first)
    print("\n[HDFCBANK] Searching for HDFCBANK...")
    results = instrument_manager.search_underlying("HDFCBANK")
    if results:
        hdfc = results[0]
        print(f"Found: {hdfc}")
        key_hdfc = hdfc['key']
        symbol_hdfc = instrument_manager._resolve_to_option_symbol(key_hdfc)
        print(f"Key: {key_hdfc} -> Symbol: {symbol_hdfc}")
        expiries_stock = instrument_manager.get_expiry_dates(key_hdfc)
        print(f"Expiries for HDFCBANK: {expiries_stock}")
    else:
        print("HDFCBANK not found in search!")
        
    print("\n--- Map sizes ---")
    print(f"Underlying Map: {len(instrument_manager.underlying_map)}")
    print(f"Option Chain Keys: {len(instrument_manager.option_chain_map.keys())}")
    print(f"Option Chain Keys Sample: {list(instrument_manager.option_chain_map.keys())[:10]}")

if __name__ == "__main__":
    asyncio.run(debug())
