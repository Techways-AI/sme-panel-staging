import time
import logging
from functools import wraps
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Performance monitoring
class PerformanceMonitor:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.start_times: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__)
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.start_times[operation] = time.time()
    
    def end_timer(self, operation: str) -> float:
        """End timing an operation and return duration"""
        if operation not in self.start_times:
            return 0.0
        
        duration = time.time() - self.start_times[operation]
        
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append(duration)
        
        # Keep only last 100 measurements
        if len(self.metrics[operation]) > 100:
            self.metrics[operation] = self.metrics[operation][-100:]
        
        del self.start_times[operation]
        
        self.logger.info(f"Performance: {operation} took {duration:.3f}s")
        return duration
    
    def get_average_time(self, operation: str) -> float:
        """Get average time for an operation"""
        if operation not in self.metrics or not self.metrics[operation]:
            return 0.0
        return sum(self.metrics[operation]) / len(self.metrics[operation])
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get performance stats for an operation"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
        
        times = self.metrics[operation]
        return {
            "count": len(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times)
        }
    
    def log_slow_operations(self, threshold: float = 5.0):
        """Log operations that take longer than threshold"""
        for operation, times in self.metrics.items():
            if times:
                avg_time = sum(times) / len(times)
                if avg_time > threshold:
                    self.logger.warning(f"Slow operation detected: {operation} averages {avg_time:.3f}s")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def monitor_performance(operation: str):
    """Decorator to monitor performance of functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            performance_monitor.start_timer(operation)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                performance_monitor.end_timer(operation)
        return wrapper
    return decorator

def log_performance_summary():
    """Log a summary of all performance metrics"""
    logger = logging.getLogger(__name__)
    logger.info("=== Performance Summary ===")
    
    for operation, times in performance_monitor.metrics.items():
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            logger.info(f"{operation}: {len(times)} calls, avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
    
    logger.info("=== End Performance Summary ===") 