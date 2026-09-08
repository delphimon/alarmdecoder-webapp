import { useEffect, useState } from "react";
import type { AuthStatus, PanelState, ZoneInfo } from "../types";
import { ConfirmDialog, Modal } from "./Dialog";

type ZonePanelProps = {
  state: PanelState;
  auth: AuthStatus | null;
  loadZones: () => Promise<ZoneInfo[]>;
  saveZones: (zones: ZoneInfo[]) => Promise<ZoneInfo[]>;
  deleteZone?: (zoneId: number) => Promise<{ deleted: boolean }>;
};

const STANDARD_ZONES: ZoneInfo[] = [
  { id: 1, name: "Front Entry Door", enabled: true },
  { id: 2, name: "Back Patio Door", enabled: true },
  { id: 3, name: "Garage Overhead / Entry", enabled: true },
  { id: 4, name: "Living Room Motion", enabled: true },
  { id: 5, name: "Kitchen Windows", enabled: true },
  { id: 6, name: "Master Bedroom", enabled: true },
  { id: 7, name: "Smoke / Heat Detector", enabled: true },
  { id: 8, name: "Carbon Monoxide", enabled: true },
];

export function ZonePanel({ state, auth, loadZones, saveZones, deleteZone }: ZonePanelProps) {
  const [zones, setZones] = useState<ZoneInfo[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState<"all" | "faulted" | "normal">("all");

  // Add Zone modal state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newZoneId, setNewZoneId] = useState("");
  const [newZoneName, setNewZoneName] = useState("");
  const [newZoneEnabled, setNewZoneEnabled] = useState(true);

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<ZoneInfo | null>(null);

  const isAdmin = auth?.user?.role === "admin";

  useEffect(() => {
    void loadZones().then(setZones).catch(() => setZones([]));
  }, [loadZones]);

  // Combine loaded zones with any newly faulted zones that aren't in the list yet
  const allZonesMap = new Map<number, ZoneInfo>();
  for (const z of zones) {
    allZonesMap.set(z.id, z);
  }
  for (const fz of state.faulted_zones) {
    if (!allZonesMap.has(fz)) {
      allZonesMap.set(fz, { id: fz, name: "", enabled: true });
    }
  }
  const visibleZones = Array.from(allZonesMap.values()).sort((a, b) => a.id - b.id);

  const isZoneFaulted = (id: number) => !state.ready && state.faulted_zones.includes(id);

  const faultedCount = visibleZones.filter((z) => isZoneFaulted(z.id)).length;
  const normalCount = visibleZones.length - faultedCount;

  const filteredZones = visibleZones.filter((z) => {
    const isFaulted = isZoneFaulted(z.id);
    if (filter === "faulted") return isFaulted;
    if (filter === "normal") return !isFaulted;
    return true;
  });

  const handleQuickSetup = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const next = await saveZones(STANDARD_ZONES);
      setZones(next);
      setMessage("Configured standard zones 1 through 8.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to configure zones.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddZone = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const id = parseInt(newZoneId, 10);
    if (isNaN(id) || id <= 0) {
      setError("Zone number must be a positive integer.");
      return;
    }
    if (visibleZones.some((z) => z.id === id)) {
      setError(`Zone ${id} already exists.`);
      return;
    }
    const newZone: ZoneInfo = {
      id,
      name: newZoneName.trim() || `Zone ${id}`,
      enabled: newZoneEnabled,
    };
    const updated = [...visibleZones, newZone].sort((a, b) => a.id - b.id);
    setSaving(true);
    try {
      const next = await saveZones(updated);
      setZones(next);
      setIsAddOpen(false);
      setNewZoneId("");
      setNewZoneName("");
      setNewZoneEnabled(true);
      setMessage(`Zone ${id} added successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add zone.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteZone = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    setError(null);
    try {
      if (deleteZone) {
        await deleteZone(deleteTarget.id);
      }
      const remaining = visibleZones.filter((z) => z.id !== deleteTarget.id);
      const next = await saveZones(remaining);
      setZones(next);
      setMessage(`Zone ${deleteTarget.id} deleted successfully.`);
      setDeleteTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete zone.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const next = await saveZones(visibleZones);
      setZones(next);
      setMessage("Zone configurations saved successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save zones.");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateZone = (id: number, patch: Partial<ZoneInfo>) => {
    setZones((current) => updateZone(current, id, patch));
  };

  return (
    <section className="summary-panel" aria-label="Zones">
      <div className="section-heading" style={{ flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2>Zones ({visibleZones.length})</h2>
          <span style={{ color: faultedCount > 0 ? "var(--color-danger-text)" : "var(--color-success-text)", fontWeight: 700 }}>
            {faultedCount > 0 ? `⚠️ ${faultedCount} Faulted` : "✓ All Normal"}
          </span>
        </div>

        {isAdmin ? (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {visibleZones.length === 0 ? (
              <button type="button" className="btn-secondary" onClick={handleQuickSetup} disabled={saving}>
                Quick Setup (Zones 1–8)
              </button>
            ) : null}
            <button type="button" className="btn-secondary" onClick={() => { setError(null); setIsAddOpen(true); }}>
              + Add Zone
            </button>
            {visibleZones.length > 0 ? (
              <button type="button" className="btn-primary" onClick={handleSaveAll} disabled={saving}>
                {saving ? "Saving..." : "Save Zones"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {message ? <p className="status-message" role="status" style={{ color: "var(--color-success-text)" }}>{message}</p> : null}
      {error ? <p className="status-message" role="alert" style={{ color: "var(--color-danger-text)" }}>{error}</p> : null}

      {visibleZones.length > 0 ? (
        <div style={{ display: "flex", gap: 8, margin: "12px 0" }}>
          <button
            type="button"
            className={filter === "all" ? "btn-primary" : "btn-secondary"}
            style={{ padding: "4px 12px", fontSize: 13 }}
            onClick={() => setFilter("all")}
          >
            All Zones ({visibleZones.length})
          </button>
          <button
            type="button"
            className={filter === "faulted" ? "btn-primary" : "btn-secondary"}
            style={{ padding: "4px 12px", fontSize: 13 }}
            onClick={() => setFilter("faulted")}
          >
            Faulted ({faultedCount})
          </button>
          <button
            type="button"
            className={filter === "normal" ? "btn-primary" : "btn-secondary"}
            style={{ padding: "4px 12px", fontSize: 13 }}
            onClick={() => setFilter("normal")}
          >
            Normal ({normalCount})
          </button>
        </div>
      ) : null}

      {visibleZones.length === 0 ? (
        <div style={{ padding: "32px 16px", textAlign: "center", border: "1px dashed var(--color-border-subtle)", borderRadius: 8 }}>
          <p className="empty-text" style={{ fontSize: 15, marginBottom: 16 }}>No zones configured yet.</p>
          {isAdmin ? (
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button type="button" className="btn-primary" onClick={handleQuickSetup} disabled={saving}>
                Quick Setup (Zones 1–8)
              </button>
              <button type="button" className="btn-secondary" onClick={() => setIsAddOpen(true)}>
                + Add Custom Zone
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="zone-grid" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filteredZones.map((zone) => {
            const isFaulted = isZoneFaulted(zone.id);
            return (
              <article
                key={zone.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 14px",
                  borderRadius: 8,
                  border: `1px solid ${isFaulted ? "var(--color-danger-border)" : "var(--color-border-subtle)"}`,
                  background: isFaulted ? "var(--color-danger-bg)" : "var(--color-surface-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 160 }}>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontWeight: 700,
                      fontSize: 14,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border-subtle)",
                    }}
                  >
                    Zone {String(zone.id).padStart(2, "0")}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: 4,
                      color: isFaulted ? "var(--color-danger-text)" : "var(--color-success-text)",
                    }}
                  >
                    {isFaulted ? "⚠️ FAULTED" : "✓ Normal"}
                  </span>
                </div>

                <div style={{ flex: 1, minWidth: 180 }}>
                  {isAdmin ? (
                    <input
                      value={zone.name}
                      placeholder={`e.g. Zone ${zone.id}`}
                      onChange={(e) => handleUpdateZone(zone.id, { name: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        fontSize: 14,
                        borderRadius: 6,
                        border: "1px solid var(--color-border-subtle)",
                        background: "var(--color-surface)",
                        color: "var(--color-text-primary)",
                      }}
                    />
                  ) : (
                    <span style={{ fontSize: 14, color: "var(--color-text-primary)" }}>
                      {zone.name || `Zone ${zone.id}`}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {isAdmin ? (
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer", color: "var(--color-text-muted)" }}>
                      <input
                        type="checkbox"
                        checked={zone.enabled}
                        onChange={(e) => handleUpdateZone(zone.id, { enabled: e.target.checked })}
                      />
                      Monitored
                    </label>
                  ) : (
                    <span style={{ fontSize: 12, color: zone.enabled ? "var(--color-success-text)" : "var(--color-text-muted)" }}>
                      {zone.enabled ? "Monitored" : "Bypassed"}
                    </span>
                  )}

                  {isAdmin ? (
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: "4px 8px", fontSize: 12, color: "var(--color-danger-text)" }}
                      onClick={() => setDeleteTarget(zone)}
                      title={`Delete Zone ${zone.id}`}
                    >
                      ✕
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Add Zone Dialog */}
      <Modal open={isAddOpen} title="Add Alarm Zone" onClose={() => setIsAddOpen(false)} width={380}>
        <form onSubmit={handleAddZone} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {error ? <p style={{ color: "var(--color-danger-text)", fontSize: 13, margin: 0 }}>{error}</p> : null}
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--color-text-muted)" }}>
            Zone Number
            <input
              type="number"
              min="1"
              max="128"
              required
              placeholder="e.g. 1"
              value={newZoneId}
              onChange={(e) => setNewZoneId(e.target.value)}
              style={{ padding: "8px 10px", fontSize: 14, borderRadius: 6, border: "1px solid var(--color-border-subtle)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--color-text-muted)" }}>
            Zone Description / Name
            <input
              type="text"
              placeholder="e.g. Front Door"
              value={newZoneName}
              onChange={(e) => setNewZoneName(e.target.value)}
              style={{ padding: "8px 10px", fontSize: 14, borderRadius: 6, border: "1px solid var(--color-border-subtle)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}
            />
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--color-text-muted)", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={newZoneEnabled}
              onChange={(e) => setNewZoneEnabled(e.target.checked)}
            />
            Monitored (Enabled)
          </label>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
            <button type="button" className="btn-secondary" onClick={() => setIsAddOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Adding..." : "Add Zone"}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        message={`Are you sure you want to delete Zone ${deleteTarget?.id} (${deleteTarget?.name || "unnamed"})?`}
        confirmLabel="Delete Zone"
        onConfirm={handleDeleteZone}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
}

function updateZone(zones: ZoneInfo[], id: number, patch: Partial<ZoneInfo>) {
  const existing = zones.find((zone) => zone.id === id);
  if (!existing) {
    return [...zones, { id, name: "", enabled: true, ...patch }];
  }
  return zones.map((zone) => (zone.id === id ? { ...zone, ...patch } : zone));
}
