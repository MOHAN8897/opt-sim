import redis.asyncio as redis
from .config import settings
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger("api.redis")

class RedisManager:
    """
    Manages Redis connections for:
    - Market data storage (md:{instrument_key})
    - Live PnL cache (pnl:{user_id})
    - Distributed locks (lock:{resource})
    """
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            if settings.REDIS_PASSWORD:
                redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            
            self.client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.client.ping()
            self._connected = True
            logger.info(f"✅ Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("Redis connection closed")
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._connected
    
    # ============ MARKET DATA ============
    
    async def set_market_data(self, instrument_key: str, data: Dict[str, Any]):
        """
        Store market data for an instrument.
        Key: md:{instrument_key}
        Data: {bid, ask, bid_qty, ask_qty, ltp, timestamp}
        """
        if not self.client:
            return
        
        try:
            # ✅ PHASE 2: Extended schema with staleness metadata
            await self.client.hset(
                f"md:{instrument_key}",
                mapping={
                    'ltp': str(data.get('ltp', 0)),
                    'bid': str(data.get('bid', 0)),
                    'ask': str(data.get('ask', 0)),
                    'bid_qty': str(data.get('bid_qty', 0)),
                    'ask_qty': str(data.get('ask_qty', 0)),
                    'timestamp': data.get('timestamp', ''),
                    # ✅ NEW: Staleness & simulation tracking
                    'bid_ts': str(data.get('bid_ts', 0)),
                    'ask_ts': str(data.get('ask_ts', 0)),
                    'bid_simulated': str(data.get('bid_simulated', False)),
                    'ask_simulated': str(data.get('ask_simulated', False)),
                    'spread': str(data.get('spread', 0)),
                    'spread_pct': str(data.get('spread_pct', 0))
                }
            )
            
            # Set expiry (10 seconds - strict watchdog for zombie data)
            await self.client.expire(f"md:{instrument_key}", 10)
        
        except Exception as e:
            logger.error(f"Error setting market data for {instrument_key}: {e}")
    
    async def get_market_data(self, instrument_key: str) -> Dict[str, Any]:
        """
        Get market data for an instrument.
        Returns: {bid, ask, bid_qty, ask_qty, ltp, timestamp}
        """
        if not self.client:
            return {}
        
        try:
            data = await self.client.hgetall(f"md:{instrument_key}")
            if not data:
                return {}
            
            # ✅ PHASE 2: Return extended data with staleness metadata
            return {
                'ltp': float(data.get('ltp', 0)),
                'bid': float(data.get('bid', 0)),
                'ask': float(data.get('ask', 0)),
                'bid_qty': int(float(data.get('bid_qty', 0))),
                'ask_qty': int(float(data.get('ask_qty', 0))),
                'timestamp': data.get('timestamp', ''),
                # ✅ NEW: Staleness metadata
                'bid_ts': int(float(data.get('bid_ts', 0))),
                'ask_ts': int(float(data.get('ask_ts', 0))),
                'bid_simulated': data.get('bid_simulated', 'False') == 'True',
                'ask_simulated': data.get('ask_simulated', 'False') == 'True',
                'spread': float(data.get('spread', 0)),
                'spread_pct': float(data.get('spread_pct', 0))
            }
        
        except Exception as e:
            logger.error(f"Error getting market data for {instrument_key}: {e}")
            return {}
    
    # ============ PNL CACHE ============
    
    async def set_pnl(self, user_id: int, pnl: float):
        """
        Cache live PnL for a user.
        Key: pnl:{user_id}
        """
        if not self.client:
            return
        
        try:
            await self.client.set(f"pnl:{user_id}", str(pnl), ex=300)
        except Exception as e:
            logger.error(f"Error setting PnL for user {user_id}: {e}")
    
    async def get_pnl(self, user_id: int) -> float:
        """Get cached PnL for a user"""
        if not self.client:
            return 0.0
        
        try:
            pnl = await self.client.get(f"pnl:{user_id}")
            return float(pnl) if pnl else 0.0
        except Exception as e:
            logger.error(f"Error getting PnL for user {user_id}: {e}")
            return 0.0
    
    # ============ DISTRIBUTED LOCKS ============
    
    async def acquire_lock(self, lock_key: str, ttl: int = 1) -> bool:
        """
        Acquire a distributed lock using SET NX.
        Returns: True if lock acquired, False otherwise
        """
        if not self.client:
            return False
        
        try:
            # SET key value NX EX ttl
            result = await self.client.set(lock_key, "1", nx=True, ex=ttl)
            return result is not None
        except Exception as e:
            logger.error(f"Error acquiring lock {lock_key}: {e}")
            return False
    
    async def release_lock(self, lock_key: str):
        """Release a distributed lock"""
        if not self.client:
            return
        
        try:
            await self.client.delete(lock_key)
        except Exception as e:
            logger.error(f"Error releasing lock {lock_key}: {e}")


# Global instance
redis_manager = RedisManager()
