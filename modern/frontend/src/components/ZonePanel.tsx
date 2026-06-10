import { useEffect, useState } from "react";
import type { AuthStatus, PanelState, ZoneInfo } from "../types";

type ZonePanelProps = {
  state: PanelState;
  auth: AuthStatus | null;
  loadZones: () => Promise<ZoneInfo[]>;
  saveZones: (zones: ZoneInfo[]) => Promise<ZoneInfo[]>;
};

export function ZonePanel({ state, auth, loadZones, saveZones }: ZonePanelProps) {
  const [zones, setZones] = useState<ZoneInfo[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const isAdmin = auth?.user?.role === "admin";

  useEffect(() => {
    void loadZones().then(setZones).catch(() => setZones([]));
  }, [loadZones]);

  const visibleZones = zones.length ? zones : state.faulted_zones.map((zone) => ({ id: zone, name: "", enabled: true }));

  const save = async () => {
    const next = await saveZones(visibleZones);
    setZones(next);
    setMessage("Zones saved.");
  };

  return (
    <section className="summary-panel" aria-label="Zones">
      <div className="section-heading">
        <h2>Zones</h2>
        <span>{state.faulted_zones.length} faulted</span>
      </div>
      {message ? <p className="read-only-note">{message}</p> : null}
      <div className="zone-grid">
        {visibleZones.length === 0 ? (
          <p className="empty-text">No zones reported yet.</p>
        ) : (
          visibleZones.map((zone) => (
            <article key={zone.id}>
              <strong>Zone {zone.id}</strong>
              {isAdmin ? (
                <input
                  value={zone.name}
                  placeholder="Zone name"
                  onChange={(event) => setZones((current) => updateZone(current, zone.id, { name: event.target.value }))}
                />
              ) : (
                <span>{zone.name || (state.faulted_zones.includes(zone.id) ? "Faulted" : "Ready")}</span>
              )}
            </article>
          ))
        )}
      </div>
      {isAdmin ? <button className="save-button" type="button" onClick={save}>Save zones</button> : null}
    </section>
  );
}

function updateZone(zones: ZoneInfo[], id: number, patch: Partial<ZoneInfo>) {
  const existing = zones.find((zone) => zone.id === id);
  if (!existing) {
    return [...zones, { id, name: "", enabled: true, ...patch }];
  }
  return zones.map((zone) => zone.id === id ? { ...zone, ...patch } : zone);
}
