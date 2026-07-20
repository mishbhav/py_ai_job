/**
 * Centralized API client. Components never call fetch() directly —
 * everything talks to the backend through here, so the base-URL logic
 * (which differs between local dev and Codespaces) lives in one place.
 */

function resolveApiBaseUrl() {
  // Explicit override always wins (set in frontend/.env as VITE_API_BASE_URL).
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  const { hostname, protocol } = window.location;

  // Codespaces forwarded URLs look like:
  //   https://<name>-5173.app.github.dev
  // The backend on port 8000 is forwarded at:
  //   https://<name>-8000.app.github.dev
  if (hostname.endsWith(".app.github.dev")) {
    const backendHost = hostname.replace(/-\d+\.app\.github\.dev$/, "-8000.app.github.dev");
    return `${protocol}//${backendHost}`;
  }

  return "http://localhost:8000";
}

export const API_BASE_URL = resolveApiBaseUrl();

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function parseErrorResponse(response) {
  try {
    const body = await response.json();
    return body.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function submitAnalysis({ roleQuery, location, maxJobs, cvFile }) {
  const formData = new FormData();
  formData.append("role_query", roleQuery);
  if (location) formData.append("location", location);
  formData.append("max_jobs", String(maxJobs));
  formData.append("cv_file", cvFile);

  const response = await fetch(`${API_BASE_URL}/api/analysis`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorResponse(response), response.status);
  }
  return response.json(); // { job_id, status }
}

export async function fetchAnalysisResult(jobId) {
  const response = await fetch(`${API_BASE_URL}/api/analysis/${jobId}`);
  if (!response.ok) {
    throw new ApiError(await parseErrorResponse(response), response.status);
  }
  return response.json();
}

/**
 * Polls GET /api/analysis/{jobId} until status is COMPLETE or FAILED.
 * Returns the final result. Calls onUpdate with every intermediate
 * status so the UI can show progress (scraping -> analyzing -> ...).
 */
export async function pollAnalysisUntilDone(jobId, { onUpdate, intervalMs = 2500, timeoutMs = 180_000 } = {}) {
  const startedAt = Date.now();

  while (true) {
    const result = await fetchAnalysisResult(jobId);
    onUpdate?.(result);

    if (result.status === "complete" || result.status === "failed") {
      return result;
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new ApiError("Analysis timed out client-side after 3 minutes.", 408);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export { ApiError };
