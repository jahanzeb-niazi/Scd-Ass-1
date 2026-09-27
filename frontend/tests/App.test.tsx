import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { App } from "../src/App";

describe("App", () => {
  it("renders the navigation", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );
    expect(screen.getByText("Submit")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Stats")).toBeInTheDocument();
  });
});

// TODO(you): the spec requires >=5 meaningful component tests (§2.1, rubric B).
// This one only proves navigation renders. Add real ones, e.g.:
//   - SubmitPage: shows validation hint / disables button while submitting
//   - DashboardPage: renders a 409 error message verbatim when update fails
//   - StatsPage: displays "HIT" vs "MISS" based on mocked header
//   - ErrorBoundary: renders fallback UI when a child throws
// Mock api/client.ts calls with vitest's vi.mock() rather than hitting a real backend.
