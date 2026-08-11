import { useMemo, useState } from "react";
import { Radar } from "lucide-react";
import PipelineRail from "./components/PipelineRail.jsx";
import UploadDropzone from "./components/UploadDropzone.jsx";
import ConfigCard from "./components/ConfigCard.jsx";
import ProcessingConsole from "./components/ProcessingConsole.jsx";
import DownloadCenter from "./components/DownloadCenter.jsx";
import { uploadFile, createJob, jobEventsUrl } from "./lib/api.js";
import { useSSE } from "./hooks/useSSE.js";

const STEP_INDEX = { upload: 0, configure: 1, processing: 2, done: 3 };

export default function App() {
  const [step, setStep] = useState("upload");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadResult, setUploadResult] = useState(null); // { file_id, filename, sheets }
  const [starting, setStarting] = useState(false);
  const [jobId, setJobId] = useState(null);

  const eventsUrl = useMemo(() => (jobId ? jobEventsUrl(jobId) : null), [jobId]);
  const { status, connectionError } = useSSE(eventsUrl, {
    enabled: step === "processing",
  });
  const jobDone = step === "processing" && status?.state === "complete";

  async function handleFileSelected(file) {
    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadFile(file);
      setUploadResult(result);
      setStep("configure");
    } catch (err) {
      setUploadError(err.message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleStart(config) {
    setStarting(true);
    try {
      const { job_id } = await createJob(config);
      setJobId(job_id);
      setStep("processing");
    } catch (err) {
      setUploadError(err.message || "Could not start the job.");
    } finally {
      setStarting(false);
    }
  }

  function handleReset() {
    setStep("upload");
    setUploadResult(null);
    setJobId(null);
    setUploadError(null);
  }

  const railIndex = jobDone ? 3 : STEP_INDEX[step];

  return (
    <div className="min-h-screen text-ink">
      <header className="border-b border-border">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-amber/10 border border-amber/40 flex items-center justify-center text-amber">
            <Radar size={18} />
          </div>
          <div>
            <h1 className="font-semibold text-ink leading-tight">Places Enrichment Console</h1>
            <p className="text-xs text-ink-dim">
              Verify &amp; refresh a store database against the Google Places API
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 flex flex-col md:flex-row gap-10">
        <PipelineRail activeIndex={railIndex} />

        <div className="flex-1 max-w-2xl">
          {step === "upload" && (
            <UploadDropzone
              onFileSelected={handleFileSelected}
              uploading={uploading}
              error={uploadError}
            />
          )}

          {step === "configure" && uploadResult && (
            <ConfigCard
              fileId={uploadResult.file_id}
              sheets={uploadResult.sheets}
              onStart={handleStart}
              starting={starting}
            />
          )}

          {step === "processing" &&
            (jobDone ? (
              <DownloadCenter status={status} onReset={handleReset} />
            ) : (
              <ProcessingConsole status={status} connectionError={connectionError} />
            ))}
        </div>
      </main>
    </div>
  );
}
