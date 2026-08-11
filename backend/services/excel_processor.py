"""
Everything pandas-facing: reading the uploaded workbook, auto-detecting
which column is which, running the row-by-row enrichment loop for either
mode, checkpointing progress, and writing the final .xlsx deliverable.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Callable, Optional

import pandas as pd

from models import ColumnMapping, EnrichmentMode, JobConfig, JobSummary, SheetInfo
from services.places_api import PlacesAPIError, PlacesClient
from utils.matching import format_photo_count, verify_match

# ---------------------------------------------------------------------------
# Column auto-detection
# ---------------------------------------------------------------------------

# Each semantic field maps to a list of header spellings seen across the
# Krakow / Toscana / Wroclaw files so far. Matching is done on a normalized
# (lowercased, punctuation-stripped) header, first hit wins.
CANDIDATE_HEADERS: dict[str, list[str]] = {
    "name": ["name", "title", "company name", "business name", "store name"],
    "address": ["full address", "address", "street address"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lng", "lon", "long"],
    "place_id": ["google place id", "place_id", "place id"],
    "rating": ["reviews rating", "rating score", "rating"],
    "review_count": [
        "reviews count",
        "exact review count",
        "review count",
        "user rating count",
        "userratingcount",
    ],
    "photo_count": ["photos count", "photo count"],
    "website": ["current website url", "website", "website url", "websiteuri"],
}

# Sheets whose names contain any of these are excluded from "process every
# sheet" style runs (full-audit mode's original multi-tab behavior). Not
# used to filter the dropdown - just surfaced as a warning in the UI.
EXCLUDED_SHEET_KEYWORDS = ["removed", "chain", "brand", "reference"]


def _normalize_header(header: str) -> str:
    return str(header).strip().lower()


def detect_column_mapping(headers: list[str]) -> ColumnMapping:
    normalized = {_normalize_header(h): h for h in headers}
    detected: dict[str, Optional[str]] = {}
    for field, candidates in CANDIDATE_HEADERS.items():
        match = None
        for candidate in candidates:
            if candidate in normalized:
                match = normalized[candidate]
                break
        detected[field] = match

    # name/address are required by ColumnMapping; fall back to the first
    # unmapped header rather than leaving the model invalid, and let the
    # user fix it in the editable preview.
    if not detected.get("name"):
        detected["name"] = headers[0] if headers else ""
    if not detected.get("address"):
        detected["address"] = headers[1] if len(headers) > 1 else detected["name"]

    return ColumnMapping(**detected)


def load_workbook_info(path: str) -> list[SheetInfo]:
    excel_file = pd.ExcelFile(path)
    sheets = []
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=0)
        full_df = pd.read_excel(excel_file, sheet_name=sheet_name, usecols=[0])
        sheets.append(
            SheetInfo(
                name=sheet_name,
                row_count=len(full_df),
                headers=list(df.columns.astype(str)),
            )
        )
    return sheets


def run_key_for(file_id: str, sheet_name: str, mode: str) -> str:
    """Deterministic key so re-submitting the same file/sheet/mode after a
    crash resumes from the same checkpoint instead of starting over, even
    though each API-level job run gets its own job_id."""
    raw = f"{file_id}|{sheet_name}|{mode}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Enrichment engine
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int, JobSummary], None]
LogCallback = Callable[[str], None]

CHECKPOINT_EVERY = 100
LOG_EVERY = 25


class EnrichmentEngine:
    def __init__(
        self,
        config: JobConfig,
        checkpoint_path: str,
        on_progress: ProgressCallback,
        on_log: LogCallback,
    ):
        self.config = config
        self.checkpoint_path = checkpoint_path
        self.on_progress = on_progress
        self.on_log = on_log
        self.client = PlacesClient(
            api_key=config.api_key,
            location_bias_radius_m=config.location_bias_radius_m,
        )
        self.summary = JobSummary()

    # -- shared helpers -----------------------------------------------------

    def _load_checkpoint(self, df: pd.DataFrame, tracking_cols: list[str]) -> pd.DataFrame:
        if os.path.exists(self.checkpoint_path):
            self.on_log(f"Found checkpoint at {os.path.basename(self.checkpoint_path)}. Resuming...")
            checkpoint_df = pd.read_csv(self.checkpoint_path)
            df.update(checkpoint_df)
            for col in tracking_cols:
                if col in df.columns and df[col].dtype != bool:
                    df[col] = df[col].fillna(False).astype(bool)
        return df

    def _save_checkpoint(self, df: pd.DataFrame) -> None:
        df.to_csv(self.checkpoint_path, index=False)

    def _row_field(self, row: pd.Series, column: Optional[str], default=None):
        if not column or column not in row.index:
            return default
        value = row.get(column)
        return default if pd.isna(value) else value

    # -- mode: minimalist -----------------------------------------------------

    def run_minimalist(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = self.config.column_mapping
        rating_col = mapping.rating or "Rating"
        review_col = mapping.review_count or "Review Count"
        photo_col = mapping.photo_count or "Photo Count"

        for col in (rating_col, review_col, photo_col):
            if col not in df.columns:
                df[col] = None
        for col in ("_to_delete", "_processed"):
            if col not in df.columns:
                df[col] = False

        df = self._load_checkpoint(df, ["_to_delete", "_processed"])

        total_rows = len(df)
        self.summary.total_rows = total_rows
        self.on_log(f"Starting run for {total_rows} rows (minimalist / in-place mode)...")

        for idx, row in df.iterrows():
            if bool(row.get("_processed")):
                if bool(row.get("_to_delete")):
                    self.summary.deleted += 1
                elif pd.notna(row.get(rating_col)):
                    self.summary.updated += 1
                self._tick(idx + 1, total_rows)
                continue

            time.sleep(self.config.request_delay_s)
            name = str(self._row_field(row, mapping.name, ""))
            address = str(self._row_field(row, mapping.address, ""))
            lat = self._row_field(row, mapping.latitude)
            lng = self._row_field(row, mapping.longitude)
            place_id = self._row_field(row, mapping.place_id)

            try:
                if place_id:
                    result = self.client.get_place_details(str(place_id).strip())
                else:
                    result = self.client.search_text(name, address, lat, lng)

                if result is None:
                    pass  # no candidate found - leave row untouched, silently
                elif place_id:
                    # Path A is deterministic - no gate needed.
                    if result.business_status == "CLOSED_PERMANENTLY":
                        df.at[idx, "_to_delete"] = True
                        self.summary.deleted += 1
                    else:
                        self._apply_minimalist_update(df, idx, result, rating_col, review_col, photo_col)
                        self.summary.updated += 1
                else:
                    verification = verify_match(
                        lat, lng, name, result.latitude, result.longitude, result.name,
                        self.config.max_distance_m, self.config.min_similarity,
                    )
                    if verification.passed:
                        if result.business_status == "CLOSED_PERMANENTLY":
                            df.at[idx, "_to_delete"] = True
                            self.summary.deleted += 1
                        else:
                            self._apply_minimalist_update(df, idx, result, rating_col, review_col, photo_col)
                            self.summary.updated += 1
                    else:
                        self.summary.flagged_manual += 1
            except PlacesAPIError as err:
                self.summary.errors += 1
                self.on_log(f"Row {idx + 1}: error - {err}")

            df.at[idx, "_processed"] = True
            self._tick(idx + 1, total_rows)
            if (idx + 1) % CHECKPOINT_EVERY == 0 or (idx + 1) == total_rows:
                self._save_checkpoint(df)

        final_df = df[df["_to_delete"] == False].copy()  # noqa: E712
        final_df.drop(columns=["_to_delete", "_processed"], inplace=True, errors="ignore")
        return final_df

    def _apply_minimalist_update(self, df, idx, result, rating_col, review_col, photo_col):
        df.at[idx, rating_col] = result.rating
        df.at[idx, review_col] = result.user_rating_count
        df.at[idx, photo_col] = format_photo_count(result.photos)

    # -- mode: full audit -----------------------------------------------------

    def run_full_audit(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        audit_cols = [
            "Exact Review Count",
            "Rating Score",
            "Photo Count",
            "Google Place ID",
            "Current Website URL",
            "Online-Only Flag",
            "Match",
            "_business_status",
            "_processed",
        ]
        for col in audit_cols:
            if col not in df.columns:
                df[col] = None

        df = self._load_checkpoint(df, ["_processed"])

        total_rows = len(df)
        self.summary.total_rows = total_rows
        self.on_log(f"Starting run for {total_rows} rows (full audit mode)...")

        mapping = self.config.column_mapping
        for idx, row in df.iterrows():
            if bool(row.get("_processed")):
                match_val = str(row.get("Match", ""))
                if "manual check" in match_val:
                    self.summary.flagged_manual += 1
                elif "Verified" in match_val:
                    self.summary.verified_matches += 1
                elif match_val.startswith("Error:"):
                    self.summary.errors += 1
                self._tick(idx + 1, total_rows)
                continue

            time.sleep(self.config.request_delay_s)
            name = str(self._row_field(row, mapping.name, ""))
            address = str(self._row_field(row, mapping.address, ""))
            lat = self._row_field(row, mapping.latitude)
            lng = self._row_field(row, mapping.longitude)
            place_id = self._row_field(row, mapping.place_id)

            try:
                if place_id:
                    result = self.client.get_place_details(str(place_id).strip())
                    self._apply_audit_fields(df, idx, result)
                    df.at[idx, "Match"] = "Verified (Place ID)"
                    self.summary.verified_matches += 1
                else:
                    result = self.client.search_text(name, address, lat, lng)
                    if result is None:
                        df.at[idx, "Match"] = "manual check (0m, 0.00)"
                        self.summary.flagged_manual += 1
                    else:
                        verification = verify_match(
                            lat, lng, name, result.latitude, result.longitude, result.name,
                            self.config.max_distance_m, self.config.min_similarity,
                        )
                        if verification.passed:
                            self._apply_audit_fields(df, idx, result)
                            df.at[idx, "Match"] = "Verified"
                            self.summary.verified_matches += 1
                        else:
                            df.at[idx, "Match"] = verification.flag_text
                            self.summary.flagged_manual += 1
            except PlacesAPIError as err:
                df.at[idx, "Match"] = f"Error: {err}"
                self.summary.errors += 1

            df.at[idx, "_processed"] = True
            self._tick(idx + 1, total_rows)
            if (idx + 1) % CHECKPOINT_EVERY == 0 or (idx + 1) == total_rows:
                self._save_checkpoint(df)

        closed_mask = df["_business_status"] == "CLOSED_PERMANENTLY"
        df_closed = df[closed_mask].copy()
        df_closed["Removal Reason"] = "Permanently Closed according to Google Places API"
        df_active = df[~closed_mask].copy()

        for frame in (df_active, df_closed):
            frame.drop(columns=["_business_status", "_processed"], inplace=True, errors="ignore")
        self.summary.deleted = len(df_closed)  # "deleted" == moved out of the active sheet
        return df_active, df_closed

    def _apply_audit_fields(self, df, idx, result):
        df.at[idx, "Google Place ID"] = result.place_id
        df.at[idx, "Exact Review Count"] = result.user_rating_count
        df.at[idx, "Rating Score"] = result.rating
        df.at[idx, "Photo Count"] = format_photo_count(result.photos)
        df.at[idx, "Current Website URL"] = result.website_uri
        df.at[idx, "Online-Only Flag"] = result.pure_service_area_business
        df.at[idx, "_business_status"] = result.business_status

    # -- progress plumbing -----------------------------------------------------

    def _tick(self, processed: int, total: int) -> None:
        self.on_progress(processed, total, self.summary)
        if processed % LOG_EVERY == 0 or processed == total:
            self.on_log(
                f"Progress: {processed}/{total} rows | "
                f"Verified: {self.summary.verified_matches} | Updated: {self.summary.updated} | "
                f"Flagged: {self.summary.flagged_manual} | Deleted: {self.summary.deleted} | "
                f"Errors: {self.summary.errors}"
            )


def run_enrichment(
    input_path: str,
    sheet_name: str,
    mode: EnrichmentMode,
    config: JobConfig,
    checkpoint_path: str,
    output_path: str,
    on_progress: ProgressCallback,
    on_log: LogCallback,
) -> JobSummary:
    df = pd.read_excel(input_path, sheet_name=sheet_name)
    engine = EnrichmentEngine(config, checkpoint_path, on_progress, on_log)

    if mode == "minimalist":
        final_df = engine.run_minimalist(df)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            final_df.to_excel(writer, sheet_name="Working File post API Calls", index=False)
    else:
        df_active, df_closed = engine.run_full_audit(df)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_active.to_excel(writer, sheet_name=sheet_name, index=False)
            # Preserve any pre-existing Removed tab from the original file.
            try:
                original_removed = pd.read_excel(input_path, sheet_name="Removed")
                combined_removed = pd.concat([original_removed, df_closed], ignore_index=True)
            except (ValueError, FileNotFoundError):
                combined_removed = df_closed
            combined_removed.to_excel(writer, sheet_name="Removed", index=False)

    on_log(
        f"Run complete. Total: {engine.summary.total_rows} | "
        f"Verified: {engine.summary.verified_matches} | Updated: {engine.summary.updated} | "
        f"Flagged: {engine.summary.flagged_manual} | Deleted: {engine.summary.deleted} | "
        f"Errors: {engine.summary.errors}"
    )
    # Checkpoint has served its purpose once the output is written.
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    return engine.summary
