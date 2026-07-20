import { useState } from "react";
import AnalysisForm from "./components/AnalysisForm.jsx";
import MarketFitPanel from "./components/MarketFitPanel.jsx";
import GapAnalysisPanel from "./components/GapAnalysisPanel.jsx";
import { submitAnalysis, pollAnalysisUntilDone, ApiError } from "./api/client.js";

export default function App() {
  const [result, setResult] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  async function handleSubmit({ roleQuery, location, maxJobs, cvFile }) {
    setIsSubmitting(true);
    setSubmitError(null);
    setResult(null);

    try {
      const { job_id } = await submitAnalysis({ roleQuery, location, maxJobs, cvFile });
      const finalResult = await pollAnalysisUntilDone(job_id, {
        onUpdate: (partial) => setResult(partial),
      });
      setResult(finalResult);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Job Market Fit Analyzer</h1>
        <p>Upload your CV, pick a target role, and see how you stack up against live postings.</p>
      </header>

      <AnalysisForm onSubmit={handleSubmit} isSubmitting={isSubmitting} statusMessage={result?.status} />

      {submitError && <p className="form-error top-level-error">{submitError}</p>}

      {result && (
        <main className="dashboard">
          <MarketFitPanel result={result} />
          <GapAnalysisPanel result={result} />
        </main>
      )}
    </div>
  );
}
