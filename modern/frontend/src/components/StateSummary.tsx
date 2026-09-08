import type { EffectiveConfig, PanelState } from "../types";
import { StatusPill } from "./StatusPill";

type StateSummaryProps = {
  state: PanelState;
  config: EffectiveConfig | null;
  socketStatus: "connecting" | "open" | "closed";
};

export function StateSummary({ state, config, socketStatus }: StateSummaryProps) {
  return (
    <section className="summary-panel" aria-label="Panel state">
      <div className="section-heading">
        <h2>Panel State</h2>
        <span className={`connection ${state.connection_status}`}>{state.connection_status}</span>
      </div>

      <div className="status-grid" role="region" aria-label="System status indicators">

        <StatusPill label="Connected" active={state.connected} tone="green" />
        <StatusPill label="Ready" active={state.ready} tone="green" />
        <StatusPill label="Armed" active={state.armed} tone="red" />
        <StatusPill label="Stay" active={state.armed_stay} tone="amber" />
        <StatusPill label="Alarm" active={state.alarming} tone="red" />
        <StatusPill label="Fire" active={state.fire_detected} tone="red" />
        <StatusPill label="Panic" active={state.panic} tone="red" />
        <StatusPill label="Trouble" active={state.trouble} tone="amber" />
        <StatusPill label="Battery" active={state.battery_trouble || state.power === "BATTERY"} tone="amber" />
      </div>

      <dl className="state-list">
        <div>
          <dt>Adapter</dt>
          <dd>{config?.adapter ?? "unknown"}</dd>
        </div>
        <div>
          <dt>Mode</dt>
          <dd>
            {config?.read_only
              ? "Read-only"
              : config?.adapter === "fake"
                ? "Simulator"
                : config?.allow_commands
                  ? "Commands enabled"
                  : "Read-only"}
          </dd>
        </div>
        <div>
          <dt>WebSocket</dt>
          <dd>{socketStatus}</dd>
        </div>
        <div>
          <dt>Panel</dt>
          <dd>{state.panel_type}</dd>
        </div>
        <div>
          <dt>Armed mode</dt>
          <dd>{state.armed_mode}</dd>
        </div>
        <div>
          <dt>Power</dt>
          <dd>{state.power}</dd>
        </div>
        <div>
          <dt>Trouble</dt>
          <dd>{state.trouble_text ?? "None"}</dd>
        </div>
        <div>
          <dt>Faulted zones</dt>
          <dd>{(!state.ready && state.faulted_zones.length) ? state.faulted_zones.join(", ") : "None"}</dd>
        </div>
        <div>
          <dt>Relays</dt>
          <dd>{Object.keys(state.relay_status).length ? JSON.stringify(state.relay_status) : "None"}</dd>
        </div>
        <div>
          <dt>Last command</dt>
          <dd>{state.last_command ?? "None"}</dd>
        </div>
      </dl>
    </section>
  );
}
