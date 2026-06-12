from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url


def build_redis(redis_url: str) -> Redis:
    return redis_from_url(redis_url, decode_responses=True)
