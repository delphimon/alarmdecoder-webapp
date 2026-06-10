export type PanelState = {
  connected: boolean;
  connection_status: "idle" | "connecting" | "connected" | "disconnected" | "reconnecting" | "error";
  panel_type: "ADEMCO" | "DSC";
  display_line1: string;
  display_line2: string;
  armed: boolean;
  armed_stay: boolean;
  armed_mode: "disarmed" | "away" | "stay" | "unknown";
  ready: boolean;
  chime: boolean;
  alarming: boolean;
  bypassed: boolean;
  fire_detected: boolean;
  battery_trouble: boolean;
  trouble: boolean;
  trouble_text: string | null;
  panic: boolean;
  power: "AC" | "BATTERY" | "UNKNOWN";
  relay_status: Record<string, boolean>;
  beeps: number;
  cursor_location: number | null;
  faulted_zones: number[];
  last_message: string;
  last_raw_message: string | null;
  last_command: string | null;
  updated_at: string;
};

export type PanelEvent = {
  id: string;
  timestamp: string;
  type: string;
  message: string;
  data: Record<string, unknown>;
};

export type Snapshot = {
  state: PanelState;
  events: PanelEvent[];
  raw_messages: RawAlarmMessage[];
};

export type RawAlarmMessage = {
  id: string;
  timestamp: string;
  raw: string;
};

export type EffectiveConfig = {
  adapter: string;
  ser2sock_host: string;
  ser2sock_port: number;
  ser2sock_tls: boolean;
  serial_path: string;
  serial_baudrate: number;
  panel_type: "ADEMCO" | "DSC";
  read_only: boolean;
  allow_commands: boolean;
  auth_required: boolean;
  database_url: string;
  reconnect_initial_delay_seconds: number;
  reconnect_max_delay_seconds: number;
  command_cooldown_seconds: number;
  raw_retention_days: number;
  event_retention_days: number;
};

export type User = {
  id: number | null;
  username: string;
  role: "admin" | "operator" | "viewer";
  disabled: boolean;
};

export type CustomButton = {
  id: number;
  label: string;
  dangerous: boolean;
  enabled: boolean;
  sort_order: number;
};

export type ApiToken = {
  id: number;
  name: string;
  username: string;
  token_prefix: string;
  role: "admin" | "operator" | "viewer";
  disabled: boolean;
  created_at: string;
  last_used_at: string | null;
};

export type ApiTokenCreateResponse = {
  token: string;
  record: ApiToken;
};

export type SetupStatus = {
  setup_required: boolean;
  users_exist: boolean;
  adapter: string;
  panel_type: "ADEMCO" | "DSC";
};

export type AuthStatus = {
  authenticated: boolean;
  auth_required: boolean;
  csrf_token: string | null;
  user: User | null;
};

export type SettingItem = {
  key: string;
  value: string;
};

export type ZoneInfo = {
  id: number;
  name: string;
  enabled: boolean;
};

export type NotificationConfig = {
  id: number | null;
  provider: "webhook" | "smtp" | "test";
  enabled: boolean;
  config: Record<string, unknown>;
};

export type AuditEntry = {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
};

export type SocketMessage = {
  type: "snapshot" | "state" | "event";
  state?: PanelState;
  event?: PanelEvent;
  events?: PanelEvent[];
  raw_messages?: RawAlarmMessage[];
};
