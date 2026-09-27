/**
 * Test helpers: a scripted fake `fetch` and fixture builders typed against the
 * generated API schema, so a contract change breaks the fixtures at compile time.
 */
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { Complaint, ComplaintCreated, Providers, Stats } from "../src/api/client";

export interface Route {
  method?: string;
  match: (url: URL) => boolean;
  status?: number;
  body: unknown;
  headers?: Record<string, string>;
}

export interface FetchMock {
  calls: { method: string; url: URL; body: unknown }[];
}

/** Stub global fetch with an ordered list of routes; first match wins and is consumed. */
export function mockFetch(routes: Route[]): FetchMock {
  const remaining = [...routes];
  const state: FetchMock = { calls: [] };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request) => {
      const url = new URL(input.url);
      const method = input.method.toUpperCase();
      const text = await input.text();
      state.calls.push({ method, url, body: text ? JSON.parse(text) : undefined });
      const idx = remaining.findIndex((r) => (r.method ?? "GET") === method && r.match(url));
      if (idx === -1) throw new Error(`Unmocked request: ${method} ${url.pathname}${url.search}`);
      const [route] = remaining.splice(idx, 1);
      return new Response(JSON.stringify(route!.body), {
        status: route!.status ?? 200,
        headers: { "Content-Type": "application/json", ...(route!.headers ?? {}) },
      });
    }),
  );
  return state;
}

export const path = (p: string) => (url: URL) => url.pathname === p;

export function renderAt(ui: ReactElement, route = "/") {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>);
}

export function complaint(overrides: Partial<Complaint> = {}): Complaint {
  return {
    id: "6b1f1c1e-1111-4222-8333-444455556666",
    text: "Burst water main flooding Street 12 since fajr, water entering ground floors",
    location: "Street 12, Gulshan-e-Iqbal",
    reporter_contact: null,
    category: "water",
    priority: "high",
    status: "open",
    ai_summary: "Burst main flooding Street 12; water entering homes",
    triaged_by: "llm:gemini",
    triage_latency_ms: 842,
    created_at: "2026-09-27T07:00:00Z",
    updated_at: "2026-09-27T07:00:00Z",
    allowed_transitions: ["in_progress", "rejected"],
    ...overrides,
  };
}

export function created(overrides: Partial<ComplaintCreated> = {}): ComplaintCreated {
  return {
    ...complaint(),
    triage: { confidence: 0.93, cache_hit: false, fallback: false },
    ...overrides,
  };
}

export function stats(): Stats {
  return {
    total: 35,
    by_category: { water: 7, electricity: 6, sanitation: 7, roads: 6, streetlights: 5, other: 4 },
    by_priority: { high: 15, normal: 13, low: 7 },
    by_status: { open: 17, in_progress: 8, resolved: 6, rejected: 4 },
  };
}

export function providers(): Providers {
  return {
    active: "llm:gemini",
    configured: "llm",
    fallback: "rules:fallback",
    model: "gemini-2.5-flash-lite",
    timeout_s: 10,
    cache: { hits: 3, misses: 9, hit_rate: 0.25 },
    recent: [
      {
        complaint_id: "c1",
        provider: "rules:fallback",
        latency_ms: 10012,
        fallback: true,
        cache_hit: false,
        error: "ProviderTimeoutError",
        at: "2026-09-27T07:00:00+00:00",
      },
    ],
  };
}
