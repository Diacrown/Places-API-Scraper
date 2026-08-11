// Same-origin by default (backend serves the built frontend directly - see
// main.py's StaticFiles mount). Set VITE_API_BASE at build time if you're
// deploying the frontend and backend on separate domains instead.
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore parse failure, fall back to statusText */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  return handle(res);
}

export async function detectMapping(fileId, sheetName) {
  const res = await fetch(`${BASE}/detect-mapping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, sheet_name: sheetName }),
  });
  return handle(res);
}

export async function createJob(config) {
  const res = await fetch(`${BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  return handle(res);
}

export function jobEventsUrl(jobId) {
  return `${BASE}/jobs/${jobId}/events`;
}

export function jobDownloadUrl(jobId) {
  return `${BASE}/jobs/${jobId}/download`;
}
