import time
import threading
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

class JobService:
    def __init__(self, max_workers: int = 4):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def create_job(self, job_id: str, operation: str, input_filename: str) -> Dict[str, Any]:
        with self._lock:
            job = {
                "job_id": job_id,
                "operation": operation,
                "input_filename": input_filename,
                "status": "pending",
                "progress": 0,
                "message": "Queued for processing...",
                "output_filename": None,
                "output_filepath": None,
                "output_mimetype": None,
                "output_size": 0,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time()
            }
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)
                self._jobs[job_id]["updated_at"] = time.time()

    def set_progress(self, job_id: str, progress: int, message: str = ""):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "processing"
                self._jobs[job_id]["progress"] = min(100, max(0, progress))
                if message:
                    self._jobs[job_id]["message"] = message
                self._jobs[job_id]["updated_at"] = time.time()

    def set_completed(self, job_id: str, output_filepath: str, output_filename: str, output_mimetype: str = "application/octet-stream", output_size: int = 0):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "completed"
                self._jobs[job_id]["progress"] = 100
                self._jobs[job_id]["message"] = "Processing completed successfully!"
                self._jobs[job_id]["output_filepath"] = output_filepath
                self._jobs[job_id]["output_filename"] = output_filename
                self._jobs[job_id]["output_mimetype"] = output_mimetype
                self._jobs[job_id]["output_size"] = output_size
                self._jobs[job_id]["updated_at"] = time.time()

    def set_failed(self, job_id: str, error_message: str):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error_message
                self._jobs[job_id]["message"] = f"Failed: {error_message}"
                self._jobs[job_id]["updated_at"] = time.time()

    def submit_task(self, fn, *args, **kwargs):
        """Submit job worker function to background thread pool."""
        return self._executor.submit(fn, *args, **kwargs)

# Global singleton job service
job_service = JobService()
