import { Component, StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./styles.css";

/** Keep startup rendering failures visible instead of leaving a blank page. */
class StartupBoundary extends Component {
  /** Initialize the startup error boundary in its healthy state. */
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  /** Switch to the fallback screen when a child component fails to render. */
  static getDerivedStateFromError() {
    return { failed: true };
  }

  /** Render the application or its visible startup-failure fallback. */
  render() {
    if (this.state.failed) {
      return (
        <main className="startup-error">
          <h1>The local interface could not start.</h1>
          <p>Reload once. If this remains visible, the frontend has reported a startup error.</p>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <StartupBoundary><App /></StartupBoundary>
  </StrictMode>,
);
