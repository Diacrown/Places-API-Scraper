import { useEffect, useState } from "react";
import { ChevronDown, Eye, EyeOff, KeyRound, Play, Settings2 } from "lucide-react";
import { detectMapping } from "../lib/api";

const FIELD_LABELS = {
  name: "Business name",
  address: "Address",
  latitude: "Latitude",
  longitude: "Longitude",
  place_id: "Google Place ID (optional)",
  rating: "Rating column to update",
  review_count: "Review count column to update",
  photo_count: "Photo count column",
  website: "Website URL (optional)",
};

const REQUIRED_FIELDS = ["name", "address"];

function MappingRow({ field, value, headers, onChange }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <label className="text-sm text-ink-dim shrink-0 w-48">{FIELD_LABELS[field]}</label>
      <select
        value={value || ""}
        onChange={(e) => onChange(field, e.target.value || null)}
        className="flex-1 bg-surface2 border border-border rounded-md px-2.5 py-1.5 text-sm text-ink font-mono focus:outline-none focus:ring-1 focus:ring-amber"
      >
        <option value="">
          {REQUIRED_FIELDS.includes(field) ? "— select column —" : "— not used —"}
        </option>
        {headers.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function ConfigCard({ fileId, sheets, onStart, starting }) {
  const [sheetName, setSheetName] = useState(sheets[0]?.name || "");
  const [mode, setMode] = useState("minimalist");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [headers, setHeaders] = useState([]);
  const [mapping, setMapping] = useState(null);
  const [mappingLoading, setMappingLoading] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [thresholds, setThresholds] = useState({
    max_distance_m: 150,
    min_similarity: 0.55,
    location_bias_radius_m: 500,
    request_delay_s: 0.12,
  });

  useEffect(() => {
    if (!sheetName) return;
    setMappingLoading(true);
    detectMapping(fileId, sheetName)
      .then((res) => {
        setHeaders(res.headers);
        setMapping(res.suggested_mapping);
      })
      .finally(() => setMappingLoading(false));
  }, [fileId, sheetName]);

  const selectedSheet = sheets.find((s) => s.name === sheetName);
  const isExcludedName = /removed|chain|brand|reference/i.test(sheetName);
  const canStart =
    apiKey.trim() &&
    mapping?.name &&
    mapping?.address &&
    !mappingLoading;

  return (
    <div className="corner-frame bg-surface border border-border rounded-lg p-6 space-y-6">
      <div>
        <h2 className="font-semibold text-ink mb-1">Configure this run</h2>
        <p className="text-sm text-ink-dim">
          {sheets.length} sheet{sheets.length !== 1 && "s"} detected in the uploaded file.
        </p>
      </div>

      {/* API key */}
      <div>
        <label className="text-sm text-ink-dim mb-1.5 flex items-center gap-1.5">
          <KeyRound size={14} /> Google Places API key
        </label>
        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="AIzaSy..."
            className="w-full bg-surface2 border border-border rounded-md px-3 py-2 pr-10 text-sm font-mono text-ink focus:outline-none focus:ring-1 focus:ring-amber"
          />
          <button
            type="button"
            onClick={() => setShowKey((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-dim hover:text-ink"
            aria-label={showKey ? "Hide API key" : "Show API key"}
          >
            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <p className="text-xs text-ink-dim mt-1">
          Used only for this run — sent directly to your backend, never stored.
        </p>
      </div>

      {/* Sheet select */}
      <div>
        <label className="text-sm text-ink-dim mb-1.5 block">Target sheet</label>
        <select
          value={sheetName}
          onChange={(e) => setSheetName(e.target.value)}
          className="w-full bg-surface2 border border-border rounded-md px-3 py-2 text-sm font-mono text-ink focus:outline-none focus:ring-1 focus:ring-amber"
        >
          {sheets.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name} ({s.row_count} rows)
            </option>
          ))}
        </select>
        {isExcludedName && (
          <p className="text-xs text-amber mt-1">
            Heads up — this sheet name looks like a "Removed" / reference tab. Make sure that's intentional.
          </p>
        )}
      </div>

      {/* Mode toggle */}
      <div>
        <label className="text-sm text-ink-dim mb-1.5 block">Enrichment mode</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setMode("minimalist")}
            className={[
              "text-left rounded-md border px-3 py-2.5 transition-colors",
              mode === "minimalist"
                ? "border-amber bg-amber/10"
                : "border-border bg-surface2 hover:border-ink-dim",
            ].join(" ")}
          >
            <div className="text-sm font-medium text-ink">In-place update</div>
            <div className="text-xs text-ink-dim mt-0.5">
              Overwrites rating/review/photo columns. Deletes closed businesses.
            </div>
          </button>
          <button
            type="button"
            onClick={() => setMode("full_audit")}
            className={[
              "text-left rounded-md border px-3 py-2.5 transition-colors",
              mode === "full_audit"
                ? "border-amber bg-amber/10"
                : "border-border bg-surface2 hover:border-ink-dim",
            ].join(" ")}
          >
            <div className="text-sm font-medium text-ink">Full audit</div>
            <div className="text-xs text-ink-dim mt-0.5">
              Appends new audit columns + Match status. Moves closures to a Removed tab.
            </div>
          </button>
        </div>
      </div>

      {/* Column mapping preview */}
      <div>
        <label className="text-sm text-ink-dim mb-1.5 block">
          Column mapping {mappingLoading && <span className="text-amber">(detecting...)</span>}
        </label>
        {mapping && (
          <div className="bg-bg/40 border border-border rounded-md px-3 py-1 divide-y divide-border/60">
            {Object.keys(FIELD_LABELS)
              .filter((f) => {
                const isOverwriteTarget = ["rating", "review_count", "photo_count"].includes(f);
                // Full-audit mode appends brand-new audit columns, so it
                // never needs to know which existing column to overwrite.
                return mode === "minimalist" || !isOverwriteTarget;
              })
              .map((field) => (
                <MappingRow
                  key={field}
                  field={field}
                  value={mapping[field]}
                  headers={headers}
                  onChange={(f, v) => setMapping((m) => ({ ...m, [f]: v }))}
                />
              ))}
          </div>
        )}
        <p className="text-xs text-ink-dim mt-1.5">
          Auto-detected from the header row — review before starting, especially rating/review/photo
          columns in-place mode will overwrite.
        </p>
      </div>

      {/* Advanced thresholds */}
      <div>
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex items-center gap-1.5 text-sm text-ink-dim hover:text-ink"
        >
          <Settings2 size={14} />
          Advanced matching thresholds
          <ChevronDown
            size={14}
            className={`transition-transform ${advancedOpen ? "rotate-180" : ""}`}
          />
        </button>
        {advancedOpen && (
          <div className="grid grid-cols-2 gap-3 mt-3 bg-bg/40 border border-border rounded-md p-3">
            {[
              ["max_distance_m", "Max distance (m)"],
              ["min_similarity", "Min name similarity (0-1)"],
              ["location_bias_radius_m", "Search bias radius (m)"],
              ["request_delay_s", "Delay between rows (s)"],
            ].map(([key, label]) => (
              <div key={key}>
                <label className="text-xs text-ink-dim block mb-1">{label}</label>
                <input
                  type="number"
                  step="any"
                  value={thresholds[key]}
                  onChange={(e) =>
                    setThresholds((t) => ({ ...t, [key]: parseFloat(e.target.value) }))
                  }
                  className="w-full bg-surface2 border border-border rounded-md px-2 py-1.5 text-sm font-mono text-ink focus:outline-none focus:ring-1 focus:ring-amber"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        disabled={!canStart || starting}
        onClick={() =>
          onStart({
            file_id: fileId,
            api_key: apiKey.trim(),
            sheet_name: sheetName,
            mode,
            column_mapping: mapping,
            ...thresholds,
          })
        }
        className="w-full flex items-center justify-center gap-2 bg-amber text-bg font-semibold rounded-md py-2.5 disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 transition"
      >
        <Play size={16} />
        {starting ? "Starting..." : `Start enrichment (${selectedSheet?.row_count ?? 0} rows)`}
      </button>
    </div>
  );
}
