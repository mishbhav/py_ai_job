import { useState } from "react";

const STATUS_LABELS = {
  pending: "Queued...",
  scraping: "Scraping live job postings...",
  analyzing: "Running keyword & similarity analysis...",
  generating_insights: "Generating AI gap analysis...",
  complete: "Complete",
  failed: "Failed",
};

export default function AnalysisForm({ onSubmit, isSubmitting, statusMessage }) {
  const [roleQuery, setRoleQuery] = useState("");
  const [location, setLocation] = useState("");
  const [maxJobs, setMaxJobs] = useState(40);
  const [cvFile, setCvFile] = useState(null);
  const [formError, setFormError] = useState(null);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (file && file.type !== "application/pdf") {
      setFormError("Please upload a PDF file.");
      setCvFile(null);
      return;
    }
    setFormError(null);
    setCvFile(file ?? null);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!cvFile) {
      setFormError("A CV in PDF format is required.");
      return;
    }
    setFormError(null);
    onSubmit({ roleQuery, location, maxJobs, cvFile });
  }

  return (
    <form className="analysis-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="roleQuery">Target role</label>
        <input
          id="roleQuery"
          type="text"
          placeholder="e.g. Senior Data Scientist"
          value={roleQuery}
          onChange={(e) => setRoleQuery(e.target.value)}
          required
          minLength={2}
        />
      </div>

      <div className="field">
        <label htmlFor="location">Location (optional)</label>
        <input
          id="location"
          type="text"
          placeholder="e.g. Bengaluru"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="maxJobs">Jobs to analyze: {maxJobs}</label>
        <input
          id="maxJobs"
          type="range"
          min={10}
          max={50}
          value={maxJobs}
          onChange={(e) => setMaxJobs(Number(e.target.value))}
        />
      </div>

      <div className="field">
        <label htmlFor="cvFile">CV (PDF)</label>
        <input id="cvFile" type="file" accept="application/pdf" onChange={handleFileChange} required />
      </div>

      {formError && <p className="form-error">{formError}</p>}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? statusMessage ? STATUS_LABELS[statusMessage] ?? "Working..." : "Working..." : "Analyze Fit"}
      </button>
    </form>
  );
}

export { STATUS_LABELS };
