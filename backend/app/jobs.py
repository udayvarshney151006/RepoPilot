"""RQ deployment queue and bounded local executor; all handlers persist their state."""
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="repopilot-job")
logger = logging.getLogger("repopilot.jobs")


def dispatch(kind: str, entity_id: str):
    if kind == "index":
        from app.ingestion import index_repository
        index_repository(entity_id)
    elif kind == "agent":
        from app.agents import execute_agent
        execute_agent(entity_id)
    elif kind == "evaluation":
        from app.evaluations import execute_evaluation
        execute_evaluation(entity_id)
    else:
        raise ValueError("Unknown background job type")


def submit(kind: str, entity_id: str):
    if settings.job_backend == "rq":
        from redis import Redis
        from rq import Queue
        from rq.serializers import JSONSerializer
        if not settings.redis_url:
            raise ValueError("REDIS_URL is required for JOB_BACKEND=rq")
        Queue("repopilot", connection=Redis.from_url(settings.redis_url), serializer=JSONSerializer).enqueue(
            dispatch, kind, entity_id, job_timeout=600, result_ttl=3600, failure_ttl=86400)
    elif settings.job_backend == "local":
        executor.submit(dispatch, kind, entity_id)
    else:
        raise ValueError("JOB_BACKEND must be local or rq")
