"""
Comprehensive Market Data Fetcher
Optimized to fetch Option Chain details (LTP, OI, IV, Greeks) from Upstox APIs
Works seamlessly for both MARKET OPEN and MARKET CLOSED scenarios

Uses Priority-Based Endpoint Selection:
- Market OPEN: Prefers live endpoints (/v3/market-quote/option-greek for Greeks)
- Market CLOSED: Uses persisted endpoints (/v2/market-quote/full for last session data)

📌 API ENDPOINT REFERENCE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data Type                Endpoint (Market OPEN)              Endpoint (Market CLOSED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LTP (Last Price)         /v3/market-quote/ltp               /v2/market-quote/ohlc (close)
OI (Open Interest)       /v2/market-quote/full              /v2/market-quote/full (persists)
IV (Implied Volatility)  /v3/market-quote/option-greek      /v2/market-quote/full (0 when closed)
Greeks (Δ,Γ,Θ,Ν)       /v3/market-quote/option-greek      N/A (zeros when market closed)
Option Chain             /v2/option/chain                   /v2/option/chain
Historical Candles       /v2/historical-candle/...          /v2/historical-candle/...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import httpx
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger("api.market_data_fetcher")


@dataclass
class QuoteData:
    """Unified quote data structure for both market states"""
    ltp: float = 0.0                    # Last Traded Price
    volume: int = 0                     # Volume
    oi: int = 0                         # Open Interest
    iv: float = 0.0                     # Implied Volatility (%)
    delta: float = 0.0                  # Greek
    gamma: float = 0.0                  # Greek
    theta: float = 0.0                  # Greek
    vega: float = 0.0                   # Greek
    bid: float = 0.0                    # Bid Price
    ask: float = 0.0                    # Ask Price
    bid_quantity: int = 0               # Bid Quantity
    ask_quantity: int = 0               # Ask Quantity
    previous_close: float = 0.0         # Previous close price
    timestamp: Optional[str] = None     # Last trade timestamp
    market_status: str = "UNKNOWN"      # OPEN / CLOSED
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "ltp": self.ltp,
            "volume": self.volume,
            "oi": self.oi,
            "iv": self.iv,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "bid": self.bid,
            "ask": self.ask,
            "bid_quantity": self.bid_quantity,
            "ask_quantity": self.ask_quantity,
            "previous_close": self.previous_close,
            "timestamp": self.timestamp,
            "market_status": self.market_status,
        }


class MarketDataFetcher:
    """
    Unified market data fetcher optimizing API calls for market state
    """
    
    def __init__(self, access_token: str, timeout: float = 10.0):
        self.access_token = access_token
        self.timeout = timeout
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
    
    def _build_client(self) -> httpx.AsyncClient:
        """Build HTTP client with timeout"""
        return httpx.AsyncClient(timeout=self.timeout)
    
    async def get_spot_price(self, instrument_key: str) -> Tuple[float, str]:
        """
        Fetch spot (underlying) price with automatic fallback for market-closed
        
        Returns: (price, market_status)
        market_status: "OPEN", "CLOSED", or "UNKNOWN"
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 [SPOT PRICE] Fetching spot price for {instrument_key}")
        logger.info(f"{'='*80}")
        
        async with self._build_client() as client:
            # PRIMARY: /v2/market-quote/ltp (official recommended endpoint - works during market hours AND after market close)
            try:
                logger.debug(f"  ➊ PRIMARY: /v2/market-quote/ltp (official Upstox endpoint)")
                resp = await client.get(
                    "https://api.upstox.com/v2/market-quote/ltp",
                    headers=self.headers,
                    params={"instrument_key": instrument_key}
                )
                
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get(instrument_key, {})
                    price = data.get("last_price", 0)
                    
                    if price > 0:
                        logger.info(f"     ✅ LTP = {price} from /v2/market-quote/ltp (LAST SPOT PRICE)")
                        return price, "OPEN"
                    else:
                        logger.debug(f"     ⚠️  LTP returned 0 → trying fallback")
                
                elif resp.status_code == 401:
                    raise ValueError("401 Unauthorized - Token expired")
                else:
                    logger.warning(f"     ❌ /v2/market-quote/ltp HTTP {resp.status_code}")
            
            except Exception as e:
                logger.warning(f"     ❌ PRIMARY failed: {e}")
            
            # FALLBACK 1: /v2/market-quote/full (BEST for closed market - returns last_traded_price)
            try:
                logger.debug(f"  ➋ FALLBACK 1: /v2/market-quote/full (best for closed market)")
                resp = await client.get(
                    "https://api.upstox.com/v2/market-quote/full",
                    headers=self.headers,
                    params={"instrument_key": instrument_key}
                )
                
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get(instrument_key, {})
                    # Use last_traded_price (better for closed market) or close as fallback
                    price = data.get("last_traded_price", 0) or data.get("close", 0)
                    
                    if price > 0:
                        logger.info(f"     ✅ Last Traded Price = {price} from /v2/market-quote/full (MARKET CLOSED)")
                        return price, "CLOSED"
                    else:
                        logger.debug(f"     ⚠️  /full returned 0, trying OHLC")
                
                elif resp.status_code == 401:
                    raise ValueError("401 Unauthorized - Token expired")
                else:
                    logger.warning(f"     ❌ /full HTTP {resp.status_code}")
            
            except Exception as e:
                logger.warning(f"     ❌ FALLBACK 1 failed: {e}")
            
            # FALLBACK 2: /v2/market-quote/ohlc (previous day close)
            try:
                logger.debug(f"  ➌ FALLBACK 2: /v2/market-quote/ohlc")
                resp = await client.get(
                    "https://api.upstox.com/v2/market-quote/ohlc",
                    headers=self.headers,
                    params={
                        "instrument_key": instrument_key,
                        "interval": "1d"
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get(instrument_key, {})
                    ohlc = data.get("ohlc", {})
                    price = ohlc.get("close", 0)
                    
                    if price > 0:
                        logger.info(f"     ✅ OHLC Close = {price} from /v2 (MARKET CLOSED)")
                        return price, "CLOSED"
                
                elif resp.status_code == 401:
                    raise ValueError("401 Unauthorized - Token expired")
                else:
                    logger.warning(f"     ❌ /ohlc HTTP {resp.status_code}")
            
            except Exception as e:
                logger.warning(f"     ❌ FALLBACK 2 failed: {e}")
            
            # FALLBACK 3: /v2/historical-candle (most recent candle close)
            try:
                logger.debug(f"  ➍ FALLBACK 3: /v2/historical-candle")
                today = datetime.now().strftime("%Y-%m-%d")
                from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                
                resp = await client.get(
                    f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{today}/{from_date}",
                    headers={"accept": "application/json"}
                )
                
                if resp.status_code == 200:
                    candles = resp.json().get("data", {}).get("candles", [])
                    if candles and len(candles) > 0:
                        # Format: [timestamp, open, high, low, close, volume, oi]
                        price = candles[-1][4] if len(candles[-1]) >= 5 else 0
                        
                        if price > 0:
                            logger.info(f"     ✅ Historical Close = {price} from /historical-candle (LAST TRADING DAY)")
                            return price, "CLOSED"
                
                else:
                    logger.warning(f"     ❌ /historical-candle HTTP {resp.status_code}")
            
            except Exception as e:
                logger.warning(f"     ❌ FALLBACK 3 failed: {e}")
            
            logger.error(f"❌ [SPOT PRICE] FAILED: Could not determine spot price via any endpoint")
            logger.info(f"{'='*80}\n")
            return 0.0, "UNKNOWN"
    
    async def get_quotes_batch(
        self, 
        instrument_keys: List[str],
        market_status: str = "UNKNOWN"
    ) -> Dict[str, QuoteData]:
        """
        Fetch batch quotes with intelligent endpoint selection
        
        🔴 RACE CONDITION FIX 🔴
        Market status is determined at START of request.
        If market closes DURING the request:
        - /v3/market-quote/option-greek may return stale data
        - /v2/market-quote/full will return correct last-session data
        
        Solution: Use /v2/market-quote/full as DEFAULT when uncertain
        Only use /v3 when CONFIRMED market is OPEN
        
        Args:
            instrument_keys: List of option instrument keys
            market_status: "OPEN", "CLOSED", or "UNKNOWN"
        
        Returns:
            Dict mapping instrument_key -> QuoteData
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 [BATCH QUOTES] Fetching {len(instrument_keys)} options (Status: {market_status})")
        logger.info(f"{'='*80}")
        
        if not instrument_keys:
            logger.warning(f"     ⚠️  No instrument keys provided")
            return {}
        
        quote_map = {}
        batch_size = 50  # Upstox limit
        
        async with self._build_client() as client:
            # AUTO-DETECT market status if unknown
            if market_status == "UNKNOWN":
                # Try to fetch one instrument with BOTH endpoints to determine status safely
                try:
                    logger.debug(f"     🔍 Auto-detecting market status...")
                    test_resp = await client.get(
                        "https://api.upstox.com/v3/market-quote/option-greek",
                        headers=self.headers,
                        params={"instrument_key": instrument_keys[0]}
                    )
                    if test_resp.status_code == 200:
                        test_data = test_resp.json().get("data", {}).get(instrument_keys[0], {})
                        # Check multiple indicators to avoid race condition
                        has_live_greeks = test_data.get("iv", 0) > 0
                        has_greeks_values = (
                            test_data.get("delta", 0) != 0 or 
                            test_data.get("gamma", 0) != 0 or
                            test_data.get("vega", 0) != 0
                        )
                        
                        if has_live_greeks and has_greeks_values:
                            market_status = "OPEN"
                            logger.info(f"     ✅ Market OPEN (IV={test_data.get('iv', 0):.2f}, Delta={test_data.get('delta', 0):.2f})")
                        else:
                            market_status = "CLOSED"
                            logger.info(f"     ⚠️  Market CLOSED (IV=0, Greeks=0)")
                    else:
                        market_status = "CLOSED"
                        logger.debug(f"     ⚠️  Test endpoint returned {test_resp.status_code} → defaulting to CLOSED")
                except Exception as e:
                    market_status = "CLOSED"
                    logger.warning(f"     ❌ Auto-detect failed: {e} → defaulting to CLOSED")
            
            # SMART ENDPOINT SELECTION
            # ⭐ PREFERENCE: When in doubt, use /v2 (safer for market-closed)
            if market_status == "OPEN":
                logger.info(f"     📡 Using /v3/market-quote/option-greek (live Greeks)")
                await self._fetch_quotes_with_greeks(client, instrument_keys, quote_map, batch_size)
            else:
                logger.info(f"     📡 Using /v2/market-quote/full (persisted data)")
                await self._fetch_quotes_full(client, instrument_keys, quote_map, batch_size)
        
        logger.info(f"     ✅ Total fetched: {len(quote_map)}/{len(instrument_keys)} quotes")
        
        # 🔴 RACE CONDITION CHECK 🔴
        # If we detected OPEN but got mostly zeros, market may have closed mid-request
        zero_count = sum(1 for q in quote_map.values() if q.iv == 0 and q.delta == 0)
        total_count = len(quote_map)
        
        if market_status == "OPEN" and total_count > 0:
            zero_ratio = zero_count / total_count
            if zero_ratio > 0.7:  # More than 70% have zero Greeks
                logger.warning(f"⚠️  RACE CONDITION DETECTED!")
                logger.warning(f"     {zero_count}/{total_count} quotes ({zero_ratio*100:.0f}%) have IV=0 & Delta=0")
                logger.warning(f"     Market likely closed mid-request → re-marking all as CLOSED")
                # Re-mark all quotes as closed since we're seeing zeros
                for key in quote_map:
                    quote_map[key].market_status = "CLOSED"
        
        logger.info(f"{'='*80}\n")
        return quote_map
    
    async def _fetch_quotes_with_greeks(
        self,
        client: httpx.AsyncClient,
        instrument_keys: List[str],
        quote_map: Dict[str, QuoteData],
        batch_size: int
    ):
        """Fetch quotes using /v3/market-quote/option-greek (market OPEN)"""
        logger.info(f"     📡 /v3/market-quote/option-greek endpoint (MARKET OPEN - includes Greeks)")
        
        batches = [instrument_keys[i:i + batch_size] for i in range(0, len(instrument_keys), batch_size)]
        logger.debug(f"     Batch count: {len(batches)} (batch size: {batch_size})")
        
        for batch_idx, batch in enumerate(batches):
            keys_str = ",".join(batch)
            logger.debug(f"        Batch {batch_idx + 1}/{len(batches)}: {len(batch)} options")
            
            try:
                resp = await client.get(
                    "https://api.upstox.com/v3/market-quote/option-greek",
                    headers=self.headers,
                    params={"instrument_key": keys_str}
                )
                
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    logger.info(f"        ✅ Batch {batch_idx + 1}: {len(data)} quotes (LTP, OI, IV, Greeks)")
                    
                    # Log first quote as sample
                    if data:
                        first_key = list(data.keys())[0]
                        first_val = data[first_key]
                        logger.debug(f"           Sample: LTP={first_val.get('last_price', 0)}, OI={first_val.get('oi', 0)}, IV={first_val.get('iv', 0):.2f}, Δ={first_val.get('delta', 0):.2f}")
                    
                    for key, val in data.items():
                        quote_map[key] = QuoteData(
                            ltp=val.get("last_price", 0),
                            volume=val.get("volume", 0),
                            oi=val.get("oi", 0),
                            iv=val.get("iv", 0),                    # ⭐ Live Greeks
                            delta=val.get("delta", 0),
                            gamma=val.get("gamma", 0),
                            theta=val.get("theta", 0),
                            vega=val.get("vega", 0),
                            bid=val.get("bid", 0),
                            ask=val.get("ask", 0),
                            previous_close=val.get("cp", 0),
                            timestamp=val.get("timestamp", None),
                            market_status="OPEN"
                        )
                
                elif resp.status_code == 401:
                    raise ValueError("401 Unauthorized - Token expired")
                else:
                    logger.warning(f"        ❌ Batch {batch_idx + 1}: HTTP {resp.status_code}")
            
            except Exception as e:
                logger.error(f"        ❌ Batch {batch_idx + 1}: {e}")
    
    async def _fetch_quotes_full(
        self,
        client: httpx.AsyncClient,
        instrument_keys: List[str],
        quote_map: Dict[str, QuoteData],
        batch_size: int
    ):
        """Fetch quotes using /v2/market-quote/full (market CLOSED or fallback)"""
        logger.info(f"     📡 /v2/market-quote/full endpoint (MARKET CLOSED - persisted data)")
        
        batches = [instrument_keys[i:i + batch_size] for i in range(0, len(instrument_keys), batch_size)]
        logger.debug(f"     Batch count: {len(batches)} (batch size: {batch_size})")
        
        for batch_idx, batch in enumerate(batches):
            keys_str = ",".join(batch)
            logger.debug(f"        Batch {batch_idx + 1}/{len(batches)}: {len(batch)} options")
            
            try:
                resp = await client.get(
                    "https://api.upstox.com/v2/market-quote/full",
                    headers=self.headers,
                    params={"instrument_key": keys_str}
                )
                
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    logger.info(f"  Batch {batch_idx + 1}: {len(data)} quotes received")
                    
                    for key, val in data.items():
                        # /full endpoint persists last_traded_price even when market closed
                        ohlc = val.get("ohlc", {})
                        quote_map[key] = QuoteData(
                            ltp=val.get("last_traded_price", 0),        # ⭐ Persists when closed
                            volume=val.get("volume", 0),                # ⭐ Shows total volume
                            oi=val.get("oi", 0),                        # ⭐ Shows current OI
                            iv=0,                                       # /full doesn't have IV
                            delta=0,
                            gamma=0,
                            theta=0,
                            vega=0,
                            bid=val.get("bid", 0),
                            ask=val.get("ask", 0),
                            previous_close=val.get("cp", 0),
                            timestamp=val.get("last_trade_time", None),
                            market_status="CLOSED"
                        )
                
                elif resp.status_code == 401:
                    raise ValueError("401 Unauthorized - Token expired")
                else:
                    logger.warning(f"  Batch {batch_idx + 1}: HTTP {resp.status_code}")
            
            except Exception as e:
                logger.error(f"  Batch {batch_idx + 1} failed: {e}")
    
    async def get_option_chain_ltp_oi_iv(
        self,
        instrument_keys: List[str]
    ) -> Dict[str, QuoteData]:
        """
        BEST ENDPOINT FOR MARKET-CLOSED OPTION CHAIN DATA
        
        Fetches comprehensive option quotes including:
        - LTP (Last Traded Price)
        - OI (Open Interest)
        - IV (Implied Volatility) - when market open
        - Greeks - when market open
        
        Works for both market OPEN and CLOSED scenarios.
        
        Returns: Dict of instrument_key -> QuoteData
        """
        # First, determine market status from spot
        spot_price, market_status = await self.get_spot_price("NSE_INDEX|Nifty 50")
        
        # Then fetch quotes with smart endpoint selection
        return await self.get_quotes_batch(instrument_keys, market_status)
    
    async def get_option_ltp_only(
        self,
        instrument_keys: List[str]
    ) -> Dict[str, float]:
        """
        Quick fetch for just LTP (Last Traded Price)
        Best for UI updates that only need price
        
        Returns: Dict of instrument_key -> ltp
        """
        quotes = await self.get_quotes_batch(instrument_keys)
        return {k: v.ltp for k, v in quotes.items()}
    
    async def get_option_oi_iv_greeks(
        self,
        instrument_keys: List[str]
    ) -> Dict[str, QuoteData]:
        """
        Fetch OI, IV, and Greeks
        Respects market status - returns zeros for Greeks when market closed
        
        Returns: Dict of instrument_key -> QuoteData
        """
        return await self.get_quotes_batch(instrument_keys)


async def fetch_spot_ltp(access_token: str, instrument_key: str) -> Tuple[float, str]:
    """
    Utility function to fetch spot price only
    
    Returns: (price, market_status)
    """
    fetcher = MarketDataFetcher(access_token)
    return await fetcher.get_spot_price(instrument_key)


async def fetch_option_quotes_batch(
    access_token: str,
    instrument_keys: List[str]
) -> Dict[str, QuoteData]:
    """
    Utility function to fetch batch option quotes
    
    Automatically selects best endpoint based on market status
    - Market OPEN: Uses /v3/market-quote/option-greek (includes Greeks)
    - Market CLOSED: Uses /v2/market-quote/full (persists last session data)
    
    Returns: Dict of instrument_key -> QuoteData
    """
    fetcher = MarketDataFetcher(access_token)
    return await fetcher.get_quotes_batch(instrument_keys)
