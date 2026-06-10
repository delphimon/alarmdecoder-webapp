import { useEffect, useState } from "react";
import type { PanelEvent, RawAlarmMessage } from "../types";
import { EventLog } from "./EventLog";

type HistoryPanelProps = {
  loadEvents: (offset?: number) => Promise<PanelEvent[]>;
  loadRawMessages: (offset?: number) => Promise<RawAlarmMessage[]>;
};

export function HistoryPanel({ loadEvents, loadRawMessages }: HistoryPanelProps) {
  const [events, setEvents] = useState<PanelEvent[]>([]);
  const [rawMessages, setRawMessages] = useState<RawAlarmMessage[]>([]);
  const [tab, setTab] = useState<"events" | "raw">("events");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([loadEvents(), loadRawMessages()])
      .then(([nextEvents, nextRaw]) => {
        setEvents(nextEvents);
        setRawMessages(nextRaw);
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "History failed."));
  }, [loadEvents, loadRawMessages]);

  return (
    <section className="event-panel" aria-label="History">
      <div className="section-heading">
        <h2>History</h2>
        <span>{tab === "events" ? `${events.length} events` : `${rawMessages.length} raw`}</span>
      </div>
      <div className="sub-tabs">
        <button className={tab === "events" ? "active" : ""} type="button" onClick={() => setTab("events")}>Events</button>
        <button className={tab === "raw" ? "active" : ""} type="button" onClick={() => setTab("raw")}>Raw</button>
      </div>
      {error ? <p className="command-error">{error}</p> : null}
      {tab === "events" ? (
        <EventLog events={events} embedded />
      ) : (
        <div className="raw-message-list">
          {rawMessages.map((message) => (
            <article key={message.id}>
              <time>{formatTime(message.timestamp)}</time>
              <code>{message.raw}</code>
            </article>
          ))}
        </div>
      )}
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
