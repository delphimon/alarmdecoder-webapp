import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AuditEntry,
  ApiToken,
  ApiTokenCreateResponse,
  AuthStatus,
  CustomButton,
  EffectiveConfig,
  NotificationConfig,
  PanelEvent,
  PanelState,
  RawAlarmMessage,
  SettingItem,
  SetupStatus,
  Snapshot,
  SocketMessage,
  User,
  ZoneInfo,
} from "../types";

const fallbackState: PanelState = {
  connected: false,
  connection_status: "idle",
  panel_type: "ADEMCO",
  display_line1: "CONNECTING",
  display_line2: "FAKE ADAPTER",
  armed: false,
  armed_stay: false,
  armed_mode: "disarmed",
  ready: false,
  chime: false,
  alarming: false,
  bypassed: false,
  fire_detected: false,
  battery_trouble: false,
  trouble: false,
  trouble_text: null,
  panic: false,
  power: "AC",
  relay_status: {},
  beeps: 0,
  cursor_location: null,
  faulted_zones: [],
  last_message: "",
  last_raw_message: null,
  last_command: null,
  updated_at: new Date(0).toISOString(),
};

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

function websocketUrl(): string {
  const explicitBase = import.meta.env.VITE_API_BASE_URL;
  if (explicitBase) {
    const url = new URL(explicitBase);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/ws/state";
    url.search = "";
    return url.toString();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/state`;
}

export function useAlarmDecoder() {
  const [state, setState] = useState<PanelState>(fallbackState);
  const [events, setEvents] = useState<PanelEvent[]>([]);
  const [rawMessages, setRawMessages] = useState<RawAlarmMessage[]>([]);
  const [config, setConfig] = useState<EffectiveConfig | null>(null);
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [lastRealtimeEvent, setLastRealtimeEvent] = useState<PanelEvent | null>(null);
  const [socketStatus, setSocketStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const reconnectTimer = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const csrfToken = auth?.csrf_token ?? "";

  const loadSnapshot = useCallback(async () => {
    const [response, configResponse, authResponse] = await Promise.all([
      fetch(`${apiBase()}/api/snapshot`),
      fetch(`${apiBase()}/api/config/effective`),
      fetch(`${apiBase()}/api/auth/me`, { credentials: "same-origin" }),
    ]);
    if (!response.ok) {
      throw new Error(`Snapshot failed: ${response.status}`);
    }
    if (!configResponse.ok) {
      throw new Error(`Config failed: ${configResponse.status}`);
    }
    if (!authResponse.ok) {
      throw new Error(`Auth failed: ${authResponse.status}`);
    }
    const snapshot = (await response.json()) as Snapshot;
    setState(snapshot.state);
    setEvents(snapshot.events);
    setRawMessages(snapshot.raw_messages);
    setConfig((await configResponse.json()) as EffectiveConfig);
    setAuth((await authResponse.json()) as AuthStatus);
  }, []);

  useEffect(() => {
    void loadSnapshot().catch(() => {
      setSocketStatus("closed");
    });
  }, [loadSnapshot]);

  useEffect(() => {
    let disposed = false;

    const connect = () => {
      if (disposed) {
        return;
      }

      setSocketStatus("connecting");
      const ws = new WebSocket(websocketUrl());
      wsRef.current = ws;

      ws.onopen = () => setSocketStatus("open");
      ws.onmessage = (message) => {
        const payload = JSON.parse(message.data) as SocketMessage;
        if (payload.state) {
          setState(payload.state);
        }
        if (payload.events) {
          setEvents(payload.events);
        }
        if (payload.raw_messages) {
          setRawMessages(payload.raw_messages);
        }
        if (payload.event) {
          setLastRealtimeEvent(payload.event);
          setEvents((current) => [payload.event as PanelEvent, ...current].slice(0, 50));
          if (payload.event.type === "raw_message") {
            const raw = payload.event.data.raw;
            if (typeof raw === "string") {
              const rawMessage: RawAlarmMessage = {
                id: payload.event.id,
                timestamp: payload.event.timestamp,
                raw,
              };
              setRawMessages((current) => [rawMessage, ...current].slice(0, 100));
            }
          }
        }
      };
      ws.onclose = () => {
        setSocketStatus("closed");
        if (!disposed) {
          reconnectTimer.current = window.setTimeout(connect, 900);
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer.current !== null) {
        window.clearTimeout(reconnectTimer.current);
      }
      wsRef.current?.close();
    };
  }, []);

  const sendCommand = useCallback(async (keys: string, dangerousConfirmed = false) => {
    const response = await fetch(`${apiBase()}/api/keypad/command`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}) },
      body: JSON.stringify({ keys, dangerous_confirmed: dangerousConfirmed }),
    });

    if (!response.ok) {
      let detail = `Command failed: ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string };
        detail = body.detail ?? detail;
      } catch {
        // Keep the generic HTTP status message.
      }
      throw new Error(detail);
    }

    const nextState = (await response.json()) as PanelState;
    setState(nextState);
  }, [csrfToken]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch(`${apiBase()}/api/auth/login`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      throw new Error("Login failed.");
    }
    await loadSnapshot();
  }, [loadSnapshot]);

  const logout = useCallback(async () => {
    await fetch(`${apiBase()}/api/auth/logout`, {
      method: "POST",
      credentials: "same-origin",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    });
    await loadSnapshot();
  }, [csrfToken, loadSnapshot]);

  const apiGet = useCallback(async <T,>(path: string): Promise<T> => {
    const response = await fetch(`${apiBase()}${path}`, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`${path} failed: ${response.status}`);
    }
    return (await response.json()) as T;
  }, []);

  const apiSend = useCallback(async <T,>(path: string, method: string, body?: unknown): Promise<T> => {
    const response = await fetch(`${apiBase()}${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      let detail = `${path} failed: ${response.status}`;
      try {
        const data = (await response.json()) as { detail?: string };
        detail = data.detail ?? detail;
      } catch {
        // Keep generic detail.
      }
      throw new Error(detail);
    }
    return (await response.json()) as T;
  }, [csrfToken]);

  const changePassword = useCallback((payload: { current_password: string; new_password: string }) => apiSend<{ status: string }>("/api/account/password", "POST", payload), [apiSend]);
  const loadHistoryEvents = useCallback((offset = 0) => apiGet<PanelEvent[]>(`/api/history/events?limit=50&offset=${offset}`), [apiGet]);
  const loadHistoryRawMessages = useCallback((offset = 0) => apiGet<RawAlarmMessage[]>(`/api/history/raw-messages?limit=50&offset=${offset}`), [apiGet]);
  const loadZones = useCallback(() => apiGet<ZoneInfo[]>("/api/zones"), [apiGet]);
  const saveZones = useCallback((zones: ZoneInfo[]) => apiSend<ZoneInfo[]>("/api/zones", "PUT", { zones }), [apiSend]);
  const loadSettings = useCallback(() => apiGet<SettingItem[]>("/api/settings"), [apiGet]);
  const saveSettings = useCallback((settings: SettingItem[]) => apiSend<SettingItem[]>("/api/settings", "PUT", { settings }), [apiSend]);
  const loadUsers = useCallback(() => apiGet<User[]>("/api/admin/users"), [apiGet]);
  const createUser = useCallback((payload: { username: string; password: string; role: User["role"] }) => apiSend<User>("/api/admin/users", "POST", payload), [apiSend]);
  const updateUser = useCallback((username: string, payload: Partial<User> & { password?: string }) => apiSend<User>(`/api/admin/users/${encodeURIComponent(username)}`, "PATCH", payload), [apiSend]);
  const deleteUser = useCallback((username: string) => apiSend<{ status: string }>(`/api/admin/users/${encodeURIComponent(username)}`, "DELETE"), [apiSend]);
  const loadNotifications = useCallback(() => apiGet<NotificationConfig[]>("/api/admin/notifications"), [apiGet]);
  const saveNotifications = useCallback((configs: NotificationConfig[]) => apiSend<NotificationConfig[]>("/api/admin/notifications", "PUT", configs), [apiSend]);
  const loadAudit = useCallback(() => apiGet<AuditEntry[]>("/api/audit?limit=50"), [apiGet]);
  const loadSetupStatus = useCallback(() => apiGet<SetupStatus>("/api/setup/status"), [apiGet]);
  const completeSetup = useCallback((payload: { username: string; password: string; panel_type: "ADEMCO" | "DSC"; adapter: string }) => apiSend<User>("/api/setup/complete", "POST", payload), [apiSend]);
  const loadCustomButtons = useCallback(() => apiGet<CustomButton[]>("/api/custom-buttons"), [apiGet]);
  const createCustomButton = useCallback((payload: { label: string; command: string; dangerous: boolean }) => apiSend<CustomButton>("/api/custom-buttons", "POST", payload), [apiSend]);
  const updateCustomButton = useCallback((id: number, payload: Partial<{ label: string; command: string; dangerous: boolean; enabled: boolean; sort_order: number }>) => apiSend<CustomButton>(`/api/custom-buttons/${id}`, "PATCH", payload), [apiSend]);
  const deleteCustomButton = useCallback((id: number) => apiSend<{ status: string }>(`/api/custom-buttons/${id}`, "DELETE"), [apiSend]);
  const sendCustomButton = useCallback((id: number, dangerousConfirmed = false) => apiSend<PanelState>(`/api/custom-buttons/${id}/send`, "POST", { dangerous_confirmed: dangerousConfirmed }).then((nextState) => {
    setState(nextState);
    return nextState;
  }), [apiSend]);
  const loadApiTokens = useCallback(() => apiGet<ApiToken[]>("/api/admin/api-tokens"), [apiGet]);
  const createApiToken = useCallback((payload: { username: string; name: string; role: User["role"] }) => apiSend<ApiTokenCreateResponse>("/api/admin/api-tokens", "POST", payload), [apiSend]);
  const deleteApiToken = useCallback((id: number) => apiSend<{ status: string }>(`/api/admin/api-tokens/${id}`, "DELETE"), [apiSend]);
  const exportSettings = useCallback(() => apiGet<Record<string, unknown>>("/api/admin/export"), [apiGet]);
  const importSettings = useCallback((data: Record<string, unknown>, dryRun = true) => apiSend<Record<string, unknown>>("/api/admin/import", "POST", { data, dry_run: dryRun }), [apiSend]);
  const testNotification = useCallback((provider: NotificationConfig["provider"], config: Record<string, unknown>) => apiSend<{ status: string }>("/api/admin/notifications/test", "POST", { provider, config }), [apiSend]);

  return useMemo(
    () => ({
      state,
      events,
      rawMessages,
      socketStatus,
      config,
      auth,
      lastRealtimeEvent,
      sendCommand,
      login,
      logout,
      changePassword,
      reload: loadSnapshot,
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
      loadAudit,
      loadSetupStatus,
      completeSetup,
      loadCustomButtons,
      createCustomButton,
      updateCustomButton,
      deleteCustomButton,
      sendCustomButton,
      loadApiTokens,
      createApiToken,
      deleteApiToken,
      exportSettings,
      importSettings,
      testNotification,
    }),
    [
      state,
      events,
      rawMessages,
      socketStatus,
      config,
      auth,
      lastRealtimeEvent,
      sendCommand,
      login,
      logout,
      changePassword,
      loadSnapshot,
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
      loadAudit,
      loadSetupStatus,
      completeSetup,
      loadCustomButtons,
      createCustomButton,
      updateCustomButton,
      deleteCustomButton,
      sendCustomButton,
      loadApiTokens,
      createApiToken,
      deleteApiToken,
      exportSettings,
      importSettings,
      testNotification,
    ],
  );
}
