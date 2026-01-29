from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .auth import get_current_user
from .models import User, UpstoxAccount, UpstoxStatus
from .broker import decrypt
from .instrument_manager import instrument_manager
from .logging_utils import log_api_call, log_batch_fetch, log_market_data, get_market_status_message
import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Set

# Configure Logger
logger = logging.getLogger("api.market")

router = APIRouter(prefix="/api/market", tags=["market"])

# Thread-safe set to track users whose tokens are being invalidated
# Prevents race condition where multiple API calls try to invalidate same token
_invalidation_in_progress: Set[int] = set()
_invalidation_lock = asyncio.Lock()

async def _invalidate_token(user: User, db: AsyncSession, retry_count: int = 0):
    """
    Mark token as expired in database when 401 error detected.
    Includes idempotency guards to prevent race conditions.
    
    Args:
        user: User whose token to invalidate
        db: Database session
        retry_count: Internal retry counter (for logging)
    """
    global _invalidation_in_progress, _invalidation_lock
    
    # Idempotency guard: Check if invalidation already in progress for this user
    async with _invalidation_lock:
        if user.id in _invalidation_in_progress:
            logger.warning(f"⚠️ Token invalidation already in progress for user {user.email} - skipping duplicate")
            return
        
        # Mark that we're processing this user
        _invalidation_in_progress.add(user.id)
    
    try:
        # Double-check: Verify token is actually invalid before proceeding
        stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if not account:
            logger.warning(f"No account found for user {user.email} during invalidation")
            return
        
        # Guard: If already marked as expired, skip
        if account.status == UpstoxStatus.TOKEN_EXPIRED:
            logger.info(f"✅ Token already marked as EXPIRED for user {user.email} - no action needed")
            return
        
        # Invalidate the token
        logger.error(f"🔴 Token invalidation for user {user.email} (attempt {retry_count + 1})")
        account.status = UpstoxStatus.TOKEN_EXPIRED
        account.access_token = None
        account.token_expiry = None
        await db.commit()
        logger.info(f"✅ Database updated: Token marked as EXPIRED for {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate token for user {user.email}: {e}")
    finally:
        # Always remove from in-progress set
        async with _invalidation_lock:
            _invalidation_in_progress.discard(user.id)

async def get_upstox_client(user: User, db: AsyncSession):
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account or account.status != UpstoxStatus.TOKEN_VALID:
        raise HTTPException(status_code=401, detail="Broker not connected")
        
    if not account.access_token:
        raise HTTPException(status_code=401, detail="No access token found")
        
    access_token = decrypt(account.access_token)
    return access_token

async def _fetch_with_retry(client: httpx.AsyncClient, url: str, headers: dict, params: dict, max_retries: int = 1, request_name: str = "API"):
    """
    Retry API call with exponential backoff before giving up.
    This prevents premature token invalidation due to transient network issues.
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"[{request_name}] Attempt {attempt + 1}/{max_retries + 1}")
            resp = await client.get(url, headers=headers, params=params)
            return resp  # Return response (caller handles status codes)
            
        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = 0.5 * (2 ** attempt)  # Exponential backoff
                logger.warning(f"[{request_name}] Timeout, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"[{request_name}] All attempts failed")
                raise
        except Exception as e:
            logger.error(f"[{request_name}] Unexpected error: {e}")
            raise
    
    if last_exception:
        raise last_exception

def is_market_open() -> bool:
    """Check if NSE market is currently open (Mon-Fri 9:15-15:30 IST)"""
    now = datetime.now()
    if now.weekday() >= 5:  # Weekend
        return False
    # Updated to 09:12 - 15:45 as per user request (Wait, reverting to 09:15-15:30 as per latest instruction)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= now <= market_close

@router.get("/search")
async def search_instruments(
    query: str,
    user: User = Depends(get_current_user)
):
    if not instrument_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Instrument Master loading...")
        
    results = instrument_manager.search_underlying(query)
    return results

@router.get("/expiry")
async def get_expiry_dates(
    instrument_key: str = Query(..., description="Underlying Instrument Key"),
    user: User = Depends(get_current_user)
):
    if not instrument_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Instrument Master loading...")
        
    dates = instrument_manager.get_expiry_dates(instrument_key)
    return {"expiry_dates": dates}

def _extract_data_ignore_key_format(response_data: dict, instrument_key: str):
    """
    Robust extraction of data from Upstox response.
    Handles mismatch between requested key (e.g. NSE_EQ|INE...) and returned key (e.g. NSE_EQ:SYMBOL).
    """
    data_map = response_data.get("data", {})
    if not data_map:
        return None

    # 1. Try exact match
    if instrument_key in data_map:
        return data_map[instrument_key]

    # 2. Try swapping separator '|' -> ':'
    alt_key = instrument_key.replace("|", ":")
    if alt_key in data_map:
        return data_map[alt_key]

    # 3. Try resolving ISIN to Symbol if possible
    # (This relies on instrument_manager being available globally)
    symbol = instrument_manager.reverse_underlying_map.get(instrument_key)
    if symbol:
        prefix = instrument_key.split("|")[0]
        symbol_key = f"{prefix}:{symbol}"
        if symbol_key in data_map:
            return data_map[symbol_key]
            
    # 4. If nothing works and there's only one key in data, assume it's the one we wanted
    # (This is safe only for single-request endpoints like get_spot_ltp)
    if len(data_map) == 1:
        return list(data_map.values())[0]
        
    return None

# Simple In-Memory Cache (Bounded)
# key -> (timestamp, data)
DATA_CACHE = {}
CACHE_TTL = 3.0 # seconds
MAX_CACHE_SIZE = 1000

def _cleanup_cache():
    """Start fresh if too big"""
    if len(DATA_CACHE) > MAX_CACHE_SIZE:
        DATA_CACHE.clear()

@router.get("/option-chain")
async def get_option_chain(
    instrument_key: str = Query(..., description="Instrument Key (e.g. NSE_INDEX|Nifty 50)"),
    expiry_date: str = Query(..., description="Expiry Date (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get option chain with complete quote data (LTP, Volume, OI).
    
    🟢 MARKET OPEN:
      1. Fetch spot price via /market-quote/ltp endpoint → Live LTP
      2. Fetch option quotes via /market-quote/full → Live LTP, Volume, OI, Depth
      3. Status = OPEN
      4. WebSocket streams real-time updates
    
    🔴 MARKET CLOSED (LTP API returns 0):
      1. Fallback 1: /market-quote/ohlc → Yesterday's close price
      2. Fallback 2: /historical-candle → Most recent candle close
      3. Fetch option quotes via /market-quote/full → Returns last trade data (previous session's LTP, volume, OI)
      4. Status = CLOSED
      5. Frontend displays "Market Closed" and shows previous session data
      6. When market opens, WebSocket updates with live data
    
    KEY ENDPOINTS:
      - /market-quote/ltp → Just last_price (market open only)
      - /market-quote/full → last_price + volume + oi + depth (works both open/closed!)
      - /market-quote/ohlc → Open/High/Low/Close (fallback when market closed)
      - /historical-candle → Past candles (fallback when OHLC fails)
    
    VOLUME/OI BEHAVIOR:
      - Market OPEN: /market-quote/full returns TODAY's volume/OI
      - Market CLOSED: /market-quote/full returns YESTERDAY's volume/OI (last trading session)
      - This is correct behavior - frontend shows last traded values when market closed
    """
    logger.info(f"ENTRY option-chain for {instrument_key}")

    try:
        if not instrument_manager.is_loaded:
            raise HTTPException(status_code=503, detail="Instrument master not loaded yet")

        # 1. Resolve Instrument Key (Handle Aliases: BANKNIFTY -> NSE_INDEX|Nifty Bank)
        # Verify we have the correct Upstox Key before making any API calls
        resolved_key = instrument_manager.resolve_instrument_key(instrument_key)
        
        # We ALSO need the underlying SYMBOL for option chain lookup
        resolved_symbol = instrument_manager._resolve_to_option_symbol(resolved_key)
        
        logger.debug(f"Resolved Input: {instrument_key} -> Key: {resolved_key} -> Symbol: {resolved_symbol}")
        
        # Update instrument_key to the resolved one for all subsequent calls
        instrument_key = resolved_key

        # Check Cache
        cache_key = f"{instrument_key}|{expiry_date}"
        now = datetime.utcnow()
        
        if cache_key in DATA_CACHE:
            ts, cached_data = DATA_CACHE[cache_key]
            if (now - ts).total_seconds() < CACHE_TTL:
                logger.info(f"✅ Cache HIT for {cache_key}")
                return cached_data
        
        logger.info(f"📡 Cache MISS for {cache_key} - Fetching from Upstox API")

        token = await get_upstox_client(user, db)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 2️⃣ FETCH SPOT PRICE (with automatic fallback when market closed)
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"STEP 1: Determine Spot Price (for ATM calculation)")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # For Spot Price, we use the ORIGINAL key (e.g. NSE_EQ|...)
            # ⭐ Official Upstox endpoint: /v2/market-quote/ltp (returns last_price during market hours AND after market close)
            ltp_url = "https://api.upstox.com/v2/market-quote/ltp"
            ltp_params = {"instrument_key": instrument_key}
            
            spot_price = 0.0
            market_status = "OPEN"

            # PRIMARY: /v2/market-quote/ltp (official recommended endpoint - works both during market hours and after market close)
            try:
                logger.debug(f"  Trying PRIMARY: GET {ltp_url}?instrument_key={instrument_key}")
                ltp_resp = await client.get(ltp_url, headers=headers, params=ltp_params)
                logger.info(f"📡 LTP API Response Status: {ltp_resp.status_code}")
                
                if ltp_resp.status_code == 200:
                    ltp_data = ltp_resp.json()
                    logger.debug(f"📋 LTP API Response Data: {ltp_data}")
                    
                    if "data" in ltp_data:
                        # ✅ FIX: Use robust helper to extract data
                        item_data = _extract_data_ignore_key_format(ltp_data, instrument_key)
                        
                        if item_data:
                            logger.info(f"   🔍 Found data via robust lookup for {instrument_key}")

                        if item_data:
                            spot_price = item_data.get("last_price", 0)
                            logger.info(f"🎯 Extracted last_price = {spot_price}")
                            
                            if spot_price > 0:
                                # 🟢 Enforce Time-Based Market Status
                                # Even if API returns data, if it's past 3:45 PM, it's CLOSED.
                                if is_market_open():
                                    logger.info(f"✅ PRIMARY: /v2/market-quote/ltp → Spot price = {spot_price} (Market OPEN)")
                                    market_status = "OPEN"
                                else:
                                    logger.info(f"✅ PRIMARY: /v2/market-quote/ltp → Spot price = {spot_price} (Market CLOSED due to time)")
                                    market_status = "CLOSED"
                            else:
                                logger.warning(f"⚠️ LTP returned 0 - trying fallback...")
                        else:
                            formatted_key = instrument_key.replace("|", ":")
                            logger.warning(f"⚠️ Key {instrument_key} (or derivatives) not in response. Available keys sample: {list(ltp_data['data'].keys())[:5]}")
                    else:
                        logger.warning(f"⚠️ 'data' field missing in LTP response")
                elif ltp_resp.status_code == 401:
                    logger.error(f"❌ 401 Unauthorized - Upstox token expired")
                    await _invalidate_token(user, db)
                    raise HTTPException(status_code=401, detail="Broker token expired. Please reconnect your broker account.")
                else:
                    logger.warning(f"⚠️ LTP API returned {ltp_resp.status_code}")
                    try:
                        logger.warning(f"   Response: {ltp_resp.json()}")
                    except:
                        logger.warning(f"   Response text: {ltp_resp.text[:500]}")
            except HTTPException:
                raise  # Re-raise HTTPException to propagate 401 to frontend
            except Exception as e:
                logger.error(f"⚠️ Spot Fetch Error: {e}", exc_info=True)

            # FALLBACK 1: Use /market-quote/quotes to get last_traded_price (works when market closed!)
            if spot_price == 0:
                market_status = "CLOSED"
                logger.warning(f"⚠️ PRIMARY LTP returned 0 - FALLBACK 1: Using /market-quote/quotes (best for closed market)")
                full_url = "https://api.upstox.com/v2/market-quote/quotes"
                full_params = {"instrument_key": instrument_key}
                try:
                    full_resp = await client.get(full_url, headers=headers, params=full_params)
                    logger.info(f"📡 Full Quote Response Status: {full_resp.status_code}")
                    
                    if full_resp.status_code == 200:
                        f_data = full_resp.json()
                        # ✅ FIX: Use robust helper
                        quote_data = _extract_data_ignore_key_format(f_data, instrument_key) or {}
                        logger.debug(f"📋 Full Quote Data: {quote_data}")
                        
                        if quote_data:
                            spot_price = quote_data.get("last_traded_price", 0) or quote_data.get("close", 0)
                            logger.info(f"🎯 Extracted last_traded_price = {spot_price}")
                            
                            if spot_price > 0:
                                logger.info(f"✅ FALLBACK 1: /market-quote/full → Spot price = {spot_price} (last traded price from previous session, MARKET CLOSED)")
                            else:
                                logger.warning(f"⚠️ /market-quote/full returned 0 ({quote_data}), trying OHLC...")
                        else:
                            logger.warning(f"⚠️ No quote data for {instrument_key}, trying OHLC...")
                    elif full_resp.status_code == 401:
                        logger.error(f"❌ 401 Unauthorized in full fallback - Upstox token expired")
                        await _invalidate_token(user, db)
                        raise HTTPException(status_code=401, detail="Broker token expired. Please reconnect your broker account.")
                    else:
                        logger.debug(f"⚠️ /market-quote/full returned {full_resp.status_code}, trying OHLC...")
                except HTTPException:
                    raise  # Re-raise HTTPException
                except Exception as e:
                    logger.error(f"⚠️ Full Quote Fallback Error: {e}", exc_info=True)

            # FALLBACK 2: OHLC (Daily close) - If /full didn't work
            if spot_price == 0:
                logger.debug(f"  Trying: GET /market-quote/ohlc (OHLC fallback)")
                ohlc_url = "https://api.upstox.com/v2/market-quote/ohlc"
                ohlc_params = {"instrument_key": instrument_key, "interval": "1d"}
                try:
                    ohlc_resp = await client.get(ohlc_url, headers=headers, params=ohlc_params)
                    if ohlc_resp.status_code == 200:
                        rr = ohlc_resp.json()
                        # ✅ FIX: Use robust helper (Note: OHLC structure is slightly different, nested under 'ohlc')
                        # The helper returns the value associated with the key. For OHLC, the value IS the object containing "ohlc".
                        item_data = _extract_data_ignore_key_format(rr, instrument_key)
                        ohlc_data = item_data.get("ohlc", {}) if item_data else {}
                        if ohlc_data:
                            spot_price = ohlc_data.get("close", 0.0)
                            if spot_price > 0:
                                logger.info(f"✅ FALLBACK 2: /market-quote/ohlc → Spot price = {spot_price} (yesterday's close, MARKET CLOSED)")
                    elif ohlc_resp.status_code == 401:
                        logger.error(f"❌ 401 Unauthorized in OHLC fallback - Upstox token expired")
                        await _invalidate_token(user, db)
                        raise HTTPException(status_code=401, detail="Broker token expired. Please reconnect your broker account.")
                    else:
                        logger.warning(f"⚠️ OHLC returned {ohlc_resp.status_code}, trying historical...")
                except HTTPException:
                    raise  # Re-raise HTTPException
                except Exception as e:
                    logger.error(f"⚠️ OHLC Fallback Error: {e}")

            # FALLBACK 3: Historical Candles (last resort)
            if spot_price == 0:
                logger.debug(f"  Trying: GET /historical-candle (last resort fallback)")
                today = datetime.now().strftime("%Y-%m-%d")
                days_back = 5  
                from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                
                hist_url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/day/{today}/{from_date}"
                try:
                    hist_resp = await client.get(hist_url, headers={"accept": "application/json"})
                    if hist_resp.status_code == 200:
                        h_data = hist_resp.json().get("data", {}).get("candles", [])
                        if h_data and len(h_data) > 0:
                            last_candle = h_data[-1]  
                            if len(last_candle) >= 5:
                                spot_price = last_candle[4]
                                logger.info(f"✅ FALLBACK 3: /historical-candle → Spot price = {spot_price} (last trading day close, MARKET CLOSED)")
                    else:
                        logger.warning(f"⚠️ Historical-candle returned {hist_resp.status_code}")
                except Exception as e:
                    logger.error(f"⚠️ Historical Fallback Error: {e}")

            # 3️⃣ CALCULATE ATM STRIKE
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"STEP 2: ATM Calculation & Chain Building")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Use resolved_symbol for step lookup
            step_size = instrument_manager.get_strike_step(resolved_symbol)
            logger.info(f"✅ Strike Step Retrieved: {step_size}")
            
            # ✅ SOLUTION 1: ALWAYS calculate ATM, even if spot_price is 0
            if spot_price > 0:
                atm_strike = round(spot_price / step_size) * step_size
                logger.info(f"✅ Spot Price: {spot_price}, Step Size: {step_size}, ATM Strike: {atm_strike}")
            else:
                # Fallback: Use a reasonable center strike (e.g., 20000 for indices, 500 for stocks)
                # This ensures we still build a chain even if spot price fetch failed
                atm_strike = 20000 if step_size == 50 else 25000 if step_size == 100 else 500
                logger.warning(f"⚠️ Spot price is 0, using fallback ATM: {atm_strike}")
            
            # 4️⃣ GET OPTION CHAIN STRUCTURE FROM LOCAL MANAGER
            # ✅ SOLUTION 1: ALWAYS build chain (whether spot is good or fallback)
            chain_data = instrument_manager.get_option_chain(
                resolved_symbol, expiry_date, atm_strike, count=8
            )
            logger.info(f"✅ Local chain built: {len(chain_data)} strike rows with ATM strike: {atm_strike}")
            
            # 5️⃣ BATCH FETCH OPTION QUOTES WITH GREEKS (WORKS BOTH OPEN AND CLOSED!)
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"STEP 3: Fetch Option Quote Data (LTP, Volume, OI, IV, Greeks)")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            option_keys = []
            instrument_key_to_symbol = {}  # ✅ MAP: NSE_FO|xxxxx -> NSE_FO:SYMBOL...

            for row in chain_data:
                if row["call_options"]: 
                    k = row["call_options"]["instrument_key"]
                    s = row["call_options"].get("trading_symbol")
                    option_keys.append(k)
                    # ✅ FIX: Construct the API-expected key format (NSE_FO:SYMBOL)
                    if k and s: 
                        # Ensure we don't double-prefix if for some reason it's already there
                        formatted_symbol = s if ":" in s else f"NSE_FO:{s}"
                        instrument_key_to_symbol[k] = formatted_symbol

                if row["put_options"]: 
                    k = row["put_options"]["instrument_key"]
                    s = row["put_options"].get("trading_symbol")
                    option_keys.append(k)
                    # ✅ FIX: Construct the API-expected key format (NSE_FO:SYMBOL)
                    if k and s: 
                        formatted_symbol = s if ":" in s else f"NSE_FO:{s}"
                        instrument_key_to_symbol[k] = formatted_symbol
            
            quote_map = {}  # ✅ Store full quote data WITH greeks
            if option_keys:
                try:
                    batch_size = 50  # Upstox limit for batch requests
                    # ... [existing code for batching] ...
                    
                    # NOTE: We need to use the SYMBOLS for fetching if the API expects symbols,
                    # BUT Upstox API documentation says 'instrument_key'.
                    # However, the user says the API returns keys as 'trading_symbol'.
                    # Let's check if we need to send symbols or keys.
                    # The user said: "GET /v2/market-quote/quotes?instrument_key=..."
                    # So we send KEYS, but get response keyed by SYMBOL.
                    
                    batches = [option_keys[i:i + batch_size] for i in range(0, len(option_keys), batch_size)]
                    
                    # ... [market status check] ...
                    
                    if market_status == "CLOSED":
                        # When market is closed, option-greek may return empty
                        # Use full endpoint which persists last session data
                        quote_url = "https://api.upstox.com/v2/market-quote/quotes"
                        logger.info(f"📡 MARKET CLOSED: Using /v2/market-quote/quotes (persists last session prices)")
                    else:
                        # When market is open, prefer option-greek for Greeks data
                        quote_url = "https://api.upstox.com/v3/market-quote/option-greek"
                        logger.info(f"📡 MARKET OPEN: Using /v3/market-quote/option-greek (includes Greeks)")
                    
                    logger.info(f"   Fetching from: {quote_url}")
                    logger.info(f"   Total instruments: {len(option_keys)} (in {len(batches)} batches of {batch_size})")
                    logger.info(f"   Market Status: {market_status}")
                    
                    if market_status == "CLOSED":
                        logger.info(f"   ℹ️ CLOSED MODE: Will return LAST TRADING SESSION data")
                        logger.info(f"      - last_price: Last traded price from previous session")
                        logger.info(f"      - volume: Total volume from previous trading day")
                        logger.info(f"      - oi: Open interest from previous session")
                    elif market_status == "OPEN":
                        logger.info(f"   ℹ️ OPEN MODE: Will return LIVE TRADING data")
                        logger.info(f"      - last_price: Live last traded price")
                        logger.info(f"      - volume: Today's accumulated volume")
                        logger.info(f"      - oi: Current open interest")
                        logger.info(f"      - iv: Implied Volatility (Greeks)")
                    
                    for batch_idx, batch in enumerate(batches):
                        keys_str = ",".join(batch)
                        logger.debug(f"  Batch {batch_idx + 1}/{len(batches)}: {len(batch)} instruments")
                        logger.debug(f"    Instruments: {batch[:3]}... (and {len(batch)-3} more)" if len(batch) > 3 else f"    Instruments: {batch}")
                        logger.debug(f"    Keys string length: {len(keys_str)} chars")
                        
                        # ✅ Call the appropriate endpoint based on market status
                        batch_resp = await client.get(quote_url, headers=headers, params={"instrument_key": keys_str})
                        logger.info(f"  Batch {batch_idx + 1} Response: HTTP {batch_resp.status_code}")
                        
                        if batch_resp.status_code == 200:
                            q_data = batch_resp.json().get("data", {})
                            logger.info(f"  Batch {batch_idx + 1}: {len(q_data)} quotes received")
                            
                            if len(q_data) == 0:
                                logger.warning(f"⚠️ WARNING: Batch {batch_idx + 1} returned empty data!")
                                logger.warning(f"   Full response: {batch_resp.json()}")
                            
                            for key, val in q_data.items():
                                # ✅ Parse response from either endpoint
                                # /market-quote/full returns: ohlc, last_traded_price, volume, oi, depth, etc.
                                # /market-quote/option-greek returns: last_price, iv, delta, theta, gamma, vega, oi, volume, cp
                                
                                # Determine which endpoint format we have
                                if "last_traded_price" in val or "last_price" in val:
                                    # /market-quote/quotes response format (used when market closed)
                                    # Note: v2/quotes uses "last_price" or "last_traded_price" depending on internal version
                                    ltp_val = val.get("last_price") or val.get("last_traded_price") or 0
                                    
                                    quote_map[key] = {
                                        "ltp": ltp_val,    # LTP persists in /quotes even when market closed!
                                        "volume": val.get("volume", 0),
                                        "oi": val.get("oi", 0),
                                        "iv": 0,  # /quotes typically doesn't have IV
                                        "delta": 0,
                                        "theta": 0,
                                        "gamma": 0,
                                        "vega": 0,
                                        "bid": val.get("bid", 0),
                                        "ask": val.get("ask", 0),
                                    }
                                    # logger.debug(f"    {key} [QUOTES]: LTP={quote_map[key]['ltp']}")
                                else:
                                    # /market-quote/option-greek response format (used when market open)
                                    quote_map[key] = {
                                        "ltp": val.get("last_price", 0),
                                        "volume": val.get("volume", 0),
                                        "oi": val.get("oi", 0),
                                        "iv": val.get("iv", 0),
                                        "delta": val.get("delta", 0),
                                        "theta": val.get("theta", 0),
                                        "gamma": val.get("gamma", 0),
                                        "vega": val.get("vega", 0),
                                        "bid": val.get("cp", 0),
                                        "ask": val.get("cp", 0),
                                    }
                                    # logger.debug(f"    {key} [GREEK]: LTP={quote_map[key]['ltp']}")
                        
                        elif batch_resp.status_code == 401:
                            logger.error(f"❌ 401 Unauthorized in batch quote fetch - Upstox token expired")
                            await _invalidate_token(user, db)
                            raise HTTPException(status_code=401, detail="Broker token expired. Please reconnect your broker account.")
                        
                        else:
                            try:
                                error_detail = batch_resp.json()
                                logger.warning(f"  Batch {batch_idx + 1} failed: HTTP {batch_resp.status_code}")
                                logger.warning(f"    Full error response: {error_detail}")
                            except:
                                logger.warning(f"  Batch {batch_idx + 1} failed: HTTP {batch_resp.status_code}")
                                logger.warning(f"    Response text: {batch_resp.text[:500]}")
                    
                    logger.info(f"✅ Quote fetch complete: {len(quote_map)}/{len(option_keys)} contracts received quote data")
                    
                except HTTPException:
                    raise  # Re-raise HTTPException
                except Exception as e:
                    logger.error(f"❌ Batch Quote Fetch Error: {e}", exc_info=True)

            # 6. Enrich chain with quote data
            enriched_chain = []
            logger.info(f"📦 ENRICHING CHAIN: {len(quote_map)} quotes available. Market Status: {market_status}")
            logger.info(f"   Sample keys in quote_map: {list(quote_map.keys())[:5]}")
            
            if market_status == "CLOSED":
                logger.info(f"🔴 MARKET CLOSED MODE: Using last trading session data (previous close LTP, volume, OI)")
            elif market_status == "OPEN":
                logger.info(f"🟢 MARKET OPEN MODE: Using live/current trading session data")
            else:
                logger.warning(f"⚠️ MARKET STATUS UNKNOWN: Using available data from API")
            
            call_count = 0
            call_found = 0
            for row in chain_data:
                # -----------------------------------------------------------
                # ENRICH CALL OPTIONS
                # -----------------------------------------------------------
                if row["call_options"] and isinstance(row["call_options"], dict):
                    if row["call_options"].get("instrument_key"):
                        k = row["call_options"]["instrument_key"]
                        call_count += 1
                        
                        # ✅ FIX: Robust Lookup using configured symbol map
                        s_key = instrument_key_to_symbol.get(k)
                        quote_data = None
                        
                        # 1. Try Mapped Symbol (NSE_FO:SYMBOL)
                        if s_key and s_key in quote_map:
                            quote_data = quote_map[s_key]
                        # 2. Try Original Key
                        elif k in quote_map:
                            quote_data = quote_map[k]
                        # 3. Try format swap
                        else:
                            alt_k = k.replace("|", ":")
                            if alt_k in quote_map:
                                quote_data = quote_map[alt_k]

                        if quote_data:
                            call_found += 1
                            if call_found == 1:
                                logger.info(f"  ✅ CALL FOUND: {k} -> LTP {quote_data['ltp']}")
                                
                            row["call_options"]["ltp"] = quote_data["ltp"]
                            row["call_options"]["volume"] = quote_data["volume"]
                            row["call_options"]["oi"] = quote_data["oi"]
                            row["call_options"]["iv"] = quote_data.get("iv", 0)
                            row["call_options"]["delta"] = quote_data.get("delta", 0)
                            row["call_options"]["theta"] = quote_data.get("theta", 0)
                            row["call_options"]["gamma"] = quote_data.get("gamma", 0)
                            row["call_options"]["vega"] = quote_data.get("vega", 0)
                            row["call_options"]["bid"] = quote_data.get("bid", 0)
                            row["call_options"]["ask"] = quote_data.get("ask", 0)
                        else:
                            if call_count <= 2: # Reduce log noise
                                logger.warning(f"  ❌ CALL MISSING: {k} (Symbol: {s_key})")
                                
                            # Keep existing values or default to 0
                            row["call_options"].setdefault("ltp", 0)
                            row["call_options"].setdefault("volume", 0)
                            row["call_options"].setdefault("oi", 0)
                            row["call_options"].setdefault("iv", 0)
                            row["call_options"].setdefault("delta", 0)
                    
                    # Ensure defaults for anything missing
                    row["call_options"].setdefault("bid", 0)
                    row["call_options"].setdefault("ask", 0)
                    row["call_options"].setdefault("gamma", 0)
                    row["call_options"].setdefault("theta", 0)
                    row["call_options"].setdefault("vega", 0)
                else:
                     row["call_options"] = {
                         "instrument_key": "", "trading_symbol": "", "ltp": 0, 
                         "volume": 0, "oi": 0, "iv": 0, "delta": 0, "theta": 0, 
                         "gamma": 0, "vega": 0, "bid": 0, "ask": 0
                     }

                # -----------------------------------------------------------
                # ENRICH PUT OPTIONS
                # -----------------------------------------------------------
                if row["put_options"] and isinstance(row["put_options"], dict):
                    if row["put_options"].get("instrument_key"):
                        k = row["put_options"]["instrument_key"]
                        
                        # ✅ FIX: Robust Lookup
                        s_key = instrument_key_to_symbol.get(k)
                        quote_data = None
                        
                        if s_key and s_key in quote_map:
                            quote_data = quote_map[s_key]
                        elif k in quote_map:
                            quote_data = quote_map[k]
                        else:
                            alt_k = k.replace("|", ":")
                            if alt_k in quote_map:
                                quote_data = quote_map[alt_k]

                        if quote_data:
                            row["put_options"]["ltp"] = quote_data["ltp"]
                            row["put_options"]["volume"] = quote_data["volume"]
                            row["put_options"]["oi"] = quote_data["oi"]
                            row["put_options"]["iv"] = quote_data.get("iv", 0)
                            row["put_options"]["delta"] = quote_data.get("delta", 0)
                            row["put_options"]["theta"] = quote_data.get("theta", 0)
                            row["put_options"]["gamma"] = quote_data.get("gamma", 0)
                            row["put_options"]["vega"] = quote_data.get("vega", 0)
                            row["put_options"]["bid"] = quote_data.get("bid", 0)
                            row["put_options"]["ask"] = quote_data.get("ask", 0)
                        else:
                            row["put_options"].setdefault("ltp", 0)
                            row["put_options"].setdefault("volume", 0)
                            row["put_options"].setdefault("oi", 0)
                            row["put_options"].setdefault("iv", 0)
                            row["put_options"].setdefault("delta", 0)
                    
                    # Ensure defaults
                    row["put_options"].setdefault("bid", 0)
                    row["put_options"].setdefault("ask", 0)
                    row["put_options"].setdefault("gamma", 0)
                    row["put_options"].setdefault("theta", 0)
                    row["put_options"].setdefault("vega", 0)
                else:
                     row["put_options"] = {
                         "instrument_key": "", "trading_symbol": "", "ltp": 0, 
                         "volume": 0, "oi": 0, "iv": 0, "delta": 0, "theta": 0, 
                         "gamma": 0, "vega": 0, "bid": 0, "ask": 0
                     }

                row["is_atm"] = (row["strike_price"] == atm_strike)
                enriched_chain.append(row)

            response_data = {
                "spot_price": spot_price,
                "chain": enriched_chain,
                "atm_strike": atm_strike,
                "strike_step": step_size,
                "market_status": market_status
            }
            
            # ✅ SOLUTION 2: ADD COMPREHENSIVE VALIDATION LOGGING BEFORE RETURN
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"📊 RESPONSE VALIDATION BEFORE RETURN")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"  spot_price: {spot_price} {'✅ GOOD' if spot_price > 0 else '❌ ZERO/INVALID'}")
            logger.info(f"  strike_step: {step_size} {'✅ GOOD' if step_size > 0 else '❌ ZERO/INVALID'}")
            logger.info(f"  atm_strike: {atm_strike} {'✅ GOOD' if atm_strike > 0 else '❌ ZERO/INVALID'}")
            logger.info(f"  chain rows: {len(enriched_chain)} {'✅ GOOD' if len(enriched_chain) > 0 else '❌ EMPTY'}")
            logger.info(f"  market_status: {market_status}")
            
            # Validate enrichment happened
            if enriched_chain and len(enriched_chain) > 0:
                first_row = enriched_chain[0]
                call_ltp = first_row.get("call_options", {}).get("ltp", "MISSING")
                put_ltp = first_row.get("put_options", {}).get("ltp", "MISSING")
                call_vol = first_row.get("call_options", {}).get("volume", "MISSING")
                put_vol = first_row.get("put_options", {}).get("volume", "MISSING")
                
                logger.info(f"📋 First Strike {first_row['strike_price']} Data Check:")
                logger.info(f"    CALL: LTP={call_ltp} {'✅' if call_ltp not in ['MISSING', 0] else '❌'}, VOL={call_vol} {'✅' if call_vol not in ['MISSING', 0] else '❌'}")
                logger.info(f"    PUT:  LTP={put_ltp} {'✅' if put_ltp not in ['MISSING', 0] else '❌'}, VOL={put_vol} {'✅' if put_vol not in ['MISSING', 0] else '❌'}")
                
                # Check ATM row if it exists
                atm_row = next((r for r in enriched_chain if r["is_atm"]), None)
                if atm_row:
                    atm_call_ltp = atm_row.get("call_options", {}).get("ltp", "MISSING")
                    atm_put_ltp = atm_row.get("put_options", {}).get("ltp", "MISSING")
                    logger.info(f"📋 ATM Strike {atm_row['strike_price']} Data Check:")
                    logger.info(f"    CALL: LTP={atm_call_ltp} {'✅' if atm_call_ltp not in ['MISSING', 0] else '❌'}")
                    logger.info(f"    PUT:  LTP={atm_put_ltp} {'✅' if atm_put_ltp not in ['MISSING', 0] else '❌'}")
            else:
                logger.warning(f"⚠️ Chain is empty! This will result in blank values on frontend.")
            
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"✅ RESPONSE COMPLETE & READY TO SEND TO FRONTEND")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            if enriched_chain:
                first_row = enriched_chain[0]
                atm_row = next((r for r in enriched_chain if r["is_atm"]), None)
                
                logger.info(f"📊 Sample Data Validation:")
                logger.info(f"  First Strike {first_row['strike_price']}:")
                logger.info(f"    CALL: LTP={first_row['call_options'].get('ltp', 0)}, Vol={first_row['call_options'].get('volume', 0)}, OI={first_row['call_options'].get('oi', 0)}")
                logger.info(f"    PUT:  LTP={first_row['put_options'].get('ltp', 0)}, Vol={first_row['put_options'].get('volume', 0)}, OI={first_row['put_options'].get('oi', 0)}")
                
                if atm_row:
                    logger.info(f"  ATM Strike {atm_row['strike_price']} (is_atm={atm_row['is_atm']}):")
                    logger.info(f"    CALL: LTP={atm_row['call_options'].get('ltp', 0)}, Vol={atm_row['call_options'].get('volume', 0)}, OI={atm_row['call_options'].get('oi', 0)}, Bid={atm_row['call_options'].get('bid', 0)}, Ask={atm_row['call_options'].get('ask', 0)}")
                    logger.info(f"    PUT:  LTP={atm_row['put_options'].get('ltp', 0)}, Vol={atm_row['put_options'].get('volume', 0)}, OI={atm_row['put_options'].get('oi', 0)}, Bid={atm_row['put_options'].get('bid', 0)}, Ask={atm_row['put_options'].get('ask', 0)}")
            
            if market_status == "CLOSED":
                logger.info(f"🔴 MARKET CLOSED MODE EXPLANATION:")
                logger.info(f"   ✓ Spot price: Fetched from OHLC/Historical (previous session close)")
                logger.info(f"   ✓ Option LTPs: From /market-quote/full (returns last traded price)")
                logger.info(f"   ✓ Option Volume: From /market-quote/full (yesterday's total volume)")
                logger.info(f"   ✓ Option OI: From /market-quote/full (previous session's open interest)")
                logger.info(f"   ✓ Frontend displays: 'Market Closed' with previous session data")
                logger.info(f"   ✓ WebSocket: Will update these values when market opens")
            elif market_status == "OPEN":
                logger.info(f"🟢 MARKET OPEN MODE EXPLANATION:")
                logger.info(f"   ✓ Spot price: Fetched from LTP API (live)")
                logger.info(f"   ✓ Option LTPs: From /market-quote/full (live)")
                logger.info(f"   ✓ Option Volume: From /market-quote/full (today's accumulated)")
                logger.info(f"   ✓ Option OI: From /market-quote/full (current)")
                logger.info(f"   ✓ Frontend displays: Live data with 'Market Open' status")
                logger.info(f"   ✓ WebSocket: Streaming real-time updates")
            else:
                logger.warning(f"⚠️ MARKET STATUS UNKNOWN - Frontend should handle gracefully")
            
            # Update Cache
            _cleanup_cache()
            DATA_CACHE[cache_key] = (datetime.utcnow(), response_data)
            logger.info(f"💾 Cached response for {CACHE_TTL}s: {cache_key}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            return response_data
            
    except Exception as e:
        logger.exception(f"CRITICAL ERROR in get_option_chain: {e}")
        # Return empty chain rather than crashing frontend
        return {
            "spot_price": 0,
            "chain": [],
            "atm_strike": 0,
            "strike_step": 0,
            "market_status": "ERROR"
        }

@router.get("/debug/instrument-stats")
async def get_instrument_stats():
    return instrument_manager.get_debug_stats()

@router.get("/debug/upstox-quote-test")
async def test_upstox_quote(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test Upstox /market-quote/quotes endpoint directly"""
    token = await get_upstox_client(user, db)
    
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    test_key = "NSE_FO|58689"
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            "https://api.upstox.com/v2/market-quote/quotes",
            headers=headers,
            params={"instrument_key": test_key}
        )
    
    return {
        "status_code": resp.status_code,
        "success": resp.status_code == 200,
        "response": resp.json() if resp.status_code == 200 else {"error": resp.text[:500]},
        "instrument_tested": test_key
    }

# ============================================================================
# 🆕 NEW ENDPOINTS FOR LTP, OI, IV DATA
# ============================================================================

@router.get("/ltp")
async def get_spot_ltp(
    instrument_key: str = Query(..., description="Instrument Key (e.g. NSE_INDEX|Nifty 50)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get LTP (Last Traded Price) of spot/underlying.
    
    Uses Upstox /v3/market-quote/ltp endpoint for real-time or last trading session data.
    
    Response:
    {
        "ltp": 24500.5,              # Last Traded Price
        "market_status": "OPEN",     # OPEN or CLOSED
        "instrument_key": "NSE_INDEX|Nifty 50",
        "volume": 1500000,           # Volume traded today
        "previous_close": 24400.0    # Previous day's close
    }
    """
    logger.info(f"🔍 LTP endpoint called for {instrument_key}")
    
    # Resolve Key First
    resolved_key = instrument_manager.resolve_instrument_key(instrument_key)
    if resolved_key != instrument_key:
        logger.info(f"   🔄 Resolution: {instrument_key} -> {resolved_key}")
    instrument_key = resolved_key
    
    try:
        token = await get_upstox_client(user, db)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try V3 endpoint first (more data)
            resp = await client.get(
                "https://api.upstox.com/v3/market-quote/ltp",
                headers=headers,
                params={"instrument_key": instrument_key}
            )
            
            if resp.status_code == 200:
                data = _extract_data_ignore_key_format(resp.json(), instrument_key) or {}
                market_status = "OPEN" if data.get("last_price", 0) > 0 else "CLOSED"
                
                return {
                    "ltp": data.get("last_price", 0),
                    "market_status": market_status,
                    "instrument_key": instrument_key,
                    "volume": data.get("volume", 0),
                    "previous_close": data.get("cp", 0),
                    "ltq": data.get("ltq", 0),  # Last Traded Quantity
                    "timestamp": data.get("timestamp", None)
                }
            
            elif resp.status_code == 401:
                logger.error(f"❌ 401 Unauthorized - Token expired")
                await _invalidate_token(user, db)
                raise HTTPException(status_code=401, detail="Broker token expired")
            
            else:
                logger.warning(f"⚠️ LTP API returned {resp.status_code}")
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch LTP")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LTP Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=f"LTP fetch error: {str(e)}")

@router.get("/debug/resolve-key")
async def debug_resolve_key(query: str):
    """Debug endpoint to check what key instrument_manager returns for a query"""
    results = instrument_manager.search_underlying(query)
    return {"query": query, "results": results}

@router.get("/debug/check-ltp")
async def debug_check_ltp(
    instrument_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Debug endpoint to force check LTP for a specific key"""
    token = await get_upstox_client(user, db)
    
    # 1. Check LTP
    ltp_url = "https://api.upstox.com/v2/market-quote/ltp"
    ltp_params = {"instrument_key": instrument_key}
    
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        
        ltp_resp = await client.get(ltp_url, headers=headers, params=ltp_params)
        
        return {
            "key_tested": instrument_key,
            "ltp_status": ltp_resp.status_code,
            "ltp_response": ltp_resp.json() if ltp_resp.status_code == 200 else ltp_resp.text
        }

@router.get("/quotes")
async def get_market_quotes(
    instrument_key: str = Query(..., description="Comma-separated instrument keys (max 500)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full market quotes including LTP, Volume, and OI.
    
    This is the best endpoint for market-closed data as it persists last session values.
    
    Response:
    {
        "NSE_FO|58689": {
            "ltp": 245.5,
            "oi": 1250000,
            "volume": 2500000,
            "ohlc": {
                "open": 244.0,
                "high": 246.5,
                "low": 244.0,
                "close": 245.0
            },
            "previous_close": 245.0,
            "market_status": "CLOSED"
        }
    }
    """
    logger.info(f"📊 Quotes endpoint called for {len(instrument_key.split(','))} instruments")
    
    # Resolve Keys
    raw_keys = instrument_key.split(',')
    resolved_keys = [instrument_manager.resolve_instrument_key(k.strip()) for k in raw_keys]
    instrument_key = ",".join(resolved_keys)
    
    try:
        token = await get_upstox_client(user, db)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use /v2/market-quote/quotes for comprehensive data including OI
            resp = await client.get(
                "https://api.upstox.com/v2/market-quote/quotes",
                headers=headers,
                params={"instrument_key": instrument_key}
            )
            
            if resp.status_code == 200:
                raw_data = resp.json().get("data", {})
                
                # Transform response to include market status
                result = {}
                for key, quote in raw_data.items():
                    market_status = "OPEN" if quote.get("last_price", 0) > 0 else "CLOSED"
                    
                    result[key] = {
                        "ltp": quote.get("last_price", 0),
                        "oi": quote.get("oi", 0),
                        "volume": quote.get("volume", 0),
                        "ohlc": quote.get("ohlc", {}),
                        "previous_close": quote.get("cp", 0),
                        "net_change": quote.get("net_change", 0),
                        "last_trade_time": quote.get("last_trade_time", None),
                        "oi_day_high": quote.get("oi_day_high", 0),
                        "oi_day_low": quote.get("oi_day_low", 0),
                        "market_status": market_status
                    }
                
                logger.info(f"✅ Fetched quotes for {len(result)} instruments")
                return result
            
            elif resp.status_code == 401:
                logger.error(f"❌ 401 Unauthorized - Token expired")
                await _invalidate_token(user, db)
                raise HTTPException(status_code=401, detail="Broker token expired")
            
            else:
                logger.warning(f"⚠️ Quotes API returned {resp.status_code}")
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch quotes")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Quotes Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=f"Quotes fetch error: {str(e)}")

@router.get("/option-greeks")
async def get_option_greeks(
    instrument_key: str = Query(..., description="Comma-separated option instrument keys (max 50)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get option Greeks including IV (Implied Volatility) and OI.
    
    This endpoint is optimized for getting market-closed option data with IV.
    
    Response:
    {
        "NSE_FO|58689": {
            "ltp": 245.5,           # Last Traded Price
            "iv": 18.5,             # Implied Volatility (%)
            "oi": 1250000,          # Open Interest
            "delta": 0.65,          # Delta Greek
            "gamma": 0.012,         # Gamma Greek
            "theta": -0.045,        # Theta Greek
            "vega": 0.125,          # Vega Greek
            "previous_close": 245.0,
            "volume": 2500000
        }
    }
    """
    logger.info(f"⚡ Option Greeks endpoint called for {len(instrument_key.split(','))} instruments")
    
    try:
        token = await get_upstox_client(user, db)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use /v3/market-quote/option-greek for IV and Greeks
            resp = await client.get(
                "https://api.upstox.com/v3/market-quote/option-greek",
                headers=headers,
                params={"instrument_key": instrument_key}
            )
            
            if resp.status_code == 200:
                raw_data = resp.json().get("data", {})
                
                # Transform response
                result = {}
                for key, greek in raw_data.items():
                    result[key] = {
                        "ltp": greek.get("last_price", 0),
                        "iv": greek.get("iv", 0),  # ⭐ Implied Volatility
                        "oi": greek.get("oi", 0),  # ⭐ Open Interest
                        "delta": greek.get("delta", 0),
                        "gamma": greek.get("gamma", 0),
                        "theta": greek.get("theta", 0),
                        "vega": greek.get("vega", 0),
                        "previous_close": greek.get("cp", 0),
                        "volume": greek.get("volume", 0),
                        "ltq": greek.get("ltq", 0)
                    }
                
                logger.info(f"✅ Fetched Greeks for {len(result)} options")
                return result
            
            elif resp.status_code == 401:
                logger.error(f"❌ 401 Unauthorized - Token expired")
                await _invalidate_token(user, db)
                raise HTTPException(status_code=401, detail="Broker token expired")
            
            else:
                logger.warning(f"⚠️ Option Greeks API returned {resp.status_code}")
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch option greeks")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Option Greeks Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=f"Option Greeks fetch error: {str(e)}")

@router.get("/market-close-snapshot")
async def get_market_close_snapshot(
    instrument_key: str = Query(..., description="Spot/Underlying Instrument Key"),
    expiry_date: str = Query(..., description="Option Expiry Date (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive market-close snapshot with spot LTP and ±ATM options (Call/Put) LTP, OI, IV.
    
    This endpoint is specifically designed for showing market-closed data to the user.
    It fetches:
    1. Spot price (underlying LTP)
    2. ATM Call option: LTP, OI, IV, Greeks
    3. ATM Put option: LTP, OI, IV, Greeks
    4. +1 ATM Call (next strike up)
    5. -1 ATM Put (next strike down)
    
    Response:
    {
        "timestamp": "2025-01-21 15:30:00 IST",
        "market_status": "CLOSED",
        "spot": {
            "instrument_key": "NSE_INDEX|Nifty 50",
            "ltp": 24500.5,
            "previous_close": 24400.0,
            "change": 100.5,
            "change_percent": 0.41
        },
        "options": {
            "atm_strike": 24500,
            "call": {
                "strike": 24500,
                "ltp": 245.5,
                "oi": 1250000,
                "iv": 18.5,
                "delta": 0.65
            },
            "put": {
                "strike": 24500,
                "ltp": 215.25,
                "oi": 980000,
                "iv": 18.2,
                "delta": -0.35
            },
            "call_plus_1": {
                "strike": 24600,
                "ltp": 195.75,
                "oi": 950000,
                "iv": 18.8
            },
            "put_minus_1": {
                "strike": 24400,
                "ltp": 235.5,
                "oi": 1100000,
                "iv": 18.0
            }
        }
    }
    """
    logger.info(f"📸 Market-close snapshot for {instrument_key} expiry {expiry_date}")
    
    try:
        if not instrument_manager.is_loaded:
            raise HTTPException(status_code=503, detail="Instrument master not loaded")
        
        token = await get_upstox_client(user, db)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Resolve Key
        instrument_key = instrument_manager.resolve_instrument_key(instrument_key)
        
        # Resolve to option symbol
        resolved_symbol = instrument_manager._resolve_to_option_symbol(instrument_key)
        logger.debug(f"Resolved {instrument_key} -> {resolved_symbol}")
        
        # Get spot price
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Get Spot Price
            logger.info(f"Fetching spot price...")
            ltp_resp = await client.get(
                "https://api.upstox.com/v3/market-quote/ltp",
                headers=headers,
                params={"instrument_key": instrument_key}
            )
            
            spot_data = {}
            if ltp_resp.status_code == 200:
                ltp_raw = _extract_data_ignore_key_format(ltp_resp.json(), instrument_key) or {}
                spot_ltp = ltp_raw.get("last_price", 0)
                spot_prev_close = ltp_raw.get("cp", 0)
                
                spot_data = {
                    "instrument_key": instrument_key,
                    "ltp": spot_ltp,
                    "previous_close": spot_prev_close,
                    "change": round(spot_ltp - spot_prev_close, 2),
                    "change_percent": round(((spot_ltp - spot_prev_close) / spot_prev_close * 100), 2) if spot_prev_close > 0 else 0
                }
                logger.info(f"✅ Spot LTP: {spot_ltp}")
            elif ltp_resp.status_code == 401:
                await _invalidate_token(user, db)
                raise HTTPException(status_code=401, detail="Broker token expired")
            
            # 2. Calculate ATM strike
            step_size = instrument_manager.get_strike_step(resolved_symbol)
            atm_strike = round(spot_data.get("ltp", 0) / step_size) * step_size
            logger.info(f"ATM Strike: {atm_strike}, Step: {step_size}")
            
            # 3. Get option chain structure
            chain_data = instrument_manager.get_option_chain(
                resolved_symbol, expiry_date, atm_strike, count=5
            )
            
            if not chain_data:
                raise HTTPException(status_code=404, detail="No option chain data available")
            
            # Find ATM row
            atm_row = next((r for r in chain_data if r["strike_price"] == atm_strike), None)
            plus_1_row = next((r for r in chain_data if r["strike_price"] == atm_strike + step_size), None)
            minus_1_row = next((r for r in chain_data if r["strike_price"] == atm_strike - step_size), None)
            
            if not atm_row:
                logger.warning(f"⚠️ ATM row not found for strike {atm_strike}")
                atm_row = chain_data[0] if chain_data else None
            
            # 4. Collect all option keys we need
            option_keys = []
            if atm_row:
                if atm_row.get("call_options"): 
                    option_keys.append(atm_row["call_options"]["instrument_key"])
                if atm_row.get("put_options"): 
                    option_keys.append(atm_row["put_options"]["instrument_key"])
            
            if plus_1_row:
                if plus_1_row.get("call_options"): 
                    option_keys.append(plus_1_row["call_options"]["instrument_key"])
            
            if minus_1_row:
                if minus_1_row.get("put_options"): 
                    option_keys.append(minus_1_row["put_options"]["instrument_key"])
            
            # 5. Fetch option greeks
            greeks_data = {}
            if option_keys:
                logger.info(f"Fetching greeks for {len(option_keys)} options...")
                keys_str = ",".join(option_keys)
                greeks_resp = await client.get(
                    "https://api.upstox.com/v3/market-quote/option-greek",
                    headers=headers,
                    params={"instrument_key": keys_str}
                )
                
                if greeks_resp.status_code == 200:
                    greeks_raw = greeks_resp.json().get("data", {})
                    for key, greek in greeks_raw.items():
                        greeks_data[key] = {
                            "ltp": greek.get("last_price", 0),
                            "iv": greek.get("iv", 0),
                            "oi": greek.get("oi", 0),
                            "delta": greek.get("delta", 0),
                            "gamma": greek.get("gamma", 0),
                            "theta": greek.get("theta", 0),
                            "vega": greek.get("vega", 0),
                        }
                    logger.info(f"✅ Fetched greeks for {len(greeks_data)} options")
                elif greeks_resp.status_code == 401:
                    await _invalidate_token(user, db)
                    raise HTTPException(status_code=401, detail="Broker token expired")
        
        # 6. Build response
        options_response = {
            "atm_strike": atm_strike,
            "call": {},
            "put": {},
            "call_plus_1": {},
            "put_minus_1": {}
        }
        
        # ATM Call
        if atm_row and atm_row.get("call_options"):
            call_key = atm_row["call_options"]["instrument_key"]
            if call_key in greeks_data:
                options_response["call"] = {
                    "strike": atm_strike,
                    **greeks_data[call_key]
                }
        
        # ATM Put
        if atm_row and atm_row.get("put_options"):
            put_key = atm_row["put_options"]["instrument_key"]
            if put_key in greeks_data:
                options_response["put"] = {
                    "strike": atm_strike,
                    **greeks_data[put_key]
                }
        
        # +1 Call
        if plus_1_row and plus_1_row.get("call_options"):
            call_plus_1_key = plus_1_row["call_options"]["instrument_key"]
            if call_plus_1_key in greeks_data:
                options_response["call_plus_1"] = {
                    "strike": atm_strike + step_size,
                    **greeks_data[call_plus_1_key]
                }
        
        # -1 Put
        if minus_1_row and minus_1_row.get("put_options"):
            put_minus_1_key = minus_1_row["put_options"]["instrument_key"]
            if put_minus_1_key in greeks_data:
                options_response["put_minus_1"] = {
                    "strike": atm_strike - step_size,
                    **greeks_data[put_minus_1_key]
                }
        
        # Build final response
        from datetime import datetime
        response = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
            "market_status": "CLOSED" if is_market_open() == False else "OPEN",
            "spot": spot_data,
            "options": options_response
        }
        
        logger.info(f"✅ Market-close snapshot complete")
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Market-close snapshot error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Snapshot error: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════════════
# 🆕 COMPREHENSIVE MARKET DATA ENDPOINTS (Market OPEN/CLOSED Compatible)
# ════════════════════════════════════════════════════════════════════════════════════

@router.get("/ltp-v3")
async def get_ltp_v3(
    instrument_key: str = Query(..., description="Instrument Key"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get LTP (Last Traded Price) with smart fallback for market-closed
    
    🟢 Market OPEN:
      Returns: Live last-traded price via /v3/market-quote/ltp
    
    🔴 Market CLOSED:
      Returns: Previous day close price via /v2/market-quote/ohlc → /v2/historical-candle
    
    Response:
    {
        "ltp": 24500.5,
        "market_status": "OPEN",  // or "CLOSED" or "UNKNOWN"
        "volume": 1500000,
        "previous_close": 24400.0,
        "timestamp": "2025-01-21 15:30:00"
    }
    """
    logger.info(f"📊 /ltp-v3 endpoint: {instrument_key}")
    
    try:
        from .market_data_fetcher import fetch_spot_ltp
        
        token = await get_upstox_client(user, db)
        price, market_status = await fetch_spot_ltp(token, instrument_key)
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        # Get additional data
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.upstox.com/v3/market-quote/ltp",
                headers=headers,
                params={"instrument_key": instrument_key}
            )
            
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get(instrument_key, {})
                return {
                    "ltp": price,
                    "market_status": market_status,
                    "volume": data.get("volume", 0),
                    "previous_close": data.get("cp", 0),
                    "timestamp": data.get("timestamp", None),
                    "ltq": data.get("ltq", 0)
                }
            elif resp.status_code == 401:
                await _invalidate_token(user, db)
                raise HTTPException(status_code=401, detail="Broker token expired")
        
        return {
            "ltp": price,
            "market_status": market_status,
            "volume": 0,
            "previous_close": 0,
            "timestamp": None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ LTP-V3 error: {e}")
        raise HTTPException(status_code=500, detail=f"LTP fetch failed: {str(e)}")


@router.get("/option-chain-v3")
async def get_option_chain_v3(
    instrument_key: str = Query(..., description="Underlying Instrument Key"),
    expiry_date: str = Query(..., description="Expiry Date (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🆕 BEST ENDPOINT FOR MARKET-CLOSED OPTION CHAIN DATA
    
    Enhanced option-chain endpoint using unified MarketDataFetcher
    Automatically handles both market OPEN and CLOSED scenarios
    
    🟢 Market OPEN:
      - LTP from /v3/market-quote/ltp
      - IV, Greeks from /v3/market-quote/option-greek
      - Status: OPEN
      - WebSocket streams live updates
    
    🔴 Market CLOSED:
      - LTP, OI from /v2/market-quote/full (persists last session)
      - IV, Greeks: zeros (market closed)
      - Status: CLOSED
      - Shows previous session trading data
    
    Returns option chain with columns:
    - strike_price
    - call_options: {instrument_key, ltp, oi, iv, delta, gamma, theta, vega, volume, bid, ask}
    - put_options: {instrument_key, ltp, oi, iv, delta, gamma, theta, vega, volume, bid, ask}
    - market_status: "OPEN" or "CLOSED"
    """
    logger.info(f"🆕 /option-chain-v3: {instrument_key} expiry {expiry_date}")
    
    try:
        if not instrument_manager.is_loaded:
            raise HTTPException(status_code=503, detail="Instrument master loading...")
        
        from .market_data_fetcher import MarketDataFetcher
        
        token = await get_upstox_client(user, db)
        fetcher = MarketDataFetcher(token, timeout=10.0)
        
        # 1. Get spot price with market status
        spot_price, market_status = await fetcher.get_spot_price(instrument_key)
        logger.info(f"  Spot: {spot_price}, Status: {market_status}")
        
        # 2. Resolve to option symbol and build chain
        resolved_symbol = instrument_manager._resolve_to_option_symbol(instrument_key)
        step_size = instrument_manager.get_strike_step(resolved_symbol)
        
        if spot_price > 0:
            atm_strike = round(spot_price / step_size) * step_size
        else:
            atm_strike = 0
        
        chain_data = []
        if atm_strike > 0:
            chain_data = instrument_manager.get_option_chain(
                resolved_symbol, expiry_date, atm_strike, count=8
            )
            logger.info(f"  Chain built: {len(chain_data)} strikes")
        
        # 3. Collect all option keys
        option_keys = []
        for row in chain_data:
            if row.get("call_options"):
                option_keys.append(row["call_options"]["instrument_key"])
            if row.get("put_options"):
                option_keys.append(row["put_options"]["instrument_key"])
        
        # 4. Fetch batch quotes (smart endpoint selection based on market_status)
        quote_map = {}
        if option_keys:
            logger.info(f"  Fetching {len(option_keys)} option quotes...")
            quote_map = await fetcher.get_quotes_batch(option_keys, market_status)
            logger.info(f"  Received: {len(quote_map)} quotes")
        
        # 5. Enrich chain with quote data
        enriched_chain = []
        for row in chain_data:
            # Ensure complete structure for call
            if row.get("call_options") and isinstance(row["call_options"], dict):
                call_key = row["call_options"].get("instrument_key")
                if call_key and call_key in quote_map:
                    q = quote_map[call_key]
                    row["call_options"].update({
                        "ltp": q.ltp,
                        "volume": q.volume,
                        "oi": q.oi,
                        "iv": q.iv,
                        "delta": q.delta,
                        "gamma": q.gamma,
                        "theta": q.theta,
                        "vega": q.vega,
                        "bid": q.bid,
                        "ask": q.ask
                    })
                else:
                    row["call_options"].update({
                        "ltp": 0, "volume": 0, "oi": 0, "iv": 0,
                        "delta": 0, "gamma": 0, "theta": 0, "vega": 0,
                        "bid": 0, "ask": 0
                    })
            
            # Ensure complete structure for put
            if row.get("put_options") and isinstance(row["put_options"], dict):
                put_key = row["put_options"].get("instrument_key")
                if put_key and put_key in quote_map:
                    q = quote_map[put_key]
                    row["put_options"].update({
                        "ltp": q.ltp,
                        "volume": q.volume,
                        "oi": q.oi,
                        "iv": q.iv,
                        "delta": q.delta,
                        "gamma": q.gamma,
                        "theta": q.theta,
                        "vega": q.vega,
                        "bid": q.bid,
                        "ask": q.ask
                    })
                else:
                    row["put_options"].update({
                        "ltp": 0, "volume": 0, "oi": 0, "iv": 0,
                        "delta": 0, "gamma": 0, "theta": 0, "vega": 0,
                        "bid": 0, "ask": 0
                    })
            
            row["market_status"] = market_status
            enriched_chain.append(row)
        
        return {
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "market_status": market_status,
            "chain": enriched_chain,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ option-chain-v3 error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Option chain error: {str(e)}")


@router.get("/option-quotes-batch-v3")
async def get_option_quotes_batch_v3(
    instrument_key: str = Query(..., description="Comma-separated option instrument keys (max 100)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🆕 FETCH BATCH OPTION QUOTES WITH SMART ENDPOINT SELECTION
    
    Unified endpoint for getting LTP, OI, IV, Greeks for multiple options
    Automatically selects best endpoint based on market status
    
    🟢 Market OPEN:
      Uses: /v3/market-quote/option-greek
      Returns: LTP, OI, IV, Greeks
    
    🔴 Market CLOSED:
      Uses: /v2/market-quote/full
      Returns: LTP, OI (persisted), IV=0, Greeks=0
    
    Response:
    {
        "NSE_FO|58689": {
            "ltp": 245.5,
            "oi": 1250000,
            "iv": 18.5,
            "delta": 0.65,
            "gamma": 0.012,
            "theta": -0.045,
            "vega": 0.125,
            "volume": 2500000,
            "bid": 245.0,
            "ask": 245.5,
            "market_status": "OPEN"
        }
    }
    """
    logger.info(f"🆕 /option-quotes-batch-v3: {len(instrument_key.split(','))} instruments")
    
    try:
        from .market_data_fetcher import MarketDataFetcher
        
        token = await get_upstox_client(user, db)
        keys = [k.strip() for k in instrument_key.split(",") if k.strip()]
        
        if not keys:
            raise HTTPException(status_code=400, detail="No instrument keys provided")
        
        if len(keys) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 instruments per request")
        
        fetcher = MarketDataFetcher(token, timeout=10.0)
        
        # Fetch with smart endpoint selection
        quote_map = await fetcher.get_quotes_batch(keys)
        
        result = {k: v.to_dict() for k, v in quote_map.items()}
        
        logger.info(f"✅ Fetched {len(result)}/{len(keys)} option quotes")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ option-quotes-batch-v3 error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch quote fetch failed: {str(e)}")


@router.get("/option-iv-greeks-batch")
async def get_option_iv_greeks_batch(
    instrument_key: str = Query(..., description="Comma-separated option instrument keys"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🆕 FETCH IV AND GREEKS FOR MULTIPLE OPTIONS
    
    Specialized endpoint for getting option Greeks and Implied Volatility
    Returns zeros for Greeks/IV when market is closed
    
    Response:
    {
        "NSE_FO|58689": {
            "iv": 18.5,          # Implied Volatility (%)
            "delta": 0.65,       # Delta
            "gamma": 0.012,      # Gamma
            "theta": -0.045,     # Theta
            "vega": 0.125,       # Vega
            "market_status": "OPEN"
        }
    }
    """
    logger.info(f"🆕 /option-iv-greeks-batch: {len(instrument_key.split(','))} instruments")
    
    try:
        from .market_data_fetcher import MarketDataFetcher
        
        token = await get_upstox_client(user, db)
        keys = [k.strip() for k in instrument_key.split(",") if k.strip()]
        
        if not keys:
            raise HTTPException(status_code=400, detail="No instrument keys provided")
        
        fetcher = MarketDataFetcher(token, timeout=10.0)
        quote_map = await fetcher.get_quotes_batch(keys)
        
        result = {}
        for k, v in quote_map.items():
            result[k] = {
                "iv": v.iv,
                "delta": v.delta,
                "gamma": v.gamma,
                "theta": v.theta,
                "vega": v.vega,
                "market_status": v.market_status
            }
        
        logger.info(f"✅ Fetched IV/Greeks for {len(result)} options")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ option-iv-greeks-batch error: {e}")
        raise HTTPException(status_code=500, detail=f"IV/Greeks fetch failed: {str(e)}")
