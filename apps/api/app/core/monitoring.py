import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def monitor_tool_execution(tool_name):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                status = "success"
                return result
            except Exception as e:
                status = "failure"
                raise e
            finally:
                duration = time.time() - start_time
                # Log to a structured logger (e.g., JSON format)
                logger.info({
                    "event": "tool_execution",
                    "tool_name": tool_name,
                    "duration_ms": duration * 1000,
                    "status": status,
                    "args": kwargs
                })
        return wrapper
    return decorator
