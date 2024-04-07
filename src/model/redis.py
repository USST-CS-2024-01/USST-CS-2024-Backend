import asyncio
import pickle
import time

import redis.asyncio as redis


class RedisClient:
    def __init__(self, host, port, db, password):
        self.client = redis.Redis(host=host, port=port, db=db, password=password)

    async def get(self, key):
        return await self.client.get(key)

    async def set(self, key, value, expire=None):
        await self.client.set(key, value, ex=expire)

    async def update_expire(self, key, expire):
        await self.client.expire(key, expire)

    async def get_pickle(self, key):
        data = await self.client.get(key)
        if data:
            return pickle.loads(data)
        return None

    async def set_pickle(self, key, value, expire=None):
        await self.client.set(key, pickle.dumps(value), ex=expire)

    async def delete(self, key):
        await self.client.delete(key)

    async def keys(self, pattern):
        return self.client.keys(pattern)

    async def flushdb(self):
        await self.client.flushdb()

    def __del__(self):
        self.client.connection_pool.disconnect()
