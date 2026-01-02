"""
Worker utilities - background thread for long-running operations.
"""
import threading
import queue
from typing import Callable, Any, Optional
from dataclasses import dataclass


@dataclass
class WorkerResult:
    """Result from a worker operation."""
    success: bool
    result: Any = None
    error: Optional[Exception] = None


class WorkerThread(threading.Thread):
    """
    Background worker thread for running long tasks without blocking the GUI.
    
    Usage:
        def long_task(progress_callback):
            for i in range(100):
                # Do work...
                progress_callback(i, 100, "Processing...")
            return result
        
        worker = WorkerThread(long_task)
        worker.start()
        
        # In GUI update loop:
        while worker.is_alive():
            progress = worker.get_progress()
            if progress:
                update_progress_bar(progress)
            root.update()
        
        result = worker.get_result()
    """
    
    def __init__(self, target: Callable, *args, **kwargs):
        super().__init__(daemon=True)
        self.target = target
        self.args = args
        self.kwargs = kwargs
        
        self._result: Optional[WorkerResult] = None
        self._progress_queue: queue.Queue = queue.Queue()
        self._cancelled = False
    
    def run(self):
        """Execute the target function."""
        try:
            # Add progress callback to kwargs if the function supports it
            self.kwargs['progress_callback'] = self._report_progress
            result = self.target(*self.args, **self.kwargs)
            self._result = WorkerResult(success=True, result=result)
        except Exception as e:
            self._result = WorkerResult(success=False, error=e)
    
    def _report_progress(self, current: int, total: int, message: str):
        """Report progress (called from worker function)."""
        if self._cancelled:
            raise InterruptedError("Operation cancelled")
        self._progress_queue.put((current, total, message))
    
    def get_progress(self) -> Optional[tuple]:
        """Get latest progress update (non-blocking)."""
        try:
            return self._progress_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_result(self) -> Optional[WorkerResult]:
        """Get the result after thread completes."""
        return self._result
    
    def cancel(self):
        """Request cancellation (cooperative)."""
        self._cancelled = True


class TaskQueue:
    """
    Queue for managing multiple background tasks.
    """
    
    def __init__(self, max_workers: int = 1):
        self.max_workers = max_workers
        self._queue: queue.Queue = queue.Queue()
        self._workers: list = []
        self._running = False
    
    def add_task(self, target: Callable, *args, **kwargs) -> str:
        """Add a task to the queue. Returns task ID."""
        import uuid
        task_id = str(uuid.uuid4())
        self._queue.put((task_id, target, args, kwargs))
        return task_id
    
    def start(self):
        """Start processing the queue."""
        self._running = True
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._process_queue, daemon=True)
            worker.start()
            self._workers.append(worker)
    
    def stop(self):
        """Stop processing."""
        self._running = False
    
    def _process_queue(self):
        """Process tasks from the queue."""
        while self._running:
            try:
                task_id, target, args, kwargs = self._queue.get(timeout=0.5)
                try:
                    target(*args, **kwargs)
                except Exception as e:
                    print(f"Task {task_id} failed: {e}")
            except queue.Empty:
                continue
