import { Check } from "lucide-react";

const STEPS = [
  { key: "upload", label: "Upload" },
  { key: "configure", label: "Configure" },
  { key: "process", label: "Process" },
  { key: "download", label: "Download" },
];

export default function PipelineRail({ activeIndex }) {
  return (
    <nav
      aria-label="Enrichment pipeline progress"
      className="flex md:flex-col gap-0 md:w-40 shrink-0"
    >
      {STEPS.map((step, i) => {
        const state =
          i < activeIndex ? "complete" : i === activeIndex ? "active" : "pending";
        return (
          <div key={step.key} className="flex md:flex-col items-center md:items-start flex-1 md:flex-none">
            <div className="flex md:flex-col items-center md:items-start w-full">
              <div className="flex items-center gap-2 md:gap-3">
                <div
                  className={[
                    "flex items-center justify-center w-7 h-7 rounded-full border text-xs font-mono shrink-0 transition-colors",
                    state === "complete" && "bg-teal/15 border-teal text-teal",
                    state === "active" && "bg-amber/15 border-amber text-amber animate-pulse",
                    state === "pending" && "bg-surface2 border-border text-ink-dim",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {state === "complete" ? <Check size={14} /> : i + 1}
                </div>
                <span
                  className={[
                    "text-sm font-medium hidden md:inline",
                    state === "pending" ? "text-ink-dim" : "text-ink",
                  ].join(" ")}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={[
                    "md:ml-3 md:my-1 md:w-px md:h-6 h-px w-full my-3 md:my-1 flex-1 md:flex-none",
                    state === "complete" ? "bg-teal/50" : "bg-border",
                  ].join(" ")}
                />
              )}
            </div>
          </div>
        );
      })}
    </nav>
  );
}
