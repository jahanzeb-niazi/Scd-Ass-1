import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DashboardPage } from "./pages/DashboardPage";
import { StatsPage } from "./pages/StatsPage";
import { SubmitPage } from "./pages/SubmitPage";

export function App() {
  const location = useLocation();
  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="CivicPulse home">
          <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
            <rect width="32" height="32" rx="7" className="brand__tile" />
            <path d="M5 17h6l3-7 4 13 3-6h6" className="brand__pulse" />
          </svg>
          <span>
            CivicPulse
            <small>Municipal complaints</small>
          </span>
        </NavLink>
        <nav className="tabs" aria-label="Main">
          <NavLink to="/" end>
            Report
          </NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/stats">Stats</NavLink>
        </nav>
      </header>
      <main id="main">
        {/* Keyed by path: a crash in one view resets when you navigate away. */}
        <ErrorBoundary key={location.pathname}>
          <Routes>
            <Route path="/" element={<SubmitPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}
