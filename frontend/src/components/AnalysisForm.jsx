import { useState } from "react";

const STATUS_LABELS = {
  pending: "Queued...",
  scraping: "Scraping live job postings...",
  analyzing: "Running keyword & similarity analysis...",
  generating_insights: "Generating AI gap analysis...",
  complete: "Complete",
  failed: "Failed",
};

const MODES = {
  AUTO: "auto",
  MANUAL: "manual",
};

export default function AnalysisForm({ onSubmit, isSubmitting, statusMessage }) {
  const [mode, setMode] = useState(MODES.AUTO);
  const [roleQuery, setRoleQuery] = useState("");
  const [location, setLocation] = useState("");
  const [maxJobs, setMaxJobs] = useState(40);
  const [cvFile, setCvFile] = useState(null);
  const [jdTexts, setJdTexts] = useState(["", ""]);
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

  function handleJdTextChange(index, value) {
    setJdTexts((prev) => prev.map((t, i) => (i === index ? value : t)));
  }

  function addJdField() {
    setJdTexts((prev) => [...prev, ""]);
  }

  function removeJdField(index) {
    setJdTexts((prev) => prev.filter((_, i) => i !== index));
  }

  function switchMode(nextMode) {
    setMode(nextMode);
    setFormError(null);
  }

  function handleSubmit(e) {
    e.preventDefault();

    if (!cvFile) {
      setFormError("A CV in PDF format is required.");
      return;
    }

    if (mode === MODES.MANUAL) {
      const nonEmptyJds = jdTexts.map((t) => t.trim()).filter(Boolean);
      if (nonEmptyJds.length === 0) {
        setFormError("Paste at least one job description.");
        return;
      }
      setFormError(null);
      onSubmit({ mode, roleQuery, cvFile, jdTexts: nonEmptyJds });
      return;
    }

    setFormError(null);
    onSubmit({ mode, roleQuery, location, maxJobs, cvFile });
  }

  return (
    <form className="analysis-form" onSubmit={handleSubmit}>
      <div className="mode-toggle">
        <button
          type="button"
          className={mode === MODES.AUTO ? "mode-btn active" : "mode-btn"}
          onClick={() => switchMode(MODES.AUTO)}
        >
          🔎 Auto-search (Adzuna)
        </button>
        <button
          type="button"
          className={mode === MODES.MANUAL ? "mode-btn active" : "mode-btn"}
          onClick={() => switchMode(MODES.MANUAL)}
        >
          📋 Paste JDs manually
        </button>
      </div>

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

      {mode === MODES.AUTO ? (
        <>
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
        </>
      ) : (
        <div className="field jd-textarea-field">
          <label>Pasted job descriptions</label>
          <p className="field-hint">
            Paste JD text directly — useful if Adzuna rate limits or has no results for your query.
          </p>
          <div className="jd-text-list">
            {jdTexts.map((text, i) => (
              <div className="jd-text-item" key={i}>
                <textarea
                  rows={4}
                  placeholder={`Job description #${i + 1}`}
                  value={text}
                  onChange={(e) => handleJdTextChange(i, e.target.value)}
                />
                {jdTexts.length > 1 && (
                  <button type="button" className="jd-remove-btn" onClick={() => removeJdField(i)}>
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
          <button type="button" className="jd-add-btn" onClick={addJdField}>
            + Add another JD
          </button>
        </div>
      )}

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