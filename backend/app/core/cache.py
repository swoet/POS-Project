"""
Redis caching layer with performance optimization
"""
import json
import pickle
from typing import Any, Optional, Union, List
from datetime import timedelta
import redis
import structlog
from fastapi_cache2 import FastAPICache
from fastapi_cache2.backends.redis import RedisBackend

from .config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class CacheManager:
    """Redis cache manager with advanced features"""
    
    def __init__(self):
        self.redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        self.binary_redis = redis.from_url(
            settings.redis_url,
            decode_responses=False  # For binary data
        )
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value is None:
                return default
            
            # Try to parse as JSON first
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error("Cache get failed", key=key, error=str(e))
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        try:
            if ttl is None:
                ttl = settings.cache_ttl
            
            # Serialize complex objects as JSON
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)
            
            return self.redis_client.setex(key, ttl, serialized_value)
            
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error("Cache delete failed", key=key, error=str(e))
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error("Cache pattern delete failed", pattern=pattern, error=str(e))
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter in cache"""
        try:
            return self.redis_client.incr(key, amount)
        except Exception as e:
            logger.error("Cache increment failed", key=key, error=str(e))
            return 0
    
    async def set_with_lock(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        lock_timeout: int = 10
    ) -> bool:
        """Set value with distributed lock"""
        lock_key = f"lock:{key}"
        try:
            # Acquire lock
            if not self.redis_client.set(lock_key, "1", nx=True, ex=lock_timeout):
                return False
            
            # Set value
            result = await self.set(key, value, ttl)
            
            # Release lock
            self.redis_client.delete(lock_key)
            return result
            
        except Exception as e:
            logger.error("Cache locked set failed", key=key, error=str(e))
            # Ensure lock is released
            self.redis_client.delete(lock_key)
            return False
    
    async def get_or_set(
        self, 
        key: str, 
        factory_func, 
        ttl: Optional[int] = None
    ) -> Any:
        """Get value from cache or set it using factory function"""
        value = await self.get(key)
        if value is not None:
            return value
        
        # Generate value
        try:
            if callable(factory_func):
                new_value = factory_func()
            else:
                new_value = factory_func
            
            await self.set(key, new_value, ttl)
            return new_value
            
        except Exception as e:
            logger.error("Cache get_or_set failed", key=key, error=str(e))
            return None
    
    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False
    
    def get_stats(self) -> dict:
        """Get Redis statistics"""
        try:
            info = self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.error("Redis stats failed", error=str(e))
            return {}


# Cache key generators
class CacheKeys:
    """Centralized cache key management"""
    
    @staticmethod
    def user(user_id: int) -> str:
        return f"user:{user_id}"
    
    @staticmethod
    def product(product_id: int) -> str:
        return f"product:{product_id}"
    
    @staticmethod
    def products_by_category(category_id: int) -> str:
        return f"products:category:{category_id}"
    
    @staticmethod
    def product_search(query: str) -> str:
        return f"search:products:{hash(query)}"
    
    @staticmethod
    def sales_summary(start_date: str, end_date: str) -> str:
        return f"sales:summary:{start_date}:{end_date}"
    
    @staticmethod
    def inventory_low_stock() -> str:
        return "inventory:low_stock"
    
    @staticmethod
    def user_permissions(user_id: int) -> str:
        return f"permissions:user:{user_id}"
    
    @staticmethod
    def rate_limit(identifier: str) -> str:
        return f"rate_limit:{identifier}"


# Global cache manager
cache_manager = CacheManager()


def setup_fastapi_cache():
    """Initialize FastAPI cache"""
    try:
        redis_backend = RedisBackend(settings.redis_url)
        FastAPICache.init(redis_backend, prefix="fastapi-cache")
        logger.info("FastAPI cache initialized")
    except Exception as e:
        logger.error("FastAPI cache initialization failed", error=str(e))


# Cache decorators
def cache_result(ttl: int = None, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs) if callable(func) else func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl or settings.cache_ttl)
            
            return result
        return wrapper
    return decorator
