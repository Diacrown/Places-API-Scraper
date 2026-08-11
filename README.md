# Places Enrichment Console

Wraps the Google Places API enrichment pipeline (the one built up over the
Krakow / Toscana / Wroclaw runs) in a web app: drag in a `.xlsx`, configure
the run, watch live progress, download the result. No more hand-editing a
new Colab script for every incoming city file.

## How it works

- **Backend** — FastAPI (`backend/`). Modularized into:
  - `services/places_api.py` — the Google Places API (New) client (Place
    Details + Text Search, cost-optimized field masks)
  - `services/excel_processor.py` — column auto-detection, checkpointing,
    and the two enrichment-mode engines
  - `utils/matching.py` — Haversine distance + fuzzy name-similarity gate
  - `jobs/job_manager.py` — runs a job in a background thread, streams
    progress over SSE
- **Frontend** — React + Vite + Tailwind (`frontend/`). Four-step flow:
  upload → configure → process → download.

### Two enrichment modes (pick per run)

| | **In-place** (`minimalist`) | **Full audit** (`full_audit`) |
|---|---|---|
| Behavior | Overwrites the rating/review-count/photo-count columns you point it at | Appends new audit columns, leaves originals untouched |
| Closed businesses | Row deleted | Moved to a `Removed` tab with a reason stamp |
| Unverified matches | Left silently untouched | Flagged in a `Match` column as `manual check (Xm, 0.XX)` |
| Output | Single sheet, `Working File post API Calls` | Original sheet name + `Removed` tab |

This mirrors the two patterns that came out of the Gemini exploration —
Krakow was full-audit, Toscana/Wroclaw were in-place.

### Column mapping

On upload, the app reads the sheet's headers and guesses which column is
Name / Address / Latitude / Longitude / Place ID / Rating / Review Count /
Photo Count / Website, based on the header spellings seen across the city
files so far (`Name`/`Title`, `Full address`/`Address`, etc. — see
`CANDIDATE_HEADERS` in `services/excel_processor.py`). You get an editable
preview before starting, so a file with different headers just needs a
quick manual fix instead of a new script. Add more candidate spellings to
that dict as new files show new patterns.

### Checkpointing

Same guarantee as the original scripts: progress is saved to a checkpoint
CSV every 100 rows. The checkpoint is keyed by a hash of
`(file, sheet, mode)` rather than by job ID, so if the server restarts or
the job errors out partway through, re-running the *same* file/sheet/mode
combination resumes from where it left off instead of re-billing already
-processed rows. The checkpoint is deleted automatically once a run
completes.

## Local development

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
npm run dev
```
Open the printed Vite URL (typically `http://localhost:5173`) — it proxies
`/api/*` to `http://127.0.0.1:8000` automatically (see `vite.config.js`).

Paste your Google Places API key into the Configuration step at runtime —
it's sent with the job request and used only for that run; it's never
written to disk or logged.

## Deploying

The Dockerfile builds the frontend and serves it *from the same FastAPI
process* as the API (`main.py` mounts `frontend/dist` as static files), so
there's one container, one port, and no CORS to configure.

```bash
docker build -t places-enrichment .
docker run -p 8000:8000 -v $(pwd)/backend/data:/app/backend/data places-enrichment
```
Open `http://localhost:8000` — frontend and API both live there.

The volume mount is optional but recommended in production: it's where
uploads, checkpoints, and output files live, so mounting it means a
container restart mid-run doesn't lose checkpoint progress.

**Where to run it:** any platform that deploys a Dockerfile works as-is —
Railway, Render, Fly.io, or a plain VPS with `docker run`. There's nothing
Vercel/Netlify-specific here since it's one combined service, not a static
site + serverless functions.

**If you'd rather split frontend and backend onto separate domains**
(e.g. a static host for the frontend + a separate API host), build the
frontend with `VITE_API_BASE=https://your-api-domain.com/api npm run
build`, deploy `frontend/dist` as a static site, deploy `backend/` alone
(e.g. `Dockerfile` without the frontend-build stage, or just `pip install
-r requirements.txt && uvicorn main:app`), and change `allow_origins` in
`backend/main.py` from `["*"]` to your frontend's actual domain.

## Extending to a new city file

If a new file's headers don't match anything in `CANDIDATE_HEADERS`
(`services/excel_processor.py`), the editable mapping preview in the UI
lets you fix it for that run with no code change. Only touch the code if
you want the *auto-detect* to recognize a new header spelling by default —
add it to the relevant list in `CANDIDATE_HEADERS`.

## Known limitations / next steps

- Job state is in-memory — if the backend process restarts mid-job, the
  job's live status is lost (the checkpoint survives, so simply
  re-submitting the same file/sheet/mode picks up where it stopped; there's
  just no automatic "resume" button in the UI for that yet).
- Single target sheet per run, matching how every real run so far has
  worked. Multi-sheet full-audit runs (Krakow's original "every sheet
  except Removed/chain/brand/reference" behavior) would need a small
  extension to `run_enrichment` if you need it back.
- The API key is supplied per run rather than stored server-side. Fine for
  a single tech lead running this; if non-technical teammates start using
  it independently, consider moving the key to a server-side secret instead
  of a UI field.
