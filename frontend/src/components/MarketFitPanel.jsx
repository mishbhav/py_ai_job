import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function ScoreRing({ score }) {
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="score-ring" style={{ "--score-color": color }}>
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="52" className="score-ring-bg" />
        <circle
          cx="60"
          cy="60"
          r="52"
          className="score-ring-fg"
          style={{
            stroke: color,
            strokeDasharray: `${(score / 100) * 326.7} 326.7`,
          }}
        />
      </svg>
      <div className="score-ring-label">
        <span className="score-value">{score}%</span>
        <span className="score-caption">Match</span>
      </div>
    </div>
  );
}

export default function MarketFitPanel({ result }) {
  const chartData = (result?.top_keywords ?? []).map((k) => ({
    name: k.keyword,
    count: k.count,
    percentage: k.percentage_of_jds,
  }));

  return (
    <section className="panel market-fit-panel">
      <h2>Market Fit</h2>

      {result?.match_score != null ? (
        <ScoreRing score={result.match_score} />
      ) : (
        <p className="muted">Match score will appear here once analysis completes.</p>
      )}

      <p className="jobs-scraped-note">
        Based on {result?.jobs_scraped ?? 0} live postings for "{result?.role_query}"
      </p>

      <h3>Top Market Keywords</h3>
      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 24 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={110} />
            <Tooltip
              formatter={(value, name, props) => [`${value} mentions (${props.payload.percentage}% of JDs)`, "Frequency"]}
            />
            <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="muted">No keyword data yet.</p>
      )}

      {result?.job_clusters?.length > 0 && (
        <>
          <h3>Job Sub-Domain Clusters</h3>
          <ul className="cluster-list">
            {result.job_clusters.map((cluster) => (
              <li key={cluster.cluster_label}>
                <strong>{cluster.cluster_label}</strong> — {cluster.job_count} postings
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
