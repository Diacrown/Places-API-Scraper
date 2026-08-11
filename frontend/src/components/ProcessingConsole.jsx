import { useEffect, useRef } from "react";
import { AlertTriangle, Loader2, Terminal } from "lucide-react";

const SUMMARY_TILES = [
  { key: "verified_matches", label: "Verified", color: "text-teal" },
  { key: "updated", label: "Updated", color: "text-teal" },
  { key: "flagged_manual", label: "Flagged", color: "text-amber" },
  { key: "deleted", label: "Deleted", color: "text-red" },
  { key: "errors", label: "Errors", color: "text-red" },
];

export default function ProcessingConsole({ status, connectionError }) {
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [status?.logs?.length]);

  const total = status?.total_rows || 0;
  const processed = status?.processed_rows || 0;
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

  return (
    <div className="corner-frame bg-surface border border-border rounded-lg p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-ink flex items-center gap-2">
          {status?.state === "running" && (
            <Loader2 size={16} className="animate-spin text-amber" />
          )}
          Processing
        </h2>
        <span className="text-xs font-mono text-ink-dim">
          {processed}/{total || "…"} rows
        </span>
      </div>

      {/* progress bar */}
      <div className="h-2.5 rounded-full bg-surface2 border border-border overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber to-teal transition-[width] duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* live summary tiles */}
      <div className="grid grid-cols-5 gap-2">
        {SUMMARY_TILES.map(({ key, label, color }) => (
          <div key={key} className="bg-surface2 border border-border rounded-md py-2 text-center">
            <div className={`font-mono text-lg font-semibold ${color}`}>
              {status?.summary?.[key] ?? 0}
            </div>
            <div className="text-[11px] text-ink-dim uppercase tracking-wide">{label}</div>
          </div>
        ))}
      </div>

      {/* terminal log */}
      <div>
        <div className="flex items-center gap-1.5 text-xs text-ink-dim mb-1.5">
          <Terminal size={13} /> Live log
        </div>
        <div
          ref={logRef}
          className="scrollbar-thin bg-black/40 border border-border rounded-md p-3 h-48 overflow-y-auto font-mono text-xs text-teal/90 space-y-0.5"
        >
          {(status?.logs ?? []).map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-words">
              <span className="text-ink-dim">$ </span>
              {line}
            </div>
          ))}
          {(!status || status.logs?.length === 0) && (
            <div className="text-ink-dim">Waiting for the job to start...</div>
          )}
        </div>
      </div>

      {connectionError && (
        <div className="flex items-center gap-2 text-red text-sm">
          <AlertTriangle size={14} /> {connectionError}
        </div>
      )}
      {status?.state === "error" && (
        <div className="flex items-center gap-2 text-red text-sm">
          <AlertTriangle size={14} /> {status.error_message}
        </div>
      )}
    </div>
  );
}
