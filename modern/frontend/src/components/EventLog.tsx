import type { PanelEvent } from "../types";

type EventLogProps = {
  events: PanelEvent[];
  embedded?: boolean;
};

export function EventLog({ events, embedded = false }: EventLogProps) {
  const content = (
    <>
      <div className="section-heading">
        <h2>Event Log</h2>
        <span>{events.length} in memory</span>
      </div>
      <div className="event-list">
        {events.map((event) => (
          <article className="event-row" key={event.id}>
            <time>{formatTime(event.timestamp)}</time>
            <div>
              <strong>{event.type.replaceAll("_", " ")}</strong>
              <p>{event.message}</p>
            </div>
          </article>
        ))}
      </div>
    </>
  );
  if (embedded) {
    return content;
  }
  return (
    <section className="event-panel" aria-label="Event log">
      {content}
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
