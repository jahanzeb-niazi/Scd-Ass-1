import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  hasError: boolean;
}

/** Required per §2.1 "Required engineering: An error boundary." */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // TODO(you): decide whether/how to report this (console.error is the
    // floor; consider posting to a backend endpoint if you want it visible
    // in your observability surface, though that's beyond the spec's minimum).
    console.error("Uncaught frontend error", error, info);
  }

  render() {
    if (this.state.hasError) {
      // TODO(you): style this properly — this is a functional placeholder.
      return <div role="alert">Something went wrong. Please refresh the page.</div>;
    }
    return this.props.children;
  }
}
