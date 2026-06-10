import type { EffectiveConfig, PanelEvent, PanelState, RawAlarmMessage } from "../types";

type DiagnosticsPanelProps = {
  state: PanelState;
  events: PanelEvent[];
  rawMessages: RawAlarmMessage[];
  config: EffectiveConfig | null;
  socketStatus: "connecting" | "open" | "closed";
};

export function DiagnosticsPanel({ state, events, rawMessages, config, socketStatus }: DiagnosticsPanelProps) {
  const parsedEvents = events.filter((event) => event.type !== "raw_message");

  return (
    <section className="diagnostics-panel" aria-label="Diagnostics">
      <div className="section-heading">
        <h2>Diagnostics</h2>
        <span>{config?.read_only ? "Read-only" : "Commands enabled"}</span>
      </div>

      <dl className="diagnostic-grid">
        <div>
          <dt>Connection</dt>
          <dd>{state.connection_status}</dd>
        </div>
        <div>
          <dt>WebSocket</dt>
          <dd>{socketStatus}</dd>
        </div>
        <div>
          <dt>Adapter</dt>
          <dd>{config?.adapter ?? "unknown"}</dd>
        </div>
        <div>
          <dt>Mode</dt>
          <dd>{config?.read_only ? "Read-only" : "Read/write"}</dd>
        </div>
      </dl>

      <div className="diagnostic-section">
        <h3>Parsed Events</h3>
        <div className="compact-event-list">
          {parsedEvents.slice(0, 8).map((event) => (
            <article key={event.id}>
              <time>{formatTime(event.timestamp)}</time>
              <strong>{event.type.replaceAll("_", " ")}</strong>
              <span>{event.message}</span>
            </article>
          ))}
        </div>
      </div>

      <div className="diagnostic-section">
        <h3>Raw Messages</h3>
        <div className="raw-message-list">
          {rawMessages.slice(0, 8).map((message) => (
            <article key={message.id}>
              <time>{formatTime(message.timestamp)}</time>
              <code>{message.raw}</code>
            </article>
          ))}
        </div>
      </div>

      <details className="state-json">
        <summary>Current State JSON</summary>
        <pre>{JSON.stringify(state, null, 2)}</pre>
      </details>
    </section>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
