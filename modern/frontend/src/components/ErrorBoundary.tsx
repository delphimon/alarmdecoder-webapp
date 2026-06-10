import { Component, ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  failed: boolean;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="app-shell">
          <section className="login-panel">
            <h1>AlarmDecoder Modern</h1>
            <p>The interface failed to render. Refresh the page after checking the backend status.</p>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}
