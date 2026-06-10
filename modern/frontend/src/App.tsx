import { useCallback, useEffect, useRef, useState } from "react";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { EventLog } from "./components/EventLog";
import { HistoryPanel } from "./components/HistoryPanel";
import { Keypad } from "./components/Keypad";
import { LoginPanel } from "./components/LoginPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { StateSummary } from "./components/StateSummary";
import { ZonePanel } from "./components/ZonePanel";
import { useAlarmDecoder } from "./hooks/useAlarmDecoder";
import type { CustomButton } from "./types";
import "./styles.css";

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
    logout,
    changePassword,
    loadHistoryEvents,
    loadHistoryRawMessages,
    loadZones,
    saveZones,
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
  } = alarm;
  const [muted, setMuted] = useState(() => localStorage.getItem("mute") === "1" || localStorage.getItem("ad2-muted") === "1");
  const [displayFlash, setDisplayFlash] = useState(false);
  const [customButtons, setCustomButtons] = useState<CustomButton[]>([]);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [view, setView] = useState<"keypad" | "history" | "zones" | "diagnostics" | "settings">("keypad");
  const lastBeepEventId = useRef<string>("");

  useEffect(() => {
    localStorage.setItem("ad2-muted", muted ? "1" : "0");
    localStorage.setItem("mute", muted ? "1" : "0");
  }, [muted]);

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
      playLegacyBeep(beeps);
    }
    return () => window.clearTimeout(flashTimer);
  }, [lastRealtimeEvent, muted]);

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
    if (confirmDangerous && !window.confirm(`Send this security-sensitive alarm command?`)) {
      return;
    }
    try {
      await sendCommand(command, confirmDangerous);
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : "Command failed.");
    }
  };

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
    const label = window.prompt("Button label");
    const command = window.prompt("Command string. It will be stored server-side and never shown in diagnostics.");
    if (!label || !command) {
      return;
    }
    const dangerous = window.confirm("Require confirmation before sending this custom command?");
    const created = await createCustomButton({ label, command, dangerous });
    setCustomButtons((current) => [...current, created].sort((a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label)));
  }, [createCustomButton]);

  const handleSendCustomButton = useCallback(async (id: number, confirmDangerous = false) => {
    setCommandError(null);
    if (confirmDangerous && !window.confirm("Send this custom security-sensitive alarm command?")) {
      return;
    }
    try {
      await sendCustomButton(id, confirmDangerous);
    } catch (error) {
      setCommandError(error instanceof Error ? error.message : "Custom command failed.");
    }
  }, [sendCustomButton]);

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
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>AlarmDecoder Modern</h1>
          <p>Read-only capable AlarmDecoder monitor with live state diagnostics</p>
        </div>
        <div className="topbar-status">
          <span className="adapter-badge">{config?.adapter ?? "adapter"}</span>
          <span className={config?.read_only ? "read-only-badge" : "command-enabled-badge"}>
            {config?.read_only ? "Read-only" : config?.allow_commands ? "Commands enabled" : "Commands disabled"}
          </span>
          {auth?.authenticated ? <button className="text-button" type="button" onClick={logout}>Logout {auth.user?.username}</button> : null}
          <span className={`socket-badge ${socketStatus}`}>WebSocket {socketStatus}</span>
        </div>
      </header>

      <nav className="page-tabs" aria-label="Primary views">
        {(["keypad", "history", "zones", "diagnostics", "settings"] as const).map((item) => (
          <button key={item} type="button" className={view === item ? "active" : ""} onClick={() => setView(item)}>
            {item === "history" ? "Log" : item}
          </button>
        ))}
      </nav>

      <div className="workspace">
        <div>
          {auth?.auth_required && !auth.authenticated ? (
            <LoginPanel onLogin={login} />
          ) : view === "history" ? (
            <HistoryPanel loadEvents={loadHistoryEvents} loadRawMessages={loadHistoryRawMessages} />
          ) : view === "zones" ? (
            <ZonePanel state={state} auth={auth} loadZones={loadZones} saveZones={saveZones} />
          ) : view === "diagnostics" ? (
            <DiagnosticsPanel state={state} events={events} rawMessages={rawMessages} config={config} socketStatus={socketStatus} />
          ) : view === "settings" ? (
            <SettingsPanel
              auth={auth}
              config={config}
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
            />
          ) : (
            <Keypad
              state={state}
              muted={muted}
              disabled={commandDisabled}
              disabledReason={disabledReason}
              flash={displayFlash}
              customButtons={customButtons}
              onLoadCustomButtons={refreshCustomButtons}
              onCreateCustomButton={handleCreateCustomButton}
              onSendCustomButton={handleSendCustomButton}
              onMuteChange={setMuted}
              onCommand={handleCommand}
            />
          )}
          {commandError ? <p className="command-error">{commandError}</p> : null}
        </div>
        <div className="side-rail">
          <StateSummary state={state} config={config} socketStatus={socketStatus} />
          <EventLog events={events} />
          <DiagnosticsPanel
            state={state}
            events={events}
            rawMessages={rawMessages}
            config={config}
            socketStatus={socketStatus}
          />
        </div>
      </div>
    </main>
  );
}

function playLegacyBeep(count: number) {
  const limited = Math.max(1, Math.min(Math.trunc(count), 7));
  const audio = new Audio(`/sounds/${limited}beep.wav`);
  audio.load();
  void audio.play().catch(() => {
    // Browsers can block autoplay before user interaction; panel state must still update.
  });
}
