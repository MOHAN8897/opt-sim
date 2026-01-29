"""
Enhanced Logging Utilities for Backend Debugging

Provides structured logging helpers for tracking data flow:
- Frontend -> Backend request tracking
- API calls to Upstox (with endpoint details)
- Market data fetching (LTP, OI, IV, Greeks)
- WebSocket updates

Usage:
    from .logging_utils import log_entry, log_api_call, log_market_data
    
    log_entry("get_option_chain", {"instrument": "NSE_INDEX|Nifty 50"})
    log_api_call("GET", "https://api.upstox.com/v2/market-quote/full", 200, duration_ms=45)
    log_market_data("NIFTY", "LTP", 23450.50, market_status="OPEN")
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional, List

logger = logging.getLogger("api")


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Foreground
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Background
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


def log_entry(endpoint: str, params: Dict[str, Any], user_id: Optional[str] = None):
    """Log when a frontend request enters the backend"""
    user_str = f" [User: {user_id}]" if user_id else ""
    logger.info(f"{'='*100}")
    logger.info(f"{Colors.CYAN}📥 ENTRY: {endpoint}{user_str}{Colors.RESET}")
    logger.info(f"{Colors.CYAN}   Parameters: {json.dumps(params, indent=2)}{Colors.RESET}")
    logger.info(f"{'='*100}")


def log_api_call(
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    batch_num: Optional[int] = None,
    total_batches: Optional[int] = None,
    response_size: Optional[int] = None,
    error: Optional[str] = None
):
    """Log API call to external service (Upstox, etc)"""
    
    # Status code color
    if status_code == 200:
        status_color = Colors.GREEN
        status_icon = "✅"
    elif status_code == 401:
        status_color = Colors.RED
        status_icon = "🔴"
    elif status_code >= 500:
        status_color = Colors.RED
        status_icon = "❌"
    elif status_code >= 400:
        status_color = Colors.YELLOW
        status_icon = "⚠️"
    else:
        status_color = Colors.YELLOW
        status_icon = "⚪"
    
    batch_str = f" [Batch {batch_num}/{total_batches}]" if batch_num and total_batches else ""
    size_str = f" ({response_size} bytes)" if response_size else ""
    error_str = f" - ERROR: {error}" if error else ""
    
    logger.info(
        f"{status_color}{status_icon} {method:6s} {status_code} {duration_ms:6.1f}ms {Colors.RESET} "
        f"{url}{batch_str}{size_str}{error_str}"
    )


def log_market_data(
    instrument: str,
    data_type: str,  # "LTP", "OI", "IV", "DELTA", etc.
    value: float,
    market_status: str = "UNKNOWN",
    additional_data: Optional[Dict[str, Any]] = None
):
    """Log market data fetch result"""
    
    status_icon = "🟢" if market_status == "OPEN" else "🔴" if market_status == "CLOSED" else "❓"
    
    base_msg = f"{status_icon} {data_type:8s} {instrument:20s} = {value:12.2f}  [{market_status}]"
    
    if additional_data:
        extra = ", ".join([f"{k}={v}" for k, v in additional_data.items()])
        base_msg += f"  ({extra})"
    
    logger.info(base_msg)


def log_batch_fetch(
    endpoint: str,
    total_instruments: int,
    batch_size: int,
    market_status: str
):
    """Log batch fetch operation start"""
    batch_count = (total_instruments + batch_size - 1) // batch_size
    logger.info(f"\n{'─'*100}")
    logger.info(f"{Colors.BLUE}📦 BATCH FETCH{Colors.RESET}")
    logger.info(f"   Endpoint: {endpoint}")
    logger.info(f"   Total Instruments: {total_instruments}")
    logger.info(f"   Batch Size: {batch_size}")
    logger.info(f"   Batch Count: {batch_count}")
    logger.info(f"   Market Status: {market_status}")
    logger.info(f"{'─'*100}\n")


def log_chain_enrichment(
    chain_size: int,
    quotes_found: int,
    quotes_missing: int,
    market_status: str
):
    """Log option chain enrichment statistics"""
    found_pct = (quotes_found / (quotes_found + quotes_missing) * 100) if (quotes_found + quotes_missing) > 0 else 0
    
    logger.info(f"\n{'─'*100}")
    logger.info(f"{Colors.BLUE}🔗 CHAIN ENRICHMENT{Colors.RESET}")
    logger.info(f"   Chain Size: {chain_size} strike rows")
    logger.info(f"   Quotes Found: {quotes_found} ({found_pct:.1f}%)")
    logger.info(f"   Quotes Missing: {quotes_missing}")
    logger.info(f"   Market Status: {market_status}")
    
    if market_status == "CLOSED":
        logger.info(f"   💡 Note: Missing quotes will be updated when market opens via WebSocket")
    
    logger.info(f"{'─'*100}\n")


def log_websocket_update(
    instrument_key: str,
    ltp: float,
    oi: int,
    iv: float,
    timestamp: Optional[str] = None
):
    """Log WebSocket live update"""
    logger.debug(
        f"🔄 WS Update: {instrument_key:40s} LTP={ltp:10.2f} OI={oi:8d} IV={iv:6.2f}"
    )


def log_exit(endpoint: str, status_code: int, response_size: Optional[int] = None, duration_ms: Optional[float] = None):
    """Log when response is sent back to frontend"""
    status_icon = "✅" if status_code == 200 else "❌"
    size_str = f" ({response_size} bytes)" if response_size else ""
    time_str = f" ({duration_ms:.1f}ms)" if duration_ms else ""
    
    logger.info(f"{'='*100}")
    logger.info(f"{Colors.GREEN}{status_icon} EXIT: {endpoint} [{status_code}]{size_str}{time_str}{Colors.RESET}")
    logger.info(f"{'='*100}\n")


def log_error(error_type: str, error_msg: str, context: Optional[Dict[str, Any]] = None, exc_info=None):
    """Log error with context"""
    context_str = f"\nContext: {json.dumps(context, indent=2)}" if context else ""
    logger.error(
        f"{Colors.RED}❌ ERROR: {error_type}{Colors.RESET}\n"
        f"   Message: {error_msg}{context_str}",
        exc_info=exc_info
    )


def log_token_event(event_type: str, user_email: str, status: str = ""):
    """Log token-related events"""
    icon_map = {
        "invalidate": "🔴",
        "validate": "🟢",
        "expire": "⏰",
        "refresh": "🔄",
    }
    icon = icon_map.get(event_type, "🔵")
    status_str = f" [{status}]" if status else ""
    logger.info(f"{icon} Token {event_type.upper()}: {user_email}{status_str}")


# Market status message helpers
def get_market_status_message(market_status: str) -> str:
    """Get human-readable market status message"""
    messages = {
        "OPEN": "🟢 MARKET OPEN - Using LIVE data from /v3/market-quote/option-greek",
        "CLOSED": "🔴 MARKET CLOSED - Using PERSISTED data from previous session (/v2/market-quote/full)",
        "UNKNOWN": "❓ MARKET STATUS UNKNOWN - Using fallback endpoints",
    }
    return messages.get(market_status, f"Market Status: {market_status}")
