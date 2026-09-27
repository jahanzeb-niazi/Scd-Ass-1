import { Link, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { SubmitPage } from "./pages/SubmitPage";
import { DashboardPage } from "./pages/DashboardPage";
import { StatsPage } from "./pages/StatsPage";

export function App() {
  return (
    <ErrorBoundary>
      {/* TODO(you): style this nav properly; it's a functional placeholder */}
      <nav>
        <Link to="/">Submit</Link>
        {" | "}
        <Link to="/dashboard">Dashboard</Link>
        {" | "}
        <Link to="/stats">Stats</Link>
      </nav>

      <Routes>
        <Route path="/" element={<SubmitPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/stats" element={<StatsPage />} />
      </Routes>
    </ErrorBoundary>
  );
}
