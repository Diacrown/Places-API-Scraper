import { CheckCircle2, Download, RotateCcw } from "lucide-react";
import { jobDownloadUrl } from "../lib/api";

const TILES = [
  { key: "total_rows", label: "Total rows", from: "top" },
  { key: "verified_matches", label: "Verified" },
  { key: "updated", label: "Updated" },
  { key: "flagged_manual", label: "Flagged for review" },
  { key: "deleted", label: "Deleted / closed" },
  { key: "errors", label: "Errors" },
];

export default function DownloadCenter({ status, onReset }) {
  const summary = status?.summary ?? {};

  return (
    <div className="corner-frame bg-surface border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center gap-2 text-teal">
        <CheckCircle2 size={20} />
        <h2 className="font-semibold text-ink">Run complete</h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {TILES.map(({ key, label }) => (
          <div key={key} className="bg-surface2 border border-border rounded-md p-3">
            <div className="font-mono text-2xl font-semibold text-ink">
              {key === "total_rows" ? status?.total_rows ?? 0 : summary[key] ?? 0}
            </div>
            <div className="text-xs text-ink-dim mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      <a
        href={jobDownloadUrl(status.job_id)}
        download
        className="w-full flex items-center justify-center gap-2 bg-teal text-bg font-semibold rounded-md py-2.5 hover:brightness-110 transition"
      >
        <Download size={16} />
        Download enriched file
      </a>

      <button
        type="button"
        onClick={onReset}
        className="w-full flex items-center justify-center gap-2 text-ink-dim text-sm hover:text-ink transition"
      >
        <RotateCcw size={14} /> Run another file
      </button>
    </div>
  );
}
