import os

from redis import Redis
from rq import SpawnWorker, Worker
from rq.serializers import JSONSerializer

from app.config import settings

if __name__ == "__main__":
    worker_class = SpawnWorker if os.name == "nt" else Worker
    worker_class(["repopilot"], connection=Redis.from_url(settings.redis_url), serializer=JSONSerializer).work()
