import csv
import gzip
import io
import logging
import httpx
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger("api.instrument_manager")

class InstrumentManager:
    _instance = None
    
    def __init__(self):
        # Data Structures
        self.underlying_map: Dict[str, str] = {}  # "NIFTY 50" -> "NSE_INDEX|Nifty 50"
        self.reverse_underlying_map: Dict[str, str] = {} # "NSE_INDEX|Nifty 50" -> "NIFTY 50"
        
        self.option_chain_map: Dict[str, Dict[str, Dict[float, Dict[str, dict]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        self.token_map = {} # instrument_key -> details
        self.name_to_symbol = {} # name -> symbol (Debug/Helper)
        
        # Hardcoded aliases to link Instrument Key -> Name used in Option Chain Map
        # CSV processing uses the 'name' column (e.g. "Nifty 50") as the key for indices.
        # So we must map "NSE_INDEX|Nifty 50" -> "Nifty 50"
        self.symbol_alias_map = {
            "Nifty 50": "NSE_INDEX|Nifty 50",
            "NIFTY 50": "NSE_INDEX|Nifty 50",
            "NIFTY": "NSE_INDEX|Nifty 50",
            
            "Nifty Bank": "NSE_INDEX|Nifty Bank",
            "NIFTY BANK": "NSE_INDEX|Nifty Bank",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            
            "Nifty Fin Service": "NSE_INDEX|Nifty Fin Service",
            "NIFTY FIN SERVICE": "NSE_INDEX|Nifty Fin Service",
            "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
            
            "Nifty Midcap Select": "NSE_INDEX|Nifty Midcap Select",
            "MIDCPNIFTY": "NSE_INDEX|Nifty Midcap Select"
        }
        
        self.expiry_dates: Dict[str, set] = defaultdict(set)
        self.is_loaded = False
        self.last_updated = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = InstrumentManager()
        return cls._instance

    async def initialize(self):
        """Downloads and processes the instrument master file."""
        logger.info("Starting Instrument Master download...")
        url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Use streaming to avoid loading full decompression into memory
                # response.content is bytes. We wrap in BytesIO and use gzip.open
                import io
                import gzip
                
                # Reset Maps First
                self.underlying_map = {}
                self.reverse_underlying_map = {}
                self.option_chain_map = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
                self.token_map = {}
                self.expiry_dates = defaultdict(set)
                self.strike_steps = {}
                self.name_to_symbol = {}
                self._temp_strikes = defaultdict(set)
                
                logger.info("Processing CSV content (Streaming)...")
                
                # Pass 1: Indices & Equities (Names)
                # We need to read twice? Or store mapping?
                # Streaming twice is safer for memory than storing rows.
                
                # WRAPPER for re-readability if needed? But response.content is waiting.
                # Actually, BytesIO allows seek(0).
                
                with io.BytesIO(response.content) as bio:
                     # Pass 1
                     with gzip.open(bio, mode='rt', encoding='utf-8') as f:
                         reader = csv.DictReader(f)
                         for row in reader:
                             self._process_row_pass_1(row)
                             
                     # Reset stream for Pass 2
                     bio.seek(0)
                     
                     # Pass 2: Options
                     with gzip.open(bio, mode='rt', encoding='utf-8') as f:
                         reader = csv.DictReader(f)
                         count_fo = 0
                         for row in reader:
                             if self._process_row_pass_2(row):
                                 count_fo += 1

                # Post-Process: Calculate Strike Steps
                for symbol, strikes in self._temp_strikes.items():
                    if len(strikes) > 1:
                        sorted_strikes = sorted(list(strikes))
                        min_diff = float('inf')
                        for i in range(1, len(sorted_strikes)):
                            diff = sorted_strikes[i] - sorted_strikes[i-1]
                            if diff > 0 and diff < min_diff:
                                min_diff = diff
                        self.strike_steps[symbol] = min_diff

                # FREEZE MAPS: Convert defaultdict to dict to prevent memory leak via accidental key creation
                logger.info("Optimizing memory: Freezing option chain map...")
                frozen_map = {}
                for sym, exp_map in self.option_chain_map.items():
                    frozen_exp = {}
                    for exp, strike_map in exp_map.items():
                        frozen_strike = {}
                        for strike, type_map in strike_map.items():
                             frozen_strike[strike] = dict(type_map)
                        frozen_exp[exp] = frozen_strike
                    frozen_map[sym] = frozen_exp
                
                self.option_chain_map = frozen_map
                
                # Cleanup
                del self._temp_strikes
                del self.name_to_symbol # Cleanup helper

                self.is_loaded = True
                self.last_updated = datetime.now()
                logger.info(f"Instrument Master loaded successfully. {len(self.underlying_map)} underlyings mapped.")
                logger.debug(f"Loaded expiry keys: {list(self.expiry_dates.keys())}")

        except Exception as e:
            logger.exception("Failed to load instrument master")
            
    def _process_row_pass_1(self, row):
        exchange = row.get("exchange")
        name = row.get("name")
        trading_symbol = row.get("tradingsymbol")
        instrument_key = row.get("instrument_key")
        
        if not name: return
        # logger.debug(f"PASS 1: Processing {name} ({exchange})")
        
        if exchange == "NSE_INDEX":
            # Index Name: "Nifty 50" -> Key: "NSE_INDEX|Nifty 50"
            friendly_name = name 
            
            # STANDARDISATION: Force common indices to their Option Symbol counterparts
            if name == "Nifty 50": friendly_name = "NIFTY"
            elif name == "Nifty Bank": friendly_name = "BANKNIFTY"
            elif name == "Nifty Fin Service": friendly_name = "FINNIFTY"
            
            self.underlying_map[friendly_name] = instrument_key
            self.reverse_underlying_map[instrument_key] = friendly_name
            
            # Map BOTH the original name and standardized name to the resolved symbol
            self.name_to_symbol[name] = friendly_name
            self.name_to_symbol[friendly_name] = friendly_name
            
        elif exchange == "NSE_EQ":
            # Stock Name: "HDFC BANK LTD" -> Symbol: "HDFCBANK"
            self.underlying_map[trading_symbol] = instrument_key
            self.reverse_underlying_map[instrument_key] = trading_symbol
            self.name_to_symbol[name] = trading_symbol

    def _process_row_pass_2(self, row):
         try:
             exchange = row.get("exchange")
             if exchange != "NSE_FO": return False
             
             instrument_type = row.get("instrument_type")
             if instrument_type not in ["OPTIDX", "OPTSTK"]: return False
             
             name = row.get("name")
             underlying_symbol = self.name_to_symbol.get(name)
             # logger.debug(f"PASS 2: {name} -> Resolved: {underlying_symbol}")
             
             if not underlying_symbol:
                 if instrument_type == "OPTIDX":
                     underlying_symbol = name
                 else:
                     return False
             
             expiry = row.get("expiry") 
             strike = row.get("strike")
             option_type = row.get("option_type") 
             lot_size = row.get("lot_size")
             instrument_key = row.get("instrument_key")
             trading_symbol = row.get("tradingsymbol")
             
             if strike and expiry:
                try:
                    strike_price = float(strike)
                    item = {
                        "instrument_key": instrument_key,
                        "trading_symbol": trading_symbol,
                        "lot_size": int(float(lot_size)) if lot_size else 0,
                        "name": name,
                        "expiry": expiry
                    }
                    
                    self.option_chain_map[underlying_symbol][expiry][strike_price][option_type] = item
                    self.expiry_dates[underlying_symbol].add(expiry)
                    self._temp_strikes[underlying_symbol].add(strike_price)
                    
                    # Store in token map
                    self.token_map[instrument_key] = {
                        "strike": strike_price,
                        "option_type": option_type,
                        "expiry": expiry,
                        "name": name
                    }
                    return True
                except ValueError:
                    pass
         except Exception:
             pass
         return False

    # OLD METHODS REPLACED BY ABOVE - KEEPING EMPTY FOR STRUCTURE MATCH
    def _process_csv(self, content: str):
         # This method is simulated for testing or if needed for non-gzip flow
         # It replicates the 2-pass logic on string content
         
         # Note: This implementation below is what the test expects 
         # but for production it uses initialize() with streaming.
         # Ideally we should route this to pass 1 and pass 2 helpers.
         
         if not content: return
         
         rows = []
         reader = csv.DictReader(io.StringIO(content))
         # We need to listify to iterate twice, or just re-read?
         # Since this is "process_csv" for string, we can listify.
         rows = list(reader)
         
         # Pass 1
         for row in rows:
             self._process_row_pass_1(row)
             
         # Pass 2
         count_fo = 0
         # We need to re-initialize temp structures here if not called via initialize
         if not hasattr(self, "_temp_strikes"):
              self._temp_strikes = defaultdict(set)
              self.strike_steps = {}

         for row in rows:
             if self._process_row_pass_2(row):
                 count_fo += 1
                 
         # Post-Process
         for symbol, strikes in self._temp_strikes.items():
            if len(strikes) > 1:
                sorted_strikes = sorted(list(strikes))
                min_diff = float('inf')
                for i in range(1, len(sorted_strikes)):
                    diff = sorted_strikes[i] - sorted_strikes[i-1]
                    if diff > 0 and diff < min_diff:
                        min_diff = diff
                self.strike_steps[symbol] = min_diff

         if len(self.token_map) > 0:
              logger.info(f"Token Map populated. Size: {len(self.token_map)}")
         else:
              logger.error("Token Map is EMPTY after processing!")

         logger.info(f"Processed {len(self.underlying_map)} underlyings and {count_fo} options.")

    def get_strike_step(self, underlying_key: str) -> float:
        symbol = self._resolve_to_option_symbol(underlying_key)
        # Default fallbacks if detection failed
        default_step = 50.0 
        if "Sensex" in underlying_key: default_step = 100.0
        
        return self.strike_steps.get(symbol, default_step)

    def search_underlying(self, query: str) -> List[dict]:
        """Simple prefix search for underlyings. Returns ONLY F&O enabled instruments."""
        query = query.upper()
        results = []
        seen_keys = set()
        
        # 1. INDICES - Search in underlying_map for NSE_INDEX entries
        for friendly_name, instrument_key in self.underlying_map.items():
            if "NSE_INDEX|" in instrument_key:
                # This is an index
                # Check if query matches friendly_name (e.g., "NIFTY") or the index name in key
                if query in friendly_name.upper():
                    # Verify it has options (expiry dates)
                    if friendly_name in self.expiry_dates:
                        if instrument_key not in seen_keys:
                            results.append({"name": friendly_name, "key": instrument_key, "type": "INDEX"})
                            seen_keys.add(instrument_key)
        
        # 2. STOCKS - Search in underlying_map for NSE_EQ entries
        count = 0
        for trading_symbol, instrument_key in self.underlying_map.items():
            if "NSE_EQ|" in instrument_key:
                # This is a stock
                if query in trading_symbol.upper():
                    # Verify it has options (expiry dates)
                    if trading_symbol in self.expiry_dates:
                        if instrument_key not in seen_keys:
                            results.append({"name": trading_symbol, "key": instrument_key, "type": "STOCK"})
                            seen_keys.add(instrument_key)
                            count += 1
                            
            if count > 20: break
            
        return results

    def get_expiry_dates(self, underlying_symbol_or_key: str) -> List[str]:
        symbol = self._resolve_to_option_symbol(underlying_symbol_or_key)
        dates = list(self.expiry_dates.get(symbol, set()))
        
        # Sort by Date
        try:
            dates.sort(key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
        except ValueError:
            dates.sort() 
            
        return dates

    def get_option_chain(self, underlying_key: str, expiry: str, center_strike: float, count: int = 10):
        symbol = self._resolve_to_option_symbol(underlying_key)
        
        # DEBUG LOGGING
        logger.debug(f"Fetching chain for {symbol} (Key: {underlying_key}) Expiry: {expiry}")
        
        if symbol not in self.option_chain_map:
            logger.warning(f"Symbol {symbol} not found in option chain map.")
            return []
            
        if expiry not in self.option_chain_map[symbol]:
            logger.warning(f"Expiry {expiry} not found for {symbol}")
            return []
            
        all_strikes = sorted(self.option_chain_map[symbol][expiry].keys())
        
        if not all_strikes: return []
        
        # Find index of nearest strike
        nearest_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - center_strike))
        
        start_idx = max(0, nearest_idx - count)
        end_idx = min(len(all_strikes), nearest_idx + count + 1)
        
        selected_strikes = all_strikes[start_idx:end_idx]
        
        result = []
        for strike in selected_strikes:
            data = self.option_chain_map[symbol][expiry][strike]
            
            ce_data = data.get("CE", {})
            pe_data = data.get("PE", {})
            
            result.append({
                "strike_price": strike,
                "call_options": ce_data,
                "put_options": pe_data
            })
            
        return result

    def _resolve_to_option_symbol(self, key_or_name: str) -> str:
        # Helper to convert "NSE_INDEX|Nifty 50" -> "NIFTY"
        # Or "NSE_EQ|..." -> "RELIANCE"
        
        # 1. Try to find name in underlying map reverse (Dynamic/Loaded Data)
        # If we stored trading symbol in reverse map:
        if key_or_name in self.reverse_underlying_map:
            return self.reverse_underlying_map[key_or_name]
        
        # 2. Check alias map reverse (Static/Fallback)
        for sym, key in self.symbol_alias_map.items():
            if key == key_or_name:
                return sym
            # Partial match for friendly names (e.g. "Nifty 50" matching "NSE_INDEX|Nifty 50")
            if "|" in key and key.split("|")[1] == key_or_name:
                return sym
                
        # 3. Check if it looks like a symbol already (no pipe)
        if "|" not in key_or_name:
            return key_or_name
            
        return key_or_name

    def resolve_instrument_key(self, alias_or_key: str) -> str:
        """
        Resolves a user-friendly alias (e.g. 'BANKNIFTY', 'Nifty Bank') 
        to the full instrument key (e.g. 'NSE_INDEX|Nifty Bank').
        """
        # 1. Check if it's already a key (has pipe)
        if "|" in alias_or_key:
            return alias_or_key
            
        # 2. Check Static Alias Map
        if alias_or_key in self.symbol_alias_map:
            return self.symbol_alias_map[alias_or_key]
            
        # 3. Check Underlying Map (Name -> Key)
        if alias_or_key in self.underlying_map:
            return self.underlying_map[alias_or_key]
            
        # 4. Try Case-Insensitive Lookup
        upper_key = alias_or_key.upper()
        
        # Check aliases
        for k, v in self.symbol_alias_map.items():
            if k.upper() == upper_key:
                return v
                
        # Check underlying map
        for k, v in self.underlying_map.items():
            if k.upper() == upper_key:
                return v
                
        # Return original if no match found (fallback)
        return alias_or_key

    def get_instrument_details(self, instrument_key: str):
        return self.token_map.get(instrument_key)

    async def cleanup_cache(self):
        """
        Force cleanup of any temporary structures. 
        Since option_chain_map is now frozen, we just ensure no other artifacts remain.
        """
        import gc
        logger.info("Running InstrumentManager cache cleanup...")
        if hasattr(self, "_temp_strikes"):
            del self._temp_strikes
        
        # Force garbage collection for any dropped large objects (like the CSV buffer)
        gc.collect()
        
    def get_debug_stats(self):
        return {
            "is_loaded": self.is_loaded,
            "last_updated": self.last_updated,
            "underlying_count": len(self.underlying_map),
            "expiry_keys": list(self.expiry_dates.keys()),
            "alias_map_keys": list(self.symbol_alias_map.keys()),
            "sample_underlying": list(self.underlying_map.items())[:5],
            "sample_reverse": list(self.reverse_underlying_map.items())[:5]
        }

# Global Accessor
instrument_manager = InstrumentManager.get_instance()
