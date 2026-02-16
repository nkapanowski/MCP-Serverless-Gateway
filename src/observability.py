"""
Logging and observability utilities.
"""
import time
import logging
import json
from typing import Dict, Any, Optional
from contextlib import contextmanager
from functools import wraps
from pythonjsonlogger import jsonlogger


class ObservabilityLogger:
    """Structured JSON logger for observability."""
    
    def __init__(self, name: str = "mcp-gateway"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # JSON formatter
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(latency_ms)s %(error)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_request(
        self, 
        action: str, 
        data: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log a request with structured data."""
        log_data = {
            "timestamp": time.time(),
            "action": action,
            "success": success,
        }
        
        if data:
            log_data["data"] = data
        if latency_ms is not None:
            log_data["latency_ms"] = latency_ms
        if error:
            log_data["error"] = error
        
        if success:
            self.logger.info("Request processed", extra=log_data)
        else:
            self.logger.error("Request failed", extra=log_data)
    
    def log_tool_invocation(
        self,
        tool_name: str,
        latency_ms: float,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log tool invocation metrics."""
        log_data = {
            "timestamp": time.time(),
            "tool_name": tool_name,
            "latency_ms": latency_ms,
            "success": success,
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            self.logger.info("Tool invocation completed", extra=log_data)
        else:
            self.logger.error("Tool invocation failed", extra=log_data)


@contextmanager
def time_operation(operation_name: str = "operation"):
    """Context manager to time operations and log results."""
    start_time = time.time()
    error = None
    
    try:
        yield
    except Exception as e:
        error = str(e)
        raise
    finally:
        latency_ms = (time.time() - start_time) * 1000
        logger = ObservabilityLogger()
        logger.log_request(
            action=operation_name,
            latency_ms=latency_ms,
            success=error is None,
            error=error
        )


def log_timing(func):
    """Decorator to log function execution time."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        error = None
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            logger = ObservabilityLogger()
            logger.log_request(
                action=func.__name__,
                latency_ms=latency_ms,
                success=error is None,
                error=error
            )
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        error = None
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            logger = ObservabilityLogger()
            logger.log_request(
                action=func.__name__,
                latency_ms=latency_ms,
                success=error is None,
                error=error
            )
    
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
