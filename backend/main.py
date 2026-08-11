from __future__ import annotations

import os
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from jobs.job_manager import job_manager
from models import (
    CreateJobResponse,
    DetectMappingRequest,
    DetectMappingResponse,
    JobConfig,
    JobStatus,
    UploadResponse,
)
from services.excel_processor import detect_column_mapping, load_workbook_info

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Places Enrichment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin before deploying
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# file_id -> path on disk, so /detect-mapping and /jobs can find the upload
# without trusting a client-supplied path.
_FILES: dict[str, str] = {}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Please upload an .xlsx or .xls file.")

    file_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")
    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)
    _FILES[file_id] = path

    try:
        sheets = load_workbook_info(path)
    except Exception as err:  # noqa: BLE001
        raise HTTPException(400, f"Could not read that file as Excel: {err}") from err

    return UploadResponse(file_id=file_id, filename=file.filename, sheets=sheets)


@app.post("/api/detect-mapping", response_model=DetectMappingResponse)
async def detect_mapping(req: DetectMappingRequest):
    path = _FILES.get(req.file_id)
    if not path:
        raise HTTPException(404, "Unknown file_id - upload the file again.")
    sheets = load_workbook_info(path)
    sheet = next((s for s in sheets if s.name == req.sheet_name), None)
    if sheet is None:
        raise HTTPException(404, f"Sheet '{req.sheet_name}' not found in that file.")
    mapping = detect_column_mapping(sheet.headers)
    return DetectMappingResponse(headers=sheet.headers, suggested_mapping=mapping)


@app.post("/api/jobs", response_model=CreateJobResponse)
async def create_job(config: JobConfig, background_tasks: BackgroundTasks):
    path = _FILES.get(config.file_id)
    if not path:
        raise HTTPException(404, "Unknown file_id - upload the file again.")

    job_id = job_manager.create_job(config, path)
    background_tasks.add_task(job_manager.run, job_id, path)
    return CreateJobResponse(job_id=job_id)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    record = job_manager.get(job_id)
    if record is None:
        raise HTTPException(404, "Unknown job_id.")
    return record.to_status()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    if job_manager.get(job_id) is None:
        raise HTTPException(404, "Unknown job_id.")
    return StreamingResponse(job_manager.stream(job_id), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
async def download_job_output(job_id: str):
    record = job_manager.get(job_id)
    if record is None:
        raise HTTPException(404, "Unknown job_id.")
    if record.state != "complete" or not record.output_path:
        raise HTTPException(409, "Job isn't finished yet.")
    return FileResponse(
        record.output_path,
        filename=os.path.basename(record.output_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve the built frontend (frontend/dist) as a single-origin deployment so
# there's no CORS to configure in production: one process, one port. In dev
# this directory won't exist yet (you're running `npm run dev` separately
# with its proxy instead), so the mount is skipped rather than erroring.
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
