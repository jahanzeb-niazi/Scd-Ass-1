import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Optional custom fallback, mostly for tests. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors below it so one broken view shows a recoverable
 * message instead of a blank page. (Async errors from fetch are handled in the
 * views themselves; boundaries only see errors thrown while rendering.)
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Browser console only: no third-party error service, so no data leaves the page.
    console.error("CivicPulse view crashed", error, info.componentStack);
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div className="panel panel--error" role="alert">
        <h2>Something went wrong on this page</h2>
        <p className="muted">
          The rest of CivicPulse still works. You can try this view again, or reload the page.
        </p>
        <pre className="error-detail">{error.message}</pre>
        <div className="row">
          <button type="button" className="btn" onClick={this.reset}>
            Try again
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => window.location.reload()}>
            Reload page
          </button>
        </div>
      </div>
    );
  }
}
