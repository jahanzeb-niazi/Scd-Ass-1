/**
 * Typed API client. Every request/response type comes from `schema.d.ts`,
 * which is generated from the backend's OpenAPI document (`npm run gen:api`)
 * and checked in CI (`npm run check:api`), so a backend contract change that
 * the frontend has not absorbed fails the build.
 *
 * All calls use the relative path /api — see ADR 0002. There is no backend URL
 * anywhere in this bundle, and no secrets: anything shipped to a browser is public.
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

type Schemas = components["schemas"];
export type Category = Schemas["Category"];
export type Priority = Schemas["Priority"];
export type Status = Schemas["Status"];
export type TriagedBy = Schemas["TriagedBy"];
export type Complaint = Schemas["ComplaintOut"];
export type ComplaintCreated = Schemas["ComplaintCreated"];
export type ComplaintCreate = Schemas["ComplaintCreate"];
export type ComplaintPage = Schemas["ComplaintPage"];
export type Stats = Schemas["StatsOut"];
export type Providers = Schemas["ProvidersOut"];
export type FieldError = Schemas["FieldErrorOut"];

export type ListQuery = NonNullable<
  paths["/api/complaints"]["get"]["parameters"]["query"]
>;

const client = createClient<paths>({
  // Same-origin in every environment; window.location.origin keeps Request()
  // happy in test environments that need an absolute URL.
  baseUrl: typeof window !== "undefined" ? window.location.origin : "",
  // Resolve fetch lazily so tests can stub it.
  fetch: (request: Request) => globalThis.fetch(request),
});

/** An error the server described. `message` is the server's own `detail`, verbatim. */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: FieldError[];
  readonly retryAfterS: number | null;
  readonly requestId: string | null;

  constructor(
    status: number,
    message: string,
    opts: { fieldErrors?: FieldError[]; retryAfterS?: number | null; requestId?: string | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = opts.fieldErrors ?? [];
    this.retryAfterS = opts.retryAfterS ?? null;
    this.requestId = opts.requestId ?? null;
  }
}

function toApiError(response: Response, error: unknown): ApiError {
  const body = (error ?? {}) as {
    detail?: unknown;
    errors?: FieldError[];
    request_id?: string | null;
  };
  const detail =
    typeof body.detail === "string" && body.detail
      ? body.detail
      : `Request failed (HTTP ${response.status})`;
  const retryAfter = response.headers.get("Retry-After");
  return new ApiError(response.status, detail, {
    fieldErrors: Array.isArray(body.errors) ? body.errors : [],
    retryAfterS: retryAfter !== null && retryAfter !== "" ? Number(retryAfter) : null,
    requestId: body.request_id ?? response.headers.get("X-Request-ID"),
  });
}

async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<{ data: T; response: Response }> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new ApiError(0, "Could not reach the CivicPulse API. Check your connection and try again.");
  }
  const { data, error, response } = result;
  if (!response.ok || data === undefined) throw toApiError(response, error);
  return { data, response };
}

export async function submitComplaint(body: ComplaintCreate): Promise<ComplaintCreated> {
  return (await unwrap(client.POST("/api/complaints", { body }))).data;
}

export async function listComplaints(query: ListQuery): Promise<ComplaintPage> {
  return (await unwrap(client.GET("/api/complaints", { params: { query } }))).data;
}

export async function changeStatus(id: string, status: Status): Promise<Complaint> {
  const call = client.PATCH("/api/complaints/{complaint_id}/status", {
    params: { path: { complaint_id: id } },
    body: { status },
  });
  return (await unwrap(call)).data;
}

export type CacheState = "HIT" | "MISS" | null;

export async function getStats(): Promise<{ stats: Stats; cache: CacheState }> {
  const { data, response } = await unwrap(client.GET("/api/stats"));
  const header = response.headers.get("X-Cache")?.toUpperCase();
  return { stats: data, cache: header === "HIT" || header === "MISS" ? header : null };
}

export async function getProviders(): Promise<Providers> {
  return (await unwrap(client.GET("/api/meta/providers"))).data;
}
