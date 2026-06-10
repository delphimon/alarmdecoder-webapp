import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  ApiToken,
  ApiTokenCreateResponse,
  AuditEntry,
  AuthStatus,
  CustomButton,
  EffectiveConfig,
  NotificationConfig,
  SettingItem,
  User,
} from "../types";

type SettingsTab = "overview" | "device" | "notifications" | "keypad" | "users" | "account" | "tokens" | "import" | "advanced";

type SettingsPanelProps = {
  auth: AuthStatus | null;
  config: EffectiveConfig | null;
  loadSettings: () => Promise<SettingItem[]>;
  saveSettings: (settings: SettingItem[]) => Promise<SettingItem[]>;
  loadUsers: () => Promise<User[]>;
  createUser: (payload: { username: string; password: string; role: User["role"] }) => Promise<User>;
  updateUser: (username: string, payload: Partial<User> & { password?: string }) => Promise<User>;
  deleteUser: (username: string) => Promise<{ status: string }>;
  changePassword: (payload: { current_password: string; new_password: string }) => Promise<{ status: string }>;
  loadNotifications: () => Promise<NotificationConfig[]>;
  saveNotifications: (configs: NotificationConfig[]) => Promise<NotificationConfig[]>;
  loadCustomButtons: () => Promise<CustomButton[]>;
  createCustomButton: (payload: { label: string; command: string; dangerous: boolean }) => Promise<CustomButton>;
  updateCustomButton: (id: number, payload: Partial<{ label: string; command: string; dangerous: boolean; enabled: boolean; sort_order: number }>) => Promise<CustomButton>;
  deleteCustomButton: (id: number) => Promise<{ status: string }>;
  loadApiTokens: () => Promise<ApiToken[]>;
  createApiToken: (payload: { username: string; name: string; role: User["role"] }) => Promise<ApiTokenCreateResponse>;
  deleteApiToken: (id: number) => Promise<{ status: string }>;
  exportSettings: () => Promise<Record<string, unknown>>;
  importSettings: (data: Record<string, unknown>, dryRun: boolean) => Promise<Record<string, unknown>>;
  testNotification: (provider: NotificationConfig["provider"], config: Record<string, unknown>) => Promise<{ status: string }>;
  loadAudit: () => Promise<AuditEntry[]>;
};

const tabs: Array<{ id: SettingsTab; label: string }> = [
  { id: "overview", label: "Settings" },
  { id: "device", label: "Device" },
  { id: "notifications", label: "Notifications" },
  { id: "keypad", label: "Keypad Settings" },
  { id: "users", label: "Users" },
  { id: "account", label: "Password" },
  { id: "tokens", label: "API Tokens" },
  { id: "import", label: "Export / Import" },
  { id: "advanced", label: "Advanced" },
];

export function SettingsPanel(props: SettingsPanelProps) {
  const { auth, config } = props;
  const [activeTab, setActiveTab] = useState<SettingsTab>("overview");
  const [settings, setSettings] = useState<SettingItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [notifications, setNotifications] = useState<NotificationConfig[]>([]);
  const [customButtons, setCustomButtons] = useState<CustomButton[]>([]);
  const [apiTokens, setApiTokens] = useState<ApiToken[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [oneTimeToken, setOneTimeToken] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const isAdmin = auth?.user?.role === "admin";
  const canOperate = auth?.user?.role === "admin" || auth?.user?.role === "operator";

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    void Promise.all([
      props.loadSettings(),
      props.loadUsers(),
      props.loadNotifications(),
      props.loadCustomButtons(),
      props.loadApiTokens(),
      props.loadAudit(),
    ])
      .then(([loadedSettings, loadedUsers, loadedNotifications, loadedButtons, loadedTokens, loadedAudit]) => {
        setSettings(loadedSettings);
        setUsers(loadedUsers);
        setNotifications(loadedNotifications.length ? loadedNotifications : [emptyWebhookNotification()]);
        setCustomButtons(loadedButtons);
        setApiTokens(loadedTokens);
        setAuditEntries(loadedAudit);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Settings load failed."));
  }, [isAdmin, props.loadSettings, props.loadUsers, props.loadNotifications, props.loadCustomButtons, props.loadApiTokens, props.loadAudit]);

  useEffect(() => {
    if (isAdmin || !canOperate) {
      return;
    }
    void props.loadCustomButtons().then(setCustomButtons).catch(() => setCustomButtons([]));
  }, [canOperate, isAdmin, props.loadCustomButtons]);

  const saveDeviceSettings = async () => {
    const keys = [
      "adapter",
      "panel_type",
      "ser2sock_host",
      "ser2sock_port",
      "ser2sock_tls",
      "serial_path",
      "serial_baudrate",
      "raw_retention_days",
      "event_retention_days",
    ];
    const next = await props.saveSettings(keys.map((key) => ({ key, value: settingValue(settings, key, fallbackSetting(config, key)) })));
    setSettings(next);
    setMessage("Device settings saved. Restart the backend for adapter changes to take effect.");
  };

  const addUser = async () => {
    const username = window.prompt("Username");
    const password = window.prompt("Temporary password, minimum 8 characters");
    if (!username || !password) return;
    const created = await props.createUser({ username, password, role: "viewer" });
    setUsers((current) => [...current, created].sort((a, b) => a.username.localeCompare(b.username)));
  };

  const addCustomButton = async () => {
    const label = window.prompt("Button label");
    const command = window.prompt("Command string. It is stored server-side and not shown in diagnostics.");
    if (!label || !command) return;
    const dangerous = window.confirm("Require confirmation before sending this custom command?");
    const created = await props.createCustomButton({ label, command, dangerous });
    setCustomButtons((current) => [...current, created].sort(sortButtons));
  };

  const replaceCustomButtonCommand = async (button: CustomButton) => {
    const command = window.prompt(`Replacement command for ${button.label}`);
    if (!command) return;
    const next = await props.updateCustomButton(button.id, { command });
    setCustomButtons((current) => current.map((item) => (item.id === next.id ? next : item)));
    setMessage("Custom button command replaced.");
  };

  const saveNotifications = async () => {
    const next = await props.saveNotifications(notifications);
    setNotifications(next.length ? next : [emptyWebhookNotification()]);
    setMessage("Notifications saved.");
  };

  const createToken = async () => {
    const username = window.prompt("Token username", auth?.user?.username ?? "");
    const name = window.prompt("Token name", "local automation");
    if (!username || !name) return;
    const response = await props.createApiToken({ username, name, role: "viewer" });
    setApiTokens((current) => [response.record, ...current]);
    setOneTimeToken(response.token);
    setMessage("API token created. Copy it now; it will not be shown again.");
  };

  const changePassword = async () => {
    const current_password = window.prompt("Current password");
    const new_password = window.prompt("New password, minimum 8 characters");
    if (!current_password || !new_password) return;
    await props.changePassword({ current_password, new_password });
    setMessage("Password changed.");
  };

  const exportConfig = async () => {
    const data = await props.exportSettings();
    setImportText(JSON.stringify(data, null, 2));
    setMessage("Export generated below.");
  };

  const importConfig = async (dryRun: boolean) => {
    const parsed = JSON.parse(importText) as Record<string, unknown>;
    const result = await props.importSettings(parsed, dryRun);
    setMessage(JSON.stringify(result));
    if (!dryRun) {
      setSettings(await props.loadSettings());
      setNotifications(await props.loadNotifications());
    }
  };

  return (
    <section className="summary-panel settings-shell" aria-label="Settings">
      <div className="section-heading">
        <h2>Settings</h2>
        <span>{auth?.user?.role ?? "viewer"}</span>
      </div>

      <nav className="settings-tabs" aria-label="Settings sections">
        {tabs.map((tab) => (
          <button key={tab.id} type="button" className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </nav>

      {message ? <p className="read-only-note">{message}</p> : null}
      {!isAdmin && activeTab !== "account" && activeTab !== "keypad" ? <p className="read-only-note">Admin role required for this settings section.</p> : null}

      {activeTab === "overview" ? <Overview config={config} /> : null}
      {activeTab === "device" && isAdmin ? <DeviceSettings config={config} settings={settings} setSettings={setSettings} onSave={saveDeviceSettings} /> : null}
      {activeTab === "notifications" && isAdmin ? (
        <NotificationSettings
          notifications={notifications}
          setNotifications={setNotifications}
          onSave={saveNotifications}
          onTest={(notification) => props.testNotification(notification.provider, notification.config).then(() => setMessage("Notification test sent."))}
        />
      ) : null}
      {activeTab === "keypad" && canOperate ? (
        <KeypadSettings
          buttons={customButtons}
          onAdd={addCustomButton}
          onReplaceCommand={replaceCustomButtonCommand}
          onUpdate={(button, payload) => props.updateCustomButton(button.id, payload).then((next) => setCustomButtons((current) => current.map((item) => (item.id === next.id ? next : item))))}
          onDelete={(button) => props.deleteCustomButton(button.id).then(() => setCustomButtons((current) => current.filter((item) => item.id !== button.id)))}
        />
      ) : null}
      {activeTab === "users" && isAdmin ? <UsersSettings users={users} setUsers={setUsers} onAdd={addUser} updateUser={props.updateUser} deleteUser={props.deleteUser} /> : null}
      {activeTab === "account" ? <AccountSettings authenticated={Boolean(auth?.authenticated)} onChangePassword={changePassword} /> : null}
      {activeTab === "tokens" && isAdmin ? <TokenSettings tokens={apiTokens} oneTimeToken={oneTimeToken} onCreate={createToken} onDelete={(token) => props.deleteApiToken(token.id).then(() => setApiTokens((current) => current.filter((item) => item.id !== token.id)))} /> : null}
      {activeTab === "import" && isAdmin ? <ImportExportSettings importText={importText} setImportText={setImportText} onExport={exportConfig} onImport={importConfig} /> : null}
      {activeTab === "advanced" && isAdmin ? <AdvancedSettings auditEntries={auditEntries} config={config} settings={settings} /> : null}
    </section>
  );
}

function Overview({ config }: { config: EffectiveConfig | null }) {
  return (
    <div className="settings-overview">
      <Capability title="Notifications" body="Configure alarm, fire, panic, arm/disarm, trouble, and connection notifications." />
      <Capability title="Zones" body="Name zones so logs and notifications use human-readable labels." />
      <Capability title="Keypad Settings" body="Manage custom keypad buttons and safety confirmations." />
      <Capability title="Users" body="Create users, assign viewer/operator/admin roles, and disable access." />
      <Capability title="Password" body="Change your local account password." />
      <Capability title="Advanced" body="Review diagnostics, effective configuration, audit history, and import/export settings." />
      <dl className="state-list">
        <div><dt>Adapter</dt><dd>{config?.adapter ?? "unknown"}</dd></div>
        <div><dt>Commands</dt><dd>{config?.allow_commands && !config?.read_only ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Read-only</dt><dd>{config?.read_only ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Panel mode</dt><dd>{config?.panel_type ?? "ADEMCO"}</dd></div>
      </dl>
    </div>
  );
}

function Capability({ title, body }: { title: string; body: string }) {
  return (
    <article className="capability-item">
      <strong>{title}</strong>
      <span>{body}</span>
    </article>
  );
}

function DeviceSettings({ config, settings, setSettings, onSave }: { config: EffectiveConfig | null; settings: SettingItem[]; setSettings: Dispatch<SetStateAction<SettingItem[]>>; onSave: () => void }) {
  return (
    <div className="admin-section">
      <h3>Device Setup</h3>
      <div className="form-grid">
        <label>Device type<input value={settingValue(settings, "adapter", config?.adapter ?? "fake")} onChange={(event) => setSetting(setSettings, "adapter", event.target.value)} /></label>
        <label>Panel mode<input value={settingValue(settings, "panel_type", config?.panel_type ?? "ADEMCO")} onChange={(event) => setSetting(setSettings, "panel_type", event.target.value.toUpperCase())} /></label>
        <label>Network host<input value={settingValue(settings, "ser2sock_host", config?.ser2sock_host ?? "alarmdecoder.local")} onChange={(event) => setSetting(setSettings, "ser2sock_host", event.target.value)} /></label>
        <label>Network port<input value={settingValue(settings, "ser2sock_port", String(config?.ser2sock_port ?? 10000))} onChange={(event) => setSetting(setSettings, "ser2sock_port", event.target.value)} /></label>
        <label>TLS<input value={settingValue(settings, "ser2sock_tls", String(config?.ser2sock_tls ?? false))} onChange={(event) => setSetting(setSettings, "ser2sock_tls", event.target.value)} /></label>
        <label>Serial path<input value={settingValue(settings, "serial_path", config?.serial_path ?? "/dev/ttyUSB0")} onChange={(event) => setSetting(setSettings, "serial_path", event.target.value)} /></label>
        <label>Serial baud<input value={settingValue(settings, "serial_baudrate", String(config?.serial_baudrate ?? 115200))} onChange={(event) => setSetting(setSettings, "serial_baudrate", event.target.value)} /></label>
        <label>Raw retention days<input value={settingValue(settings, "raw_retention_days", String(config?.raw_retention_days ?? 14))} onChange={(event) => setSetting(setSettings, "raw_retention_days", event.target.value)} /></label>
        <label>Event retention days<input value={settingValue(settings, "event_retention_days", String(config?.event_retention_days ?? 90))} onChange={(event) => setSetting(setSettings, "event_retention_days", event.target.value)} /></label>
      </div>
      <button type="button" onClick={onSave}>Save device settings</button>
    </div>
  );
}

function NotificationSettings({ notifications, setNotifications, onSave, onTest }: { notifications: NotificationConfig[]; setNotifications: Dispatch<SetStateAction<NotificationConfig[]>>; onSave: () => void; onTest: (notification: NotificationConfig) => Promise<void> }) {
  return (
    <div className="admin-section">
      <h3>Notifications</h3>
      {notifications.map((notification, index) => (
        <div className="notification-editor" key={notification.id ?? index}>
          <label><input type="checkbox" checked={notification.enabled} onChange={(event) => setNotifications((current) => replaceAt(current, index, { ...notification, enabled: event.target.checked }))} /> Enabled</label>
          <label>Provider<select value={notification.provider} onChange={(event) => setNotifications((current) => replaceAt(current, index, { ...notification, provider: event.target.value as NotificationConfig["provider"] }))}><option value="webhook">webhook</option><option value="smtp">smtp</option><option value="test">test</option></select></label>
          <label>Webhook URL<input value={String(notification.config.url ?? "")} onChange={(event) => setNotifications((current) => replaceAt(current, index, { ...notification, config: { ...notification.config, url: event.target.value } }))} /></label>
          <label>Event types<input value={Array.isArray(notification.config.event_types) ? notification.config.event_types.join(", ") : ""} onChange={(event) => setNotifications((current) => replaceAt(current, index, { ...notification, config: { ...notification.config, event_types: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) } }))} /></label>
          <div className="button-row"><button type="button" onClick={() => void onTest(notification)}>Send test</button></div>
        </div>
      ))}
      <div className="button-row">
        <button type="button" onClick={() => setNotifications((current) => [...current, emptyWebhookNotification()])}>New notification</button>
        <button type="button" onClick={onSave}>Save notifications</button>
      </div>
    </div>
  );
}

function KeypadSettings({ buttons, onAdd, onReplaceCommand, onUpdate, onDelete }: { buttons: CustomButton[]; onAdd: () => void; onReplaceCommand: (button: CustomButton) => void; onUpdate: (button: CustomButton, payload: Partial<{ label: string; command: string; dangerous: boolean; enabled: boolean; sort_order: number }>) => Promise<unknown>; onDelete: (button: CustomButton) => Promise<unknown> }) {
  return (
    <div className="admin-section">
      <h3>Custom Keypad Buttons</h3>
      <button type="button" onClick={onAdd}>New button</button>
      <div className="admin-list">
        {buttons.map((button) => (
          <article key={button.id}>
            <input value={button.label} onChange={(event) => void onUpdate(button, { label: event.target.value })} />
            <label><input type="checkbox" checked={button.enabled} onChange={(event) => void onUpdate(button, { enabled: event.target.checked })} /> Enabled</label>
            <label><input type="checkbox" checked={button.dangerous} onChange={(event) => void onUpdate(button, { dangerous: event.target.checked })} /> Confirm</label>
            <button type="button" onClick={() => onReplaceCommand(button)}>Replace command</button>
            <button type="button" onClick={() => void onDelete(button)}>Delete</button>
          </article>
        ))}
      </div>
    </div>
  );
}

function UsersSettings({ users, setUsers, onAdd, updateUser, deleteUser }: { users: User[]; setUsers: Dispatch<SetStateAction<User[]>>; onAdd: () => void; updateUser: SettingsPanelProps["updateUser"]; deleteUser: SettingsPanelProps["deleteUser"] }) {
  return (
    <div className="admin-section">
      <h3>Users</h3>
      <button type="button" onClick={onAdd}>Add user</button>
      <div className="admin-list">
        {users.map((user) => (
          <article key={user.username}>
            <strong>{user.username}</strong>
            <select value={user.role} onChange={(event) => void updateUser(user.username, { role: event.target.value as User["role"] }).then((next) => setUsers((current) => current.map((item) => item.username === next.username ? next : item)))}>
              <option value="viewer">viewer</option>
              <option value="operator">operator</option>
              <option value="admin">admin</option>
            </select>
            <button type="button" onClick={() => void updateUser(user.username, { disabled: !user.disabled }).then((next) => setUsers((current) => current.map((item) => item.username === next.username ? next : item)))}>
              {user.disabled ? "Enable" : "Disable"}
            </button>
            <button type="button" onClick={() => void deleteUser(user.username).then(() => setUsers((current) => current.filter((item) => item.username !== user.username)))}>
              Delete
            </button>
          </article>
        ))}
      </div>
    </div>
  );
}

function AccountSettings({ authenticated, onChangePassword }: { authenticated: boolean; onChangePassword: () => void }) {
  return (
    <div className="admin-section">
      <h3>Password</h3>
      {authenticated ? <button type="button" onClick={onChangePassword}>Change password</button> : <p className="read-only-note">Sign in to change your password.</p>}
    </div>
  );
}

function TokenSettings({ tokens, oneTimeToken, onCreate, onDelete }: { tokens: ApiToken[]; oneTimeToken: string | null; onCreate: () => void; onDelete: (token: ApiToken) => Promise<unknown> }) {
  return (
    <div className="admin-section">
      <h3>API Keys</h3>
      <button type="button" onClick={onCreate}>Create token</button>
      {oneTimeToken ? <code className="one-time-token">{oneTimeToken}</code> : null}
      <div className="admin-list">
        {tokens.map((token) => (
          <article key={token.id}>
            <strong>{token.name}</strong>
            <span>{token.username}</span>
            <span>{token.role}</span>
            <code>{token.token_prefix}...</code>
            <button type="button" onClick={() => void onDelete(token)}>Revoke</button>
          </article>
        ))}
      </div>
    </div>
  );
}

function ImportExportSettings({ importText, setImportText, onExport, onImport }: { importText: string; setImportText: (value: string) => void; onExport: () => void; onImport: (dryRun: boolean) => void }) {
  return (
    <div className="admin-section">
      <h3>Export / Import</h3>
      <div className="button-row">
        <button type="button" onClick={onExport}>Export settings</button>
        <button type="button" onClick={() => onImport(true)}>Dry run import</button>
        <button type="button" onClick={() => onImport(false)}>Apply import</button>
      </div>
      <textarea className="settings-json" value={importText} onChange={(event) => setImportText(event.target.value)} placeholder="Paste exported settings JSON here" />
    </div>
  );
}

function AdvancedSettings({ auditEntries, config, settings }: { auditEntries: AuditEntry[]; config: EffectiveConfig | null; settings: SettingItem[] }) {
  return (
    <div className="admin-section">
      <h3>Advanced / Diagnostics</h3>
      <details open><summary>Effective config</summary><pre>{JSON.stringify(config, null, 2)}</pre></details>
      <details><summary>Persisted settings</summary><pre>{JSON.stringify(settings, null, 2)}</pre></details>
      <h3>Audit History</h3>
      <div className="compact-event-list">
        {auditEntries.map((entry) => (
          <article key={entry.id}>
            <time>{new Date(entry.timestamp).toLocaleString()}</time>
            <strong>{entry.action.replaceAll("_", " ")}</strong>
            <span>{entry.actor}</span>
          </article>
        ))}
      </div>
    </div>
  );
}

function emptyWebhookNotification(): NotificationConfig {
  return { id: null, provider: "webhook", enabled: false, config: { url: "", event_types: [] } };
}

function settingValue(settings: SettingItem[], key: string, fallback: string) {
  return settings.find((setting) => setting.key === key)?.value ?? fallback;
}

function fallbackSetting(config: EffectiveConfig | null, key: string) {
  if (!config) return "";
  const value = config[key as keyof EffectiveConfig];
  return String(value ?? "");
}

function setSetting(setSettings: Dispatch<SetStateAction<SettingItem[]>>, key: string, value: string) {
  setSettings((current) => {
    const existing = current.find((setting) => setting.key === key);
    if (existing) {
      return current.map((setting) => setting.key === key ? { key, value } : setting);
    }
    return [...current, { key, value }];
  });
}

function replaceAt<T>(items: T[], index: number, next: T): T[] {
  return items.map((item, itemIndex) => itemIndex === index ? next : item);
}

function sortButtons(a: CustomButton, b: CustomButton) {
  return a.sort_order - b.sort_order || a.label.localeCompare(b.label);
}
