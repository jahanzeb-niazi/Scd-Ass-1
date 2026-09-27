import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SubmitPage } from "../src/pages/SubmitPage";
import { created, mockFetch, path, renderAt } from "./helpers";

async function fillValid() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/what is the problem/i), "Burst water main flooding Street 12");
  await user.type(screen.getByLabelText(/where/i), "Street 12, Gulshan");
  return user;
}

describe("SubmitPage", () => {
  it("validates on the client and does not call the API for invalid input", async () => {
    const api = mockFetch([]);
    const user = userEvent.setup();
    renderAt(<SubmitPage />);

    await user.type(screen.getByLabelText(/what is the problem/i), "too short");
    await user.type(screen.getByLabelText(/where/i), "ab");
    await user.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/location must be at least 3/i)).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
  });

  it("shows an honest loading state, then category, priority, AI summary and provider", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const api = mockFetch([
      { method: "POST", match: path("/api/complaints"), status: 201, body: created() },
    ]);
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async (req: Request) => {
      await gate;
      return realFetch(req);
    }) as typeof fetch;

    renderAt(<SubmitPage />);
    const user = await fillValid();
    await user.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(await screen.findByText(/reading and triaging your complaint/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submitting/i })).toBeDisabled();

    release();
    expect(await screen.findByText(/your complaint is logged/i)).toBeInTheDocument();
    expect(screen.getByText("Water")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Burst main flooding Street 12; water entering homes")).toBeInTheDocument();
    expect(screen.getByText("Gemini (hosted LLM)")).toBeInTheDocument();
    expect(screen.getByText("842 ms")).toBeInTheDocument();

    expect(api.calls[0]?.body).toEqual({
      text: "Burst water main flooding Street 12",
      location: "Street 12, Gulshan",
      reporter_contact: null,
    });
    expect(api.calls[0]?.url.pathname).toBe("/api/complaints"); // relative /api, no baked host
  });

  it("tells the citizen when the rule-based fallback was used", async () => {
    mockFetch([
      {
        method: "POST",
        match: path("/api/complaints"),
        status: 201,
        body: created({
          triaged_by: "rules:fallback",
          triage: { confidence: 0.5, cache_hit: false, fallback: true },
        }),
      },
    ]);
    renderAt(<SubmitPage />);
    const user = await fillValid();
    await user.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(await screen.findByText("Keyword rules (fallback)")).toBeInTheDocument();
    expect(screen.getByText(/AI classifier was unavailable/i)).toBeInTheDocument();
  });

  it("surfaces the server's 429 message with its retry time", async () => {
    mockFetch([
      {
        method: "POST",
        match: path("/api/complaints"),
        status: 429,
        headers: { "Retry-After": "42" },
        body: {
          detail: "Too many complaints from this address: limit is 10 per window. Try again in 42 s.",
          retry_after_s: 42,
        },
      },
    ]);
    renderAt(<SubmitPage />);
    const user = await fillValid();
    await user.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 42 s.");
    expect(screen.getByRole("button", { name: /submit complaint/i })).toBeEnabled();
  });

  it("maps server field errors (400) onto the matching inputs", async () => {
    mockFetch([
      {
        method: "POST",
        match: path("/api/complaints"),
        status: 400,
        body: {
          detail: "Validation failed",
          errors: [{ field: "location", message: "Location not recognised", type: "value_error" }],
        },
      },
    ]);
    renderAt(<SubmitPage />);
    const user = await fillValid();
    await user.click(screen.getByRole("button", { name: /submit complaint/i }));

    await waitFor(() => expect(screen.getByText("Location not recognised")).toBeInTheDocument());
    expect(screen.getByLabelText(/where/i)).toHaveAttribute("aria-invalid", "true");
  });
});
