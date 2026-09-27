import { config } from "../config";
import type {
  ComplaintCreate,
  ComplaintList,
  ComplaintOut,
  ComplaintStatus,
  ProviderMeta,
  StatsResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API error ${status}`);
  }
}

/** Thrown specifically for 429s so the UI can show Retry-After (§2.1 honest loading/error states). */
export class RateLimitedError extends ApiError {
  constructor(status: number, body: unknown, public retryAfterSeconds: number | null) {
    super(status, body);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${config.apiBaseUrl}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (resp.status === 429) {
    const retryAfter = resp.headers.get("Retry-After");
    const body = await resp.json().catch(() => null);
    throw new RateLimitedError(429, body, retryAfter ? Number(retryAfter) : null);
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new ApiError(resp.status, body);
  }

  // TODO(you): for stats specifically you'll also want the X-Cache header —
  // consider a separate function that returns { data, cacheStatus } instead
  // of reusing this generic `request` for GET /api/stats.
  return resp.json() as Promise<T>;
}

export const api = {
  createComplaint: (payload: ComplaintCreate) =>
    request<ComplaintOut>("/complaints", { method: "POST", body: JSON.stringify(payload) }),

  getComplaint: (id: string) => request<ComplaintOut>(`/complaints/${id}`),

  listComplaints: (params: {
    category?: string;
    priority?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
    );
    return request<ComplaintList>(`/complaints?${qs.toString()}`);
  },

  updateStatus: (id: string, status: ComplaintStatus) =>
    // TODO(you): a 409 here needs special handling in the caller — the spec
    // requires surfacing the server's exact message (§2.1: "must surface the
    // server's 409 message, not a generic 'error'"). ApiError.body should
    // carry that message through; render it verbatim in the Dashboard view.
    request<ComplaintOut>(`/complaints/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  // TODO(you): implement getStats to also surface the X-Cache header value
  // (see note above) — the Stats view must display cache hit/miss (§2.1).
  getStats: () => request<StatsResponse>("/stats"),

  getProviderMeta: () => request<ProviderMeta>("/meta/providers"),
};
