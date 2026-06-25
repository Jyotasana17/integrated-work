import asyncio
import logging
import uuid
import signal
import time
from datetime import datetime, timezone
from typing import Optional

from executor.configs.settings import settings
from executor.task_queue.consumer import QueueConsumer
from executor.task_queue.publisher import QueuePublisher
from executor.task_queue.models import QueuePayload
from executor.workers.http_executor import HttpExecutor
from executor.workers.heartbeat import WorkerHeartbeat
from executor.persistence.database import AsyncSessionLocal
from sqlalchemy import select
from executor.persistence.models import Scan, Task, ScanResponse, ScanStatus, TaskStatus
from executor.rate_limiter.limiter import RateLimiter
from executor.metrics.prometheus import (
    EXECUTOR_REQUESTS_TOTAL,
    EXECUTOR_LATENCY_SECONDS,
    EXECUTOR_RETRIES_TOTAL
)

logger = logging.getLogger(__name__)

class WorkerEngine:
    def __init__(self, queue_name: str = "tasks:default"):
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.queue_name = queue_name
        self.consumer = QueueConsumer(queue_name=queue_name)
        self.publisher = QueuePublisher(queue_name=queue_name)
        self.http_executor = HttpExecutor()
        self.heartbeat = WorkerHeartbeat(worker_id=self.worker_id)
        self.rate_limiter = RateLimiter()
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)
        self._running = False
        self._tasks = set()
        self.last_active_time = time.time()
        
    def is_idle(self, threshold_seconds: int = 60) -> bool:
        """Returns True if the worker engine has been idle beyond the threshold."""
        # Consider idle only if no active tasks and last active time exceeds threshold
        if len(self._tasks) > 0:
            self.last_active_time = time.time()
            return False
        return (time.time() - self.last_active_time) > threshold_seconds

    async def start(self):
        """Starts the worker engine loop."""
        logger.info(f"Starting Worker Engine {self.worker_id} with concurrency {settings.WORKER_CONCURRENCY}")
        self._running = True
        
        # Start heartbeat
        await self.heartbeat.start()
        
        # Setup graceful shutdown handlers (unix only, ignored on windows during dev but good practice)
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        except NotImplementedError:
            pass # Windows doesn't support add_signal_handler easily

        while self._running:
            # Block until concurrency slot is available
            await self.semaphore.acquire()
            
            if not self._running:
                self.semaphore.release()
                break

            # Fetch task
            payload = await self.consumer.consume()
            if not payload:
                self.semaphore.release()
                continue
                
            self.last_active_time = time.time()
            # Process in background task
            task = asyncio.create_task(self._process_payload(payload))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def stop(self):
        """Gracefully shuts down the worker engine."""
        if not self._running:
            return
            
        logger.info(f"Shutting down Worker Engine {self.worker_id}...")
        self._running = False
        await self.heartbeat.stop()
        await self.http_executor.close()
        
        if self._tasks:
            logger.info(f"Waiting for {len(self._tasks)} active tasks to finish...")
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        logger.info("Worker Engine stopped.")

    async def _process_payload(self, payload: QueuePayload):
        """Processes a single task payload."""
        try:
            await self._mark_task_processing(payload.task_id)

            # 1. Rate Limiting Check
            if not await self.rate_limiter.acquire(payload.url, payload.scan_id):
                raise Exception("Rate limit timeout exceeded")

            # 2. Execute HTTP Request
            try:
                status_code, latency_ms, headers, body = await self.http_executor.execute(
                    method=payload.method,
                    url=payload.url,
                    headers=payload.headers,
                    payload=payload.payload
                )
                
                # Adaptive Rate Limiting on 429
                if status_code == 429:
                    EXECUTOR_REQUESTS_TOTAL.labels(status="429").inc()
                    await self.rate_limiter.report_429(payload.url)
                    raise Exception("HTTP 429 Too Many Requests")

                EXECUTOR_REQUESTS_TOTAL.labels(status="success").inc()
                if latency_ms is not None:
                    EXECUTOR_LATENCY_SECONDS.labels(method=payload.method).observe(latency_ms / 1000.0)
                    
                error_message = None
                task_status = TaskStatus.SUCCESS.value
            except Exception as e:
                status_code = 429 if "429" in str(e) else None
                latency_ms = None
                headers = None
                body = None
                error_message = str(e)
                task_status = TaskStatus.FAILED.value
                if status_code != 429:
                    EXECUTOR_REQUESTS_TOTAL.labels(status="failure").inc()

            # 2. Persist Response to DB
            await self._save_response(
                payload.task_id,
                task_status,
                status_code,
                latency_ms,
                headers,
                body,
                error_message
            )

            # 3. Handle Retry Logic if failed
            if task_status == TaskStatus.FAILED.value:
                await self._handle_retry(payload, error_message)

        except Exception as e:
            logger.error(f"Critical error processing task {payload.task_id}: {e}")
            # Never leave a task stuck in PROCESSING: persist the failure so the
            # scan can complete and the error surfaces to the API/UI.
            try:
                await self._save_response(
                    payload.task_id,
                    TaskStatus.FAILED.value,
                    None, None, None, None,
                    f"Worker error: {e}"
                )
            except Exception as save_err:
                logger.error(f"Failed to persist critical error for {payload.task_id}: {save_err}")
            await self.consumer.send_to_dlq(payload, str(e))
        finally:
            self.semaphore.release()

    async def _mark_task_processing(self, task_id_str: str):
        """Mark a task as processing before execution."""
        async with AsyncSessionLocal() as session:
            try:
                task_id = uuid.UUID(task_id_str)
                task = await session.get(Task, task_id)
                if task:
                    task.status = TaskStatus.PROCESSING.value
                    await session.commit()
                    
                    # Publish event
                    try:
                        import json
                        from executor.task_queue.redis_client import RedisClient
                        redis = RedisClient.get_client()
                        event = {
                            "type": "task_status_updated",
                            "task_id": task_id_str,
                            "scan_id": str(task.scan_id),
                            "status": TaskStatus.PROCESSING.value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "worker_id": self.worker_id
                        }
                        await redis.publish(f"scan:{task.scan_id}:events", json.dumps(event))
                    except Exception as pub_err:
                        logger.warning(f"Failed to publish status update: {pub_err}")
            except Exception as e:
                await session.rollback()
                if isinstance(e, (ValueError, TypeError)):
                    return
                logger.error(f"Failed to mark task {task_id_str} as processing: {e}")

    async def _update_task_status(self, task_id_str: str, status: str):
        """Update a task status outside of response persistence."""
        async with AsyncSessionLocal() as session:
            try:
                task_id = uuid.UUID(task_id_str)
                task = await session.get(Task, task_id)
                if task:
                    task.status = status
                    await session.commit()
                    
                    # Publish event
                    try:
                        import json
                        from executor.task_queue.redis_client import RedisClient
                        redis = RedisClient.get_client()
                        event = {
                            "type": "task_status_updated",
                            "task_id": task_id_str,
                            "scan_id": str(task.scan_id),
                            "status": status,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "worker_id": self.worker_id
                        }
                        await redis.publish(f"scan:{task.scan_id}:events", json.dumps(event))
                    except Exception as pub_err:
                        logger.warning(f"Failed to publish status update: {pub_err}")
            except Exception as e:
                await session.rollback()
                if isinstance(e, (ValueError, TypeError)):
                    return
                logger.error(f"Failed to update status for task {task_id_str}: {e}")

    async def _evaluate_scan_completion(self, scan_id_str: str):
        """Check whether a scan should be marked completed or failed."""
        async with AsyncSessionLocal() as session:
            try:
                scan_id = uuid.UUID(scan_id_str)
                scan = await session.get(Scan, scan_id)
                if not scan:
                    return

                stmt = select(Task.status).where(Task.scan_id == scan_id)
                result = await session.execute(stmt)
                statuses = [row[0] for row in result.all()]
                if not statuses:
                    return
                if any(s in (TaskStatus.QUEUED.value, TaskStatus.PROCESSING.value, TaskStatus.RETRYING.value) for s in statuses):
                    return

                scan.finished_at = datetime.now(timezone.utc)
                scan.status = ScanStatus.COMPLETED.value if all(s == TaskStatus.SUCCESS.value for s in statuses) else ScanStatus.FAILED.value
                await session.commit()
                
                # Publish event
                try:
                    import json
                    from executor.task_queue.redis_client import RedisClient
                    redis = RedisClient.get_client()
                    event = {
                        "type": "scan_completed",
                        "scan_id": scan_id_str,
                        "status": scan.status,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    await redis.publish(f"scan:{scan_id_str}:events", json.dumps(event))
                except Exception as pub_err:
                    logger.warning(f"Failed to publish scan completion event: {pub_err}")
            except Exception as e:
                await session.rollback()
                if isinstance(e, (ValueError, TypeError)):
                    return
                logger.error(f"Failed to evaluate scan completion for {scan_id_str}: {e}")

    async def _save_response(self, task_id_str: str, status: str, status_code: Optional[int], latency: Optional[float], headers: Optional[dict], body: Optional[str], error: Optional[str]):
        """Saves the task response to Postgres."""
        async with AsyncSessionLocal() as session:
            try:
                task_id = uuid.UUID(task_id_str)

                # Update Task Status and attempt count
                db_task = await session.get(Task, task_id)
                if db_task:
                    db_task.status = status
                    db_task.attempts += 1

                # Update or create the response record
                response = await session.scalar(
                    select(ScanResponse).where(ScanResponse.task_id == task_id)
                )
                if response:
                    response.status_code = status_code
                    response.latency_ms = latency
                    response.response_headers = headers
                    response.response_body = body
                    response.error_message = error
                else:
                    response = ScanResponse(
                        task_id=task_id,
                        status_code=status_code,
                        latency_ms=latency,
                        response_headers=headers,
                        response_body=body,
                        error_message=error
                    )
                    session.add(response)

                await session.commit()

                if db_task:
                    # Publish event to Redis pub/sub
                    try:
                        import json
                        from executor.task_queue.redis_client import RedisClient
                        redis = RedisClient.get_client()
                        event = {
                            "type": "task_completed",
                            "task_id": task_id_str,
                            "scan_id": str(db_task.scan_id),
                            "status": status,
                            "status_code": status_code,
                            "latency_ms": latency,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "worker_id": self.worker_id
                        }
                        await redis.publish(f"scan:{db_task.scan_id}:events", json.dumps(event))
                    except Exception as pub_err:
                        logger.warning(f"Failed to publish task update: {pub_err}")

                    await self._evaluate_scan_completion(str(db_task.scan_id))
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error saving response for {task_id_str}: {e}")

    async def _handle_retry(self, payload: QueuePayload, error_message: str):
        """Handles exponential backoff retry for failed tasks."""
        if payload.attempt < payload.max_retries:
            EXECUTOR_RETRIES_TOTAL.inc()
            payload.attempt += 1
            await self._update_task_status(payload.task_id, TaskStatus.RETRYING.value)
            delay = settings.DEFAULT_RETRY_BACKOFF * (2 ** (payload.attempt - 1))
            logger.info(f"Task {payload.task_id} failed. Retrying in {delay}s (Attempt {payload.attempt}/{payload.max_retries})")
            await self.publisher.schedule_delayed(payload, delay_seconds=delay)
        else:
            logger.error(f"Task {payload.task_id} exceeded max retries.")
            await self._update_task_status(payload.task_id, TaskStatus.FAILED.value)
            await self.consumer.send_to_dlq(payload, f"Max retries exceeded. Last error: {error_message}")
