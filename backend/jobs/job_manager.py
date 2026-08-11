"""
Tracks running/completed jobs in memory and exposes an async generator each
SSE connection can consume. The enrichment loop itself is synchronous
(blocking requests calls + time.sleep), so it runs via FastAPI's
BackgroundTasks, which executes sync callables in a worker thread - this
dict is the only thing shared between that thread and the event loop, and
plain dict/attribute writes are safe under the GIL for this access pattern.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from models import JobConfig, JobStatus, JobSummary
from services.excel_processor import run_enrichment, run_key_for

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "checkpoints")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "outputs")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class _JobRecord:
    job_id: str
    config: JobConfig
    state: str = "queued"
    processed_rows: int = 0
    total_rows: int = 0
    summary: JobSummary = field(default_factory=JobSummary)
    logs: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def to_status(self) -> JobStatus:
        with self.lock:
            return JobStatus(
                job_id=self.job_id,
                state=self.state,  # type: ignore[arg-type]
                processed_rows=self.processed_rows,
                total_rows=self.total_rows,
                summary=self.summary.model_copy(),
                logs=list(self.logs[-200:]),
                error_message=self.error_message,
                output_filename=os.path.basename(self.output_path) if self.output_path else None,
            )


class JobManager:
    def __init__(self):
        self._jobs: dict[str, _JobRecord] = {}

    def create_job(self, config: JobConfig, input_path: str) -> str:
        job_id = str(uuid.uuid4())
        record = _JobRecord(job_id=job_id, config=config)
        self._jobs[job_id] = record
        return job_id

    def get(self, job_id: str) -> Optional[_JobRecord]:
        return self._jobs.get(job_id)

    def run(self, job_id: str, input_path: str) -> None:
        """Executed inside FastAPI's BackgroundTasks worker thread."""
        record = self._jobs[job_id]
        config = record.config
        run_key = run_key_for(config.file_id, config.sheet_name, config.mode)
        checkpoint_path = os.path.join(CHECKPOINT_DIR, f"{run_key}.csv")
        output_path = os.path.join(OUTPUT_DIR, f"{job_id}_enriched.xlsx")

        def on_progress(processed: int, total: int, summary: JobSummary) -> None:
            with record.lock:
                record.state = "running"
                record.processed_rows = processed
                record.total_rows = total
                record.summary = summary.model_copy()

        def on_log(line: str) -> None:
            with record.lock:
                record.logs.append(line)

        try:
            with record.lock:
                record.state = "running"
            summary = run_enrichment(
                input_path=input_path,
                sheet_name=config.sheet_name,
                mode=config.mode,
                config=config,
                checkpoint_path=checkpoint_path,
                output_path=output_path,
                on_progress=on_progress,
                on_log=on_log,
            )
            with record.lock:
                record.state = "complete"
                record.summary = summary
                record.output_path = output_path
        except Exception as err:  # noqa: BLE001 - surface any failure to the UI
            with record.lock:
                record.state = "error"
                record.error_message = str(err)
                record.logs.append(f"Fatal error: {err}")

    async def stream(self, job_id: str):
        """Async generator yielding SSE-formatted status snapshots."""
        record = self._jobs.get(job_id)
        if record is None:
            yield f"event: error\ndata: {json.dumps({'message': 'job not found'})}\n\n"
            return

        last_payload = None
        while True:
            status = record.to_status()
            payload = status.model_dump_json()
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if status.state in ("complete", "error", "cancelled"):
                break
            await asyncio.sleep(0.4)


job_manager = JobManager()
