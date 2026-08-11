from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SheetInfo(BaseModel):
    name: str
    row_count: int
    headers: list[str]


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    sheets: list[SheetInfo]


class ColumnMapping(BaseModel):
    """Semantic field -> actual column header in the uploaded sheet.

    Optional fields are left None when auto-detection can't find a
    confident match; the UI shows those as blank dropdowns for the user
    to fill in (or leave blank, if not applicable to this mode/file).
    """

    name: str
    address: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    place_id: Optional[str] = None
    rating: Optional[str] = None
    review_count: Optional[str] = None
    photo_count: Optional[str] = None
    website: Optional[str] = None


class DetectMappingRequest(BaseModel):
    file_id: str
    sheet_name: str


class DetectMappingResponse(BaseModel):
    headers: list[str]
    suggested_mapping: ColumnMapping


EnrichmentMode = Literal["minimalist", "full_audit"]


class JobConfig(BaseModel):
    file_id: str
    api_key: str
    sheet_name: str
    mode: EnrichmentMode
    column_mapping: ColumnMapping
    max_distance_m: float = 150.0
    min_similarity: float = 0.55
    location_bias_radius_m: float = 500.0
    request_delay_s: float = Field(default=0.12, ge=0.0)


class CreateJobResponse(BaseModel):
    job_id: str


class JobSummary(BaseModel):
    total_rows: int = 0
    verified_matches: int = 0
    flagged_manual: int = 0
    errors: int = 0
    deleted: int = 0
    updated: int = 0


class JobStatus(BaseModel):
    job_id: str
    state: Literal["queued", "running", "complete", "error", "cancelled"]
    processed_rows: int = 0
    total_rows: int = 0
    summary: JobSummary = Field(default_factory=JobSummary)
    logs: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    output_filename: Optional[str] = None
