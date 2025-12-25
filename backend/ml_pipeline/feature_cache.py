"""
Feature Cache Module
===================

This module handles caching of feature extraction results using Redis.
Caching is CRITICAL for this system because:
1. External APIs (Census, Sentinel, OSM) have rate limits
2. Data extraction is slow (seconds to minutes)
3. Data changes slowly (Census: annually, OSM: weekly)

We use different TTLs (Time To Live) for different data sources:
- Census: 365 days (Very stable)
- OSM: 7 days (Moderately stable)
- Satellite: 7 days (Updated every 5 days, but we don't need realtime)
"""

import json
import logging
import hashlib
from typing import Any, Optional, Dict
import redis
from datetime import timedelta

# Configure logging
logger = logging.getLogger(__name__)

# Default Cache Configuration
# In production, these should come from environment variables
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


class FeatureCache:
    """
    Manages caching of extracted features to avoid redundant API calls.
    Uses Redis as the backend storage.
    """

    def __init__(self, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        """
        Initialize the Redis connection.
        
        Args:
            host: Redis hostname
            port: Redis port
            db: Redis database index
        """
        try:
            self.redis_client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                decode_responses=True,  # Return strings instead of bytes
                socket_connect_timeout=2  # Fail fast if Redis is down
            )
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"Feature Cache connected to Redis at {host}:{port}")
        except redis.ConnectionError:
            self.enabled = False
            logger.warning("Redis connection failed. Caching is DISABLED.")

    def cache_key_for_location(
        self, 
        latitude: float, 
        longitude: float, 
        feature_type: str, 
        radius: int
    ) -> str:
        """
        Generate a deterministic cache key for a location and feature set.
        
        We round coordinates to ~1 meter precision (5 decimal places) to allow 
        nearby points to share cached data. This is a form of 'spatial binning'.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            feature_type: Identifier for the data source (e.g., 'census', 'osm')
            radius: Analysis radius in meters
            
        Returns:
            String key like "features:census:40.71280:-74.00600:500"
        """
        # Round to 5 decimals (~1.1 meter precision at equator)
        # This allows slightly different coordinate queries to hit the same cache
        lat_rounded = round(latitude, 5)
        lon_rounded = round(longitude, 5)
        
        key = f"features:{feature_type}:{lat_rounded}:{lon_rounded}:{radius}"
        return key

    def get_cached_features(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve features from cache if available.
        
        Args:
            cache_key: The unique key for the resource
            
        Returns:
            Dictionary of features if found, None otherwise
        """
        if not self.enabled:
            return None
            
        try:
            data = self.redis_client.get(cache_key)
            if data:
                logger.debug(f"Cache HIT for {cache_key}")
                return json.loads(data)
            else:
                logger.debug(f"Cache MISS for {cache_key}")
                return None
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
            return None

    def cache_features(
        self, 
        cache_key: str, 
        features: Dict[str, Any], 
        ttl_seconds: int = 86400
    ) -> bool:
        """
        Store features in cache with expiration.
        
        Args:
            cache_key: Unique storage key
            features: Dictionary of data to store
            ttl_seconds: Time to live in seconds (default 1 day)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            # Serialize to JSON
            json_data = json.dumps(features)
            
            # Store with expiration
            self.redis_client.setex(
                name=cache_key,
                time=ttl_seconds,
                value=json_data
            )
            return True
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
            return False

    def clear_cache(self, pattern: str = "features:*"):
        """
        Clear cache entries matching a pattern.
        Useful for testing or forcing updates.
        """
        if not self.enabled:
            return
            
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
            logger.info(f"Cleared {len(keys)} keys matching '{pattern}'")
