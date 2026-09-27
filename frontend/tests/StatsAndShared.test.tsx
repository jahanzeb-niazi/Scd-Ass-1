import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../src/components/ErrorBoundary";
import { StatsPage } from "../src/pages/StatsPage";
import { validateComplaint } from "../src/validation";
import { mockFetch, path, providers, renderAt, stats } from "./helpers";

describe("StatsPage", () => {
  it("renders aggregates and the X-Cache state reported by the server", async () => {
    mockFetch([
      { match: path("/api/stats"), body: stats(), headers: { "X-Cache": "HIT" } },
      { match: path("/api/meta/providers"), body: providers() },
    ]);
    renderAt(<StatsPage />, "/stats");

    expect(await screen.findByText("35")).toBeInTheDocument();
    expect(screen.getByTestId("cache-indicator")).toHaveTextContent("HIT");
    expect(screen.getByTestId("cache-indicator")).toHaveTextContent(/served from the redis cache/i);
    expect(screen.getByRole("region", { name: "By category" })).toHaveTextContent("Water7");
    expect(screen.getByText("25.0%")).toBeInTheDocument(); // triage cache hit rate
    expect(screen.getByText("ProviderTimeoutError")).toBeInTheDocument();
  });

  it("shows MISS after a refresh when the server recomputed", async () => {
    mockFetch([
      { match: path("/api/stats"), body: stats(), headers: { "X-Cache": "HIT" } },
      { match: path("/api/meta/providers"), body: providers() },
      { match: path("/api/stats"), body: stats(), headers: { "X-Cache": "MISS" } },
      { match: path("/api/meta/providers"), body: providers() },
    ]);
    const user = userEvent.setup();
    renderAt(<StatsPage />, "/stats");
    await screen.findByText("HIT");

    await user.click(screen.getByRole("button", { name: /refresh/i }));

    expect(await screen.findByText("MISS")).toBeInTheDocument();
  });
});

describe("ErrorBoundary", () => {
  it("replaces a crashed view with a recoverable message", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    // React dev mode re-dispatches caught render errors to window; keep CI output clean.
    const swallow = (e: ErrorEvent) => e.preventDefault();
    window.addEventListener("error", swallow);
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("render exploded");
      return <p>recovered</p>;
    }
    const user = userEvent.setup();
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("render exploded");
    shouldThrow = false;
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(screen.getByText("recovered")).toBeInTheDocument();
    window.removeEventListener("error", swallow);
  });
});

describe("validateComplaint", () => {
  it("mirrors the server's length rules after trimming", () => {
    expect(validateComplaint({ text: "   123456789   ", location: "abc", reporter_contact: "" })).toHaveProperty(
      "text",
    );
    expect(
      validateComplaint({ text: "x".repeat(10), location: "abc", reporter_contact: "y".repeat(201) }),
    ).toEqual({ reporter_contact: expect.any(String) });
    expect(
      validateComplaint({ text: "x".repeat(2000), location: "a".repeat(200), reporter_contact: "" }),
    ).toEqual({});
    expect(validateComplaint({ text: "x".repeat(2001), location: "abc", reporter_contact: "" })).toHaveProperty(
      "text",
    );
  });
});
