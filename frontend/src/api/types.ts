/**
 * Types mirroring backend/app/schemas/complaint.py and triage.py.
 *
 * TODO(you): the spec requires "a typed API client generated from or checked
 * against the backend's OpenAPI schema" (§2.1). Hand-writing these types is
 * fine to start, but before submission either:
 *   (a) generate them from http://localhost:8000/openapi.json with a tool
 *       like openapi-typescript, or
 *   (b) add a CI/pre-commit check that diffs these against the live schema
 * so "checked against" is actually true, not just aspirational.
 */

export type Category =
  | "water" | "electricity" | "sanitation" | "roads" | "streetlights" | "other";

export type Priority = "high" | "normal" | "low";

export type ComplaintStatus = "open" | "in_progress" | "resolved" | "rejected";

export interface ComplaintOut {
  id: string;
  text: string;
  location: string;
  reporter_contact: string | null;
  category: Category;
  priority: Priority;
  status: ComplaintStatus;
  ai_summary: string | null;
  triaged_by: string;
  triage_latency_ms: number;
  created_at: string;
  updated_at: string;
}

export interface ComplaintCreate {
  text: string;
  location: string;
  reporter_contact?: string | null;
}

export interface ComplaintList {
  items: ComplaintOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface FieldError {
  field: string;
  message: string;
}

export interface StatsResponse {
  // TODO(you): match this shape exactly to whatever your backend's
  // ComplaintRepository.get_stats() / GET /api/stats actually returns.
  by_category: Record<Category, number>;
  by_priority: Record<Priority, number>;
}

export interface ProviderMeta {
  active_provider: string;
  recent_outcomes: Array<{
    provider: string;
    latency_ms: number;
    fallback: boolean;
  }>;
}
