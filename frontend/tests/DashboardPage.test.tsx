import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import { complaint, mockFetch, path, renderAt } from "./helpers";

const listPath = path("/api/complaints");

describe("DashboardPage", () => {
  it("renders the page, total and pagination from the server response", async () => {
    mockFetch([
      {
        match: listPath,
        body: { items: [complaint()], total: 45, page: 1, page_size: 20 },
      },
    ]);
    renderAt(<DashboardPage />, "/dashboard");

    expect(await screen.findByText(/45 complaints · page 1 of 3/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("sends filters as query parameters and resets to page 1", async () => {
    const api = mockFetch([
      { match: listPath, body: { items: [complaint()], total: 1, page: 1, page_size: 20 } },
      { match: listPath, body: { items: [], total: 0, page: 1, page_size: 20 } },
    ]);
    const user = userEvent.setup();
    renderAt(<DashboardPage />, "/dashboard?page=2");
    await screen.findByText(/1 complaint/);

    await user.selectOptions(screen.getByLabelText("Priority"), "high");

    expect(await screen.findByText(/no complaints match/i)).toBeInTheDocument();
    const last = api.calls.at(-1)!.url.searchParams;
    expect(last.get("priority")).toBe("high");
    expect(last.get("page")).toBe("1");
  });

  it("offers transition buttons only from the server's allowed_transitions", async () => {
    mockFetch([
      {
        match: listPath,
        body: {
          items: [complaint({ status: "in_progress", allowed_transitions: ["resolved", "rejected"] })],
          total: 1,
          page: 1,
          page_size: 20,
        },
      },
    ]);
    renderAt(<DashboardPage />, "/dashboard");
    const row = (await screen.findAllByRole("listitem"))[0]!;

    expect(within(row).getByRole("button", { name: "Mark resolved" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "Start work" })).not.toBeInTheDocument();
  });

  it("applies a valid transition and updates the row in place", async () => {
    const api = mockFetch([
      { match: listPath, body: { items: [complaint()], total: 1, page: 1, page_size: 20 } },
      {
        method: "PATCH",
        match: (u) => u.pathname.endsWith("/status"),
        body: complaint({ status: "in_progress", allowed_transitions: ["resolved", "rejected"] }),
      },
    ]);
    const user = userEvent.setup();
    renderAt(<DashboardPage />, "/dashboard");

    await user.click(await screen.findByRole("button", { name: "Start work" }));

    expect(await screen.findByRole("button", { name: "Mark resolved" })).toBeInTheDocument();
    expect(api.calls.at(-1)!.body).toEqual({ status: "in_progress" });
  });

  it("surfaces the server's 409 message verbatim, not a generic error", async () => {
    const serverMessage =
      "Invalid status transition: resolved → in_progress ('resolved' is a terminal status)";
    mockFetch([
      {
        match: listPath,
        body: {
          items: [complaint({ status: "resolved", allowed_transitions: [] })],
          total: 1,
          page: 1,
          page_size: 20,
        },
      },
      {
        method: "PATCH",
        match: (u) => u.pathname.endsWith("/status"),
        status: 409,
        body: { detail: serverMessage, current: "resolved", attempted: "in_progress", allowed: [] },
      },
    ]);
    const user = userEvent.setup();
    renderAt(<DashboardPage />, "/dashboard");

    await user.selectOptions(await screen.findByLabelText(/set status manually/i), "in_progress");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(serverMessage);
    expect(screen.queryByText(/^error$/i)).not.toBeInTheDocument();
  });
});
