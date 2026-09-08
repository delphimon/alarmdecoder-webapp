import { useCallback, useEffect, useRef, useState } from "react";
import { ConfirmDialog } from "./components/Dialog";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { Keypad } from "./components/Keypad";
import { LoginPanel } from "./components/LoginPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { ZonePanel } from "./components/ZonePanel";
import { useAlarmDecoder } from "./hooks/useAlarmDecoder";
import type { CustomButton } from "./types";
import "./styles.css";

// ── Audio: shared AudioContext with pre-decoded buffers ──────────────────────

interface BeepPlayer {
  play(count: number): void;
}

/** Build a BeepPlayer backed by a shared AudioContext and pre-decoded AudioBuffers. */
function createBeepPlayer(): BeepPlayer {
  let ctx: AudioContext | null = null;
  const buffers: (AudioBuffer | null)[] = new Array(7).fill(null);
  let loading = false;

  const init = async () => {
    if (ctx || loading) return;
    loading = true;
    try {
      ctx = new AudioContext();
      await Promise.all(
        Array.from({ length: 7 }, async (_, i) => {
          try {
            const res = await fetch(`/sounds/${i + 1}beep.wav`);
            const data = await res.arrayBuffer();
            buffers[i] = await ctx!.decodeAudioData(data);
          } catch {
            // Individual beep file missing — skip gracefully.
          }
        }),
      );
    } catch {
      // AudioContext unavailable (non-HTTPS, old browser) — fall back to silence.
    }
    loading = false;
  };

  return {
    play(count: number) {
      const limited = Math.max(1, Math.min(Math.trunc(count), 7));
      const buf = buffers[limited - 1];
      if (ctx && buf) {
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.start();
      } else {
        // Lazy init on first user interaction (satisfies autoplay policy).
        void init();
      }
    },
  };
}

const beepPlayer = createBeepPlayer();

// ── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const alarm = useAlarmDecoder();
  const {
    state,
    events,
    rawMessages,
    lastRealtimeEvent,
    socketStatus,
    config,
    auth,
    sendCommand,
    login,
    loginWithPasskey,
    logout,
    changePassword,

    loadHistoryEvents,
    loadHistoryRawMessages,
    loadZones,
    saveZones,
    deleteZone,
    refreshConfig,
    loadSettings,
    saveSettings,
    loadUsers,
    createUser,
    updateUser,
    deleteUser,
    loadNotifications,
    saveNotifications,
    loadCustomButtons,
    createCustomButton,
    updateCustomButton,
    deleteCustomButton,
    sendCustomButton,
    loadAudit,
    loadApiTokens,
    createApiToken,
    deleteApiToken,
    exportSettings,
    importSettings,
    testNotification,
    getPinStatus,
    savePin,
    loadPasskeys,
    deletePasskey,
    registerPasskey,
  } = alarm;


  const [muted, setMuted] = useState(() => localStorage.getItem("mute") === "1" || localStorage.getItem("ad2-muted") === "1");
  const [displayFlash, setDisplayFlash] = useState(false);
  const [customButtons, setCustomButtons] = useState<CustomButton[]>([]);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [view, setView] = useState<"keypad" | "history" | "zones" | "diagnostics" | "settings">("keypad");

  // Auto-clear command error after 8 seconds
  useEffect(() => {
    if (!commandError) return;
    const timer = window.setTimeout(() => setCommandError(null), 8000);
    return () => window.clearTimeout(timer);
  }, [commandError]);

  // ── Confirm dialog state ─────────────────────────────────────────────────
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState("");
  const confirmResolverRef = useRef<((confirmed: boolean) => void) | null>(null);

  /**
   * Native <dialog> replacement for window.confirm().
   * Returns a Promise<boolean> — resolves true on confirm, false on cancel.
   */
  const showConfirm = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmMessage(message);
      confirmResolverRef.current = resolve;
      setConfirmOpen(true);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setConfirmOpen(false);
    confirmResolverRef.current?.(true);
  }, []);

  const handleConfirmCancel = useCallback(() => {
    setConfirmOpen(false);
    confirmResolverRef.current?.(false);
  }, []);

  // ── Live region announcements ────────────────────────────────────────────
  const [alarmAnnouncement, setAlarmAnnouncement] = useState("");
  const [statusAnnouncement, setStatusAnnouncement] = useState("");

  const lastAlarmStateRef = useRef(false);
  const lastConnectionRef = useRef(socketStatus);

  useEffect(() => {
    if (state.alarming && !lastAlarmStateRef.current) {
      setAlarmAnnouncement("ALARM — panel is alarming");
    } else if (state.fire_detected && !lastAlarmStateRef.current) {
      setAlarmAnnouncement("FIRE ALARM detected");
    } else if (!state.alarming && !state.fire_detected && lastAlarmStateRef.current) {
      setAlarmAnnouncement("Alarm cleared");
    }
    lastAlarmStateRef.current = state.alarming || state.fire_detected;
  }, [state.alarming, state.fire_detected]);

  useEffect(() => {
    if (socketStatus !== lastConnectionRef.current) {
      setStatusAnnouncement(`AlarmDecoder connection ${socketStatus}`);
      lastConnectionRef.current = socketStatus;
    }
  }, [socketStatus]);

  // ── Mute persistence ─────────────────────────────────────────────────────
  useEffect(() => {
    localStorage.setItem("ad2-muted", muted ? "1" : "0");
    localStorage.setItem("mute", muted ? "1" : "0");
  }, [muted]);

  // ── Beep + LCD flash on panel messages ──────────────────────────────────
  const lastBeepEventId = useRef<string>("");

  useEffect(() => {
    if (!lastRealtimeEvent || lastRealtimeEvent.id === lastBeepEventId.current) {
      return;
    }
    if (!["panel_display", "panel_message"].includes(lastRealtimeEvent.type)) {
      return;
    }
    const beeps = Number(lastRealtimeEvent.data.beeps ?? 0);
    if (!Number.isFinite(beeps) || beeps <= 0) {
      return;
    }

    lastBeepEventId.current = lastRealtimeEvent.id;
    setDisplayFlash(true);
    const flashTimer = window.setTimeout(() => setDisplayFlash(false), 160 * Math.min(beeps, 7));
    if (!muted) {
      beepPlayer.play(beeps);
    }
    return () => window.clearTimeout(flashTimer);
  }, [lastRealtimeEvent, muted]);

  // ── Command handling ─────────────────────────────────────────────────────
  const handleCommand = async (command: string, confirmDangerous = false) => {
    setCommandError(null);
    if (config?.read_only) {
      setCommandError("Read-only adapter active. Keypad commands are blocked.");
      return;
    }
    if (!config?.allow_commands) {
      setCommandError("Command mode is disabled. Set ALARMDECODER_ALLOW_COMMANDS=true and keep READ_ONLY=false.");
      return;
    }
    if (auth?.auth_required && auth.user?.role !== "operator" && auth.user?.role !== "admin") {
      setCommandError("Operator or admin role required.");
      return;
    }
    if (confirmDangerous) {
      let promptMsg = "Send this security-sensitive alarm command?";
      if (command === "F1") promptMsg = "Are you sure? Call the Fire Department (F1 Fire Alarm)?";
      else if (command === "F2") promptMsg = "Are you sure? Call the Police Department (F2 Police Panic)?";
      else if (command === "F3") promptMsg = "Are you sure? Call Medical Assistance (F3 Medical Emergency)?";
      else if (command === "F4") promptMsg = "Send Special / Program function (F4)?";
      else if (command === "DISARM") promptMsg = "Send Disarm command to panel?";
      const confirmed = await showConfirm(promptMsg);
      if (!confirmed) return;
    }
    try {
      await sendCommand(command, confirmDangerous);
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : "Command failed.");
    }
  };

  // ── Custom buttons ───────────────────────────────────────────────────────
  const refreshCustomButtons = useCallback(async () => {
    if (!auth?.authenticated) {
      setCustomButtons([]);
      return;
    }
    try {
      setCustomButtons(await loadCustomButtons());
    } catch {
      setCustomButtons([]);
    }
  }, [auth?.authenticated, loadCustomButtons]);

  const handleCreateCustomButton = useCallback(async () => {
    // Custom button creation is handled via dialog in Keypad/SettingsPanel.
    // This callback is kept for API compatibility; the dialog state lives inside SettingsPanel.
    try {
      setCustomButtons(await loadCustomButtons());
    } catch {
      // ignore
    }
  }, [loadCustomButtons]);

  const handleSendCustomButton = useCallback(
    async (id: number, confirmDangerous = false) => {
      setCommandError(null);
      if (confirmDangerous) {
        const confirmed = await showConfirm("Send this custom security-sensitive alarm command?");
        if (!confirmed) return;
      }
      try {
        await sendCustomButton(id, confirmDangerous);
      } catch (error) {
        setCommandError(error instanceof Error ? error.message : "Custom command failed.");
      }
    },
    [sendCustomButton, showConfirm],
  );

  const commandDisabled = Boolean(
    config?.read_only ||
      !config?.allow_commands ||
      (auth?.auth_required && auth.user?.role !== "operator" && auth.user?.role !== "admin"),
  );
  const disabledReason = config?.read_only
    ? "Read-only adapter active. Keypad commands are blocked."
    : !config?.allow_commands
      ? "Command mode is disabled."
      : auth?.auth_required && !auth.authenticated
        ? "Sign in as an operator or admin to send commands."
        : auth?.auth_required && auth.user?.role === "viewer"
          ? "Viewer role cannot send commands."
          : "";

  return (
    <div className="app-layout">
      {/* ── Accessibility: live announcement regions ── */}
      <div role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
        {alarmAnnouncement}
      </div>
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {statusAnnouncement}
      </div>

      {/* ── Confirm Dialog (replaces window.confirm) ── */}
      <ConfirmDialog
        open={confirmOpen}
        message={confirmMessage}
        confirmLabel="Send command"
        onConfirm={handleConfirm}
        onCancel={handleConfirmCancel}
      />

      {/* ── Top Navigation Bar modeled after reference control panel UI ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <img src="/img/logo.png" alt="AlarmDecoder" className="brand-logo" />
        </div>
        <nav className="topbar-nav" aria-label="Primary navigation">
          {(["keypad", "history", "zones", "diagnostics", "settings"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={`nav-link ${view === item ? "active" : ""}`}
              onClick={() => setView(item)}
            >
              {item === "history"
                ? "Log"
                : item === "keypad"
                  ? "Keypad"
                  : item === "zones"
                    ? "Zones"
                    : item === "diagnostics"
                      ? "Diagnostics"
                      : "Settings"}
            </button>
          ))}
          {auth?.authenticated ? (
            <button className="nav-link nav-logout" type="button" onClick={logout}>
              Log out
            </button>
          ) : null}
          <div className="topbar-actions">
            <span
              className={`connection-dot ${socketStatus}`}
              title={`WebSocket: ${socketStatus} | Adapter: ${config?.adapter ?? "unknown"}${config?.read_only ? " (Read-only)" : ""}`}
              aria-label={`Connection status: ${socketStatus}`}
            />
            <ThemeToggle />
          </div>
        </nav>
      </header>

      {/* ── Main Content Workspace ── */}
      <main className={`workspace ${view === "keypad" ? "workspace-keypad" : "workspace-full"}`}>
        {auth?.auth_required && !auth.authenticated ? (
          <LoginPanel onLogin={login} onLoginWithPasskey={loginWithPasskey} />
        ) : view === "history" ? (
          <HistoryPanel loadEvents={loadHistoryEvents} loadRawMessages={loadHistoryRawMessages} />
        ) : view === "zones" ? (
          <ZonePanel state={state} auth={auth} loadZones={loadZones} saveZones={saveZones} deleteZone={deleteZone} />
        ) : view === "diagnostics" ? (
          <DiagnosticsPanel state={state} events={events} rawMessages={rawMessages} config={config} socketStatus={socketStatus} />
        ) : view === "settings" ? (
          <SettingsPanel
            auth={auth}
            config={config}
            refreshConfig={refreshConfig}
            loadSettings={loadSettings}
            saveSettings={saveSettings}
            loadUsers={loadUsers}
            createUser={createUser}
            updateUser={updateUser}
            deleteUser={deleteUser}
            changePassword={changePassword}
            loadNotifications={loadNotifications}
            saveNotifications={saveNotifications}
            loadCustomButtons={loadCustomButtons}
            createCustomButton={createCustomButton}
            updateCustomButton={updateCustomButton}
            deleteCustomButton={deleteCustomButton}
            loadApiTokens={loadApiTokens}
            createApiToken={createApiToken}
            deleteApiToken={deleteApiToken}
            exportSettings={exportSettings}
            importSettings={importSettings}
            testNotification={testNotification}
            loadAudit={loadAudit}
            getPinStatus={getPinStatus}
            savePin={savePin}
            loadPasskeys={loadPasskeys}
            deletePasskey={deletePasskey}
            registerPasskey={registerPasskey}
          />
        ) : (
          <Keypad
            state={state}
            muted={muted}
            disabled={commandDisabled}
            disabledReason={disabledReason}
            flash={displayFlash}
            commandError={commandError}
            onClearCommandError={() => setCommandError(null)}
            customButtons={customButtons}
            onLoadCustomButtons={refreshCustomButtons}
            onCreateCustomButton={handleCreateCustomButton}
            onSendCustomButton={handleSendCustomButton}
            onMuteChange={setMuted}
            onCommand={handleCommand}
          />
        )}
      </main>

      {/* ── Footer modeled after classic AlarmDecoder ── */}
      <footer className="app-footer">
        <div>
          <span>© {new Date().getFullYear()} AlarmDecoder</span>
          <span className="footer-dot">·</span>
          <span>{config?.adapter ? `Adapter: ${config.adapter}` : "Modern Webapp"}</span>
          {config?.read_only ? (
            <>
              <span className="footer-dot">·</span>
              <span className="footer-badge read-only">Read-only</span>
            </>
          ) : (
            <>
              <span className="footer-dot">·</span>
              <span className="footer-badge live">Commands {config?.allow_commands ? "Enabled" : "Disabled"}</span>
            </>
          )}
        </div>
      </footer>
    </div>
  );
}
