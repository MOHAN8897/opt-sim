
import asyncio
import logging
import sys
import os

# Adjust path to find backend modules
sys.path.append(os.getcwd())

from backend.instrument_manager import instrument_manager, InstrumentManager

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_script")

async def test_lookup():

    with open("debug_output.txt", "w", encoding="utf-8") as f:
        try:
             print("Initializing InstrumentManager...")
             await instrument_manager.initialize()
        except Exception as e:
             import traceback
             f.write(f"Initialization FAILED: {e}\n")
             f.write(traceback.format_exc())
             f.write("\n")
             
        f.write(f"InstrumentManager Loaded: {instrument_manager.is_loaded}\n")
        
        # Test keys from the user logs
        test_keys = [
            "NSE_FO|58664", 
            "NSE_FO|58666", 
            "NSE_FO|58665", 
            "NSE_FO|58611",
            "NSE_FO|NIFTY26JAN25050CE" 
        ]
        
        f.write("\n--- Testing Lookups ---\n")
        for key in test_keys:
            details = instrument_manager.get_instrument_details(key)
            f.write(f"Key: {key} -> Details: {details}\n")
            
        f.write(f"\nUnderlying Lookup 'NSE_INDEX|Nifty 50': {instrument_manager.reverse_underlying_map.get('NSE_INDEX|Nifty 50')}\n")
        f.write("DONE\n")
    
    print("Debug script finished. Check debug_output.txt")

if __name__ == "__main__":
    asyncio.run(test_lookup())
