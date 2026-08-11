import { useCallback, useRef, useState } from "react";
import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";

export default function UploadDropzone({ onFileSelected, uploading, error }) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  const handleFiles = useCallback(
    (files) => {
      const file = files?.[0];
      if (!file) return;
      onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div
      className={[
        "corner-frame rounded-lg border-2 border-dashed p-10 text-center transition-colors cursor-pointer",
        dragActive ? "border-amber bg-amber/5" : "border-border bg-surface hover:border-ink-dim",
      ].join(" ")}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        handleFiles(e.dataTransfer.files);
      }}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {uploading ? (
        <Loader2 className="mx-auto mb-3 animate-spin text-amber" size={32} />
      ) : (
        <UploadCloud className="mx-auto mb-3 text-ink-dim" size={32} />
      )}
      <p className="text-ink font-medium">
        {uploading ? "Reading workbook..." : "Drop your .xlsx file here"}
      </p>
      <p className="text-ink-dim text-sm mt-1">
        or click to browse — sheet names and columns are read automatically
      </p>
      <p className="text-ink-dim text-xs mt-4 flex items-center justify-center gap-1.5">
        <FileSpreadsheet size={14} /> .xlsx / .xls only
      </p>
      {error && <p className="text-red text-sm mt-4">{error}</p>}
    </div>
  );
}
