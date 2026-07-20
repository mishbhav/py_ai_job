const IMPORTANCE_STYLES = {
  high: { label: "High priority", className: "badge badge-high" },
  medium: { label: "Medium priority", className: "badge badge-medium" },
  low: { label: "Nice to have", className: "badge badge-low" },
};

export default function GapAnalysisPanel({ result }) {
  const gaps = result?.skill_gaps ?? [];

  return (
    <section className="panel gap-analysis-panel">
      <h2>Skill Gaps &amp; Learning Path</h2>

      {result?.error_message && result?.status === "complete" && (
        <p className="warning-note">{result.error_message}</p>
      )}

      {gaps.length === 0 ? (
        <p className="muted">
          {result?.status === "complete"
            ? "No significant gaps identified — nice work!"
            : "Recommendations will appear here once the AI gap analysis finishes."}
        </p>
      ) : (
        <ul className="gap-checklist">
          {gaps.map((gap) => {
            const badge = IMPORTANCE_STYLES[gap.importance] ?? IMPORTANCE_STYLES.medium;
            return (
              <li key={gap.skill} className="gap-item">
                <div className="gap-item-header">
                  <span className="gap-skill">{gap.skill}</span>
                  <span className={badge.className}>{badge.label}</span>
                </div>
                <p className="gap-reason">{gap.reason}</p>
                {gap.learning_path?.length > 0 && (
                  <ol className="learning-path">
                    {gap.learning_path.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
