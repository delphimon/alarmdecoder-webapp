import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { Modal } from "./Dialog";
import type {
  ApiToken,
  ApiTokenCreateResponse,
  AuditEntry,
  AuthStatus,
  CustomButton,
  EffectiveConfig,
  NotificationConfig,
  Passkey,
  PinStatus,
  SettingItem,
  User,
} from "../types";

type SettingsTab = "overview" | "device" | "notifications" | "keypad" | "users" | "account" | "tokens" | "import" | "advanced";

export type SettingsPanelProps = {
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
  getPinStatus?: () => Promise<PinStatus>;
  savePin?: (pin: string) => Promise<PinStatus>;
  loadPasskeys?: () => Promise<Passkey[]>;
  deletePasskey?: (id: string) => Promise<{ status: string }>;
  registerPasskey?: (name: string) => Promise<Passkey>;
  refreshConfig?: () => Promise<void>;
};

const tabs: Array<{ id: SettingsTab; label: string }> = [
  { id: "overview", label: "Settings" },
  { id: "device", label: "Device" },
  { id: "notifications", label: "Notifications" },
  { id: "keypad", label: "Keypad Settings" },
  { id: "users", label: "Users" },
  { id: "account", label: "Account & Passkeys" },
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
  const [passkeys, setPasskeys] = useState<Passkey[]>([]);
  const [pinStatus, setPinStatus] = useState<PinStatus | null>(null);
  const [oneTimeToken, setOneTimeToken] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  // Modal dialog states
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [buttonModalOpen, setButtonModalOpen] = useState(false);
  const [replaceCmdModalOpen, setReplaceCmdModalOpen] = useState(false);
  const [targetButton, setTargetButton] = useState<CustomButton | null>(null);
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [passkeyModalOpen, setPasskeyModalOpen] = useState(false);

  // Form input states
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState<User["role"]>("viewer");
  const [newButtonLabel, setNewButtonLabel] = useState("");
  const [newButtonCommand, setNewButtonCommand] = useState("");
  const [newButtonDangerous, setNewButtonDangerous] = useState(false);
  const [replacementCommand, setReplacementCommand] = useState("");
  const [newTokenName, setNewTokenName] = useState("");
  const [newTokenRole, setNewTokenRole] = useState<User["role"]>("viewer");
  const [panelPin, setPanelPin] = useState("");
  const [panelPinConfirm, setPanelPinConfirm] = useState("");
  const [newPasskeyName, setNewPasskeyName] = useState("My Device");
  const [modalError, setModalError] = useState<string | null>(null);

  const isAdmin = auth?.user?.role === "admin";
  const canOperate = auth?.user?.role === "admin" || auth?.user?.role === "operator";

  useEffect(() => {
    if (!isAdmin) return;
    props.loadSettings().then(setSettings).catch(() => {});
    props.loadUsers().then(setUsers).catch(() => {});
    props.loadNotifications().then(setNotifications).catch(() => {});
    props.loadApiTokens().then(setApiTokens).catch(() => {});
    props.loadAudit().then(setAuditEntries).catch(() => {});
    if (props.getPinStatus) props.getPinStatus().then(setPinStatus).catch(() => {});
  }, [isAdmin]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (canOperate) props.loadCustomButtons().then(setCustomButtons).catch(() => {});
  }, [canOperate]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (auth?.authenticated && props.loadPasskeys) {
      props.loadPasskeys().then(setPasskeys).catch(() => {});
    }
  }, [auth?.authenticated]); // eslint-disable-line react-hooks/exhaustive-deps

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
    if (props.refreshConfig) {
      await props.refreshConfig();
    }
    setMessage("Device settings saved. Connecting to updated adapter configuration...");
  };

  const handleAddUser = async () => {
    if (!newUsername || !newPassword) {
      setModalError("Username and password are required.");
      return;
    }
    try {
      const created = await props.createUser({ username: newUsername, password: newPassword, role: newUserRole });
      setUsers((current) => [...current, created].sort((a, b) => a.username.localeCompare(b.username)));
      setUserModalOpen(false);
      setNewUsername("");
      setNewPassword("");
      setModalError(null);
      setMessage(`User ${created.username} created.`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to create user.");
    }
  };

  const handleAddButton = async () => {
    if (!newButtonLabel || !newButtonCommand) {
      setModalError("Label and command are required.");
      return;
    }
    try {
      const created = await props.createCustomButton({
        label: newButtonLabel,
        command: newButtonCommand,
        dangerous: newButtonDangerous,
      });
      setCustomButtons((current) => [...current, created].sort(sortButtons));
      setButtonModalOpen(false);
      setNewButtonLabel("");
      setNewButtonCommand("");
      setNewButtonDangerous(false);
      setModalError(null);
      setMessage(`Button "${created.label}" added.`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to create button.");
    }
  };

  const handleReplaceCommand = async () => {
    if (!targetButton || !replacementCommand) return;
    try {
      const next = await props.updateCustomButton(targetButton.id, { command: replacementCommand });
      setCustomButtons((current) => current.map((b) => (b.id === next.id ? next : b)));
      setReplaceCmdModalOpen(false);
      setReplacementCommand("");
      setTargetButton(null);
      setMessage(`Command replaced for "${next.label}".`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to update command.");
    }
  };

  const handleCreateToken = async () => {
    if (!newTokenName) {
      setModalError("Token name is required.");
      return;
    }
    try {
      const response = await props.createApiToken({
        username: auth?.user?.username ?? "",
        name: newTokenName,
        role: newTokenRole,
      });
      setApiTokens((current) => [response.record, ...current]);
      setOneTimeToken(response.token);
      setTokenModalOpen(false);
      setNewTokenName("");
      setModalError(null);
      setMessage("API token created. Copy it now; it will not be shown again.");
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to create token.");
    }
  };

  const handleSavePin = async () => {
    if (panelPin !== panelPinConfirm) {
      setModalError("PINs do not match.");
      return;
    }
    if (panelPin.length < 4) {
      setModalError("PIN must be at least 4 digits.");
      return;
    }
    if (!props.savePin) return;
    try {
      const res = await props.savePin(panelPin);
      setPinStatus(res);
      setPinModalOpen(false);
      setPanelPin("");
      setPanelPinConfirm("");
      setModalError(null);
      setMessage("Panel PIN saved and encrypted.");
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to save PIN.");
    }
  };

  const handleRegisterPasskey = async () => {
    if (!props.registerPasskey) return;
    setModalError(null);
    try {
      const passkey = await props.registerPasskey(newPasskeyName || "Device");
      setPasskeys((curr) => [passkey, ...curr]);
      setPasskeyModalOpen(false);
      setNewPasskeyName("My Device");
      setMessage(`Passkey "${passkey.name}" registered successfully.`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Passkey registration failed or cancelled.");
    }
  };

  return (
    <section className="summary-panel settings-shell" aria-label="Settings">
      <div className="section-heading">
        <h2>Settings</h2>
        <span>Role: {auth?.user?.role ?? "viewer"}</span>
      </div>

      <nav className="settings-tabs" aria-label="Settings sections">
        {tabs.map((tab) => (
          <button key={tab.id} type="button" className={activeTab === tab.id ? "active" : ""} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </nav>

      {message ? <p className="status-message" role="status">{message}</p> : null}
      {!isAdmin && activeTab !== "account" && activeTab !== "keypad" ? (
        <p className="read-only-note">Admin role required for this settings section.</p>
      ) : null}

      {/* ── Tabs ── */}
      {activeTab === "overview" ? <Overview config={config} /> : null}

      {activeTab === "device" && isAdmin ? (
        <DeviceSettings
          config={config}
          settings={settings}
          setSettings={setSettings}
          pinStatus={pinStatus}
          onOpenPinModal={() => { setModalError(null); setPinModalOpen(true); }}
          onSave={saveDeviceSettings}
        />
      ) : null}

      {activeTab === "notifications" && isAdmin ? (
        <NotificationSettings
          notifications={notifications}
          setNotifications={setNotifications}
          onSave={() => props.saveNotifications(notifications).then((next) => { setNotifications(next); setMessage("Notifications saved."); })}
          onTest={(n) => props.testNotification(n.provider, n.config).then(() => setMessage("Test notification sent."))}
        />
      ) : null}

      {activeTab === "keypad" && canOperate ? (
        <KeypadSettings
          buttons={customButtons}
          onAdd={() => { setModalError(null); setButtonModalOpen(true); }}
          onReplaceCommand={(btn) => { setTargetButton(btn); setReplacementCommand(""); setModalError(null); setReplaceCmdModalOpen(true); }}
          onUpdate={(btn, payload) => props.updateCustomButton(btn.id, payload).then((next) => setCustomButtons((curr) => curr.map((b) => (b.id === next.id ? next : b))))}
          onDelete={(btn) => props.deleteCustomButton(btn.id).then(() => setCustomButtons((curr) => curr.filter((b) => b.id !== btn.id)))}
        />
      ) : null}

      {activeTab === "users" && isAdmin ? (
        <UsersSettings
          users={users}
          setUsers={setUsers}
          onAdd={() => { setModalError(null); setUserModalOpen(true); }}
          updateUser={props.updateUser}
          deleteUser={props.deleteUser}
        />
      ) : null}

      {activeTab === "account" ? (
        <AccountSettings
          authenticated={Boolean(auth?.authenticated)}
          passkeys={passkeys}
          onChangePassword={props.changePassword}
          onOpenPasskeyModal={() => { setModalError(null); setPasskeyModalOpen(true); }}
          onDeletePasskey={async (id) => {
            if (!props.deletePasskey) return;
            await props.deletePasskey(id);
            setPasskeys((curr) => curr.filter((p) => p.id !== id));
            setMessage("Passkey removed.");
          }}
          onMessage={setMessage}
        />
      ) : null}

      {activeTab === "tokens" && isAdmin ? (
        <TokenSettings
          tokens={apiTokens}
          oneTimeToken={oneTimeToken}
          onCreate={() => { setModalError(null); setTokenModalOpen(true); }}
          onDelete={(token) => props.deleteApiToken(token.id).then(() => setApiTokens((curr) => curr.filter((t) => t.id !== token.id)))}
        />
      ) : null}

      {activeTab === "import" && isAdmin ? (
        <ImportExportSettings
          importText={importText}
          setImportText={setImportText}
          onExport={async () => {
            const data = await props.exportSettings();
            setImportText(JSON.stringify(data, null, 2));
            setMessage("Export generated below.");
          }}
          onImport={async (dryRun) => {
            try {
              const parsed = JSON.parse(importText) as Record<string, unknown>;
              const result = await props.importSettings(parsed, dryRun);
              setMessage(JSON.stringify(result));
              if (!dryRun) {
                setSettings(await props.loadSettings());
                setNotifications(await props.loadNotifications());
              }
            } catch (err) {
              setMessage(err instanceof Error ? err.message : "Invalid JSON");
            }
          }}
        />
      ) : null}

      {activeTab === "advanced" && isAdmin ? (
        <AdvancedSettings auditEntries={auditEntries} config={config} settings={settings} />
      ) : null}

      {/* ── Native Modal Dialogs ── */}
      <Modal open={userModalOpen} title="Add User" onClose={() => setUserModalOpen(false)}>
        <label>Username<input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} autoFocus /></label>
        <label>Password<input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></label>
        <label>Role
          <select value={newUserRole} onChange={(e) => setNewUserRole(e.target.value as User["role"])}>
            <option value="viewer">viewer</option>
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
        </label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setUserModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleAddUser}>Create User</button>
        </div>
      </Modal>

      <Modal open={buttonModalOpen} title="New Custom Button" onClose={() => setButtonModalOpen(false)}>
        <label>Button label<input value={newButtonLabel} onChange={(e) => setNewButtonLabel(e.target.value)} autoFocus placeholder="e.g. Disarm House" /></label>
        <label>Command sequence<input value={newButtonCommand} onChange={(e) => setNewButtonCommand(e.target.value)} placeholder="e.g. DISARM or 12341" /></label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={newButtonDangerous} onChange={(e) => setNewButtonDangerous(e.target.checked)} />
          Require confirmation before sending
        </label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setButtonModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleAddButton}>Add Button</button>
        </div>
      </Modal>

      <Modal open={replaceCmdModalOpen} title={`Replace Command — ${targetButton?.label ?? ""}`} onClose={() => setReplaceCmdModalOpen(false)}>
        <label>New command sequence<input value={replacementCommand} onChange={(e) => setReplacementCommand(e.target.value)} autoFocus /></label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setReplaceCmdModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleReplaceCommand}>Save Command</button>
        </div>
      </Modal>

      <Modal open={tokenModalOpen} title="Create API Token" onClose={() => setTokenModalOpen(false)}>
        <label>Token Name<input value={newTokenName} onChange={(e) => setNewTokenName(e.target.value)} autoFocus placeholder="e.g. Home Assistant" /></label>
        <label>Role
          <select value={newTokenRole} onChange={(e) => setNewTokenRole(e.target.value as User["role"])}>
            <option value="viewer">viewer</option>
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
        </label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setTokenModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleCreateToken}>Create Token</button>
        </div>
      </Modal>

      <Modal open={pinModalOpen} title="Configure Panel PIN" onClose={() => setPinModalOpen(false)}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
          The panel PIN is stored encrypted and synthesized for ARM/DISARM commands sent to real hardware.
        </p>
        <label>Panel PIN<input type="password" value={panelPin} onChange={(e) => setPanelPin(e.target.value)} autoFocus maxLength={8} /></label>
        <label>Confirm PIN<input type="password" value={panelPinConfirm} onChange={(e) => setPanelPinConfirm(e.target.value)} maxLength={8} /></label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setPinModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleSavePin}>Save PIN</button>
        </div>
      </Modal>

      <Modal open={passkeyModalOpen} title="Register Passkey" onClose={() => setPasskeyModalOpen(false)}>
        <label>Passkey Name<input value={newPasskeyName} onChange={(e) => setNewPasskeyName(e.target.value)} autoFocus placeholder="e.g. iPhone, Work MacBook" /></label>
        {modalError ? <p className="modal-error">{modalError}</p> : null}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => setPasskeyModalOpen(false)}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleRegisterPasskey}>Register</button>
        </div>
      </Modal>
    </section>
  );
}

// ── Subcomponents ────────────────────────────────────────────────────────────

function Overview({ config }: { config: EffectiveConfig | null }) {
  return (
    <div className="settings-overview">
      <div className="capability-item">
        <strong>Hardware Security</strong>
        <span>Non-fake adapters default to read-only. Commands require explicit approval and PIN synthesis.</span>
      </div>
      <dl className="state-list">
        <div><dt>Adapter</dt><dd>{config?.adapter ?? "unknown"}</dd></div>
        <div><dt>Commands</dt><dd>{config?.allow_commands && !config?.read_only ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Read-only</dt><dd>{config?.read_only ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Panel mode</dt><dd>{config?.panel_type ?? "ADEMCO"}</dd></div>
      </dl>
    </div>
  );
}

function DeviceSettings({
  config,
  settings,
  setSettings,
  pinStatus,
  onOpenPinModal,
  onSave,
}: {
  config: EffectiveConfig | null;
  settings: SettingItem[];
  setSettings: Dispatch<SetStateAction<SettingItem[]>>;
  pinStatus: PinStatus | null;
  onOpenPinModal: () => void;
  onSave: () => void;
}) {
  const currentAdapter = settingValue(settings, "adapter", config?.adapter ?? "fake");
  const currentPanel = settingValue(settings, "panel_type", config?.panel_type ?? "ADEMCO");
  const currentBaud = settingValue(settings, "serial_baudrate", String(config?.serial_baudrate ?? 115200));
  const isTls = settingValue(settings, "ser2sock_tls", String(config?.ser2sock_tls ?? false)) === "true";

  return (
    <div className="admin-section">
      <h3>Device Setup</h3>
      <div className="form-grid">
        <label>
          Adapter Type
          <select value={currentAdapter} onChange={(e) => setSetting(setSettings, "adapter", e.target.value)}>
            <option value="fake">fake (Simulator)</option>
            <option value="ser2sock">ser2sock (Network TCP)</option>
            <option value="serial">serial (USB / Serial Port)</option>
            <option value="ad2usb">ad2usb (AD2USB)</option>
            <option value="ad2pi">ad2pi (AD2PI Hat)</option>
            <option value="ad2serial">ad2serial (AD2SERIAL)</option>
          </select>
        </label>
        <label>
          Panel Protocol
          <select value={currentPanel} onChange={(e) => setSetting(setSettings, "panel_type", e.target.value)}>
            <option value="ADEMCO">ADEMCO (Honeywell / Resideo Vista)</option>
            <option value="DSC">DSC (PowerSeries)</option>
          </select>
        </label>
        <label>Network host<input value={settingValue(settings, "ser2sock_host", config?.ser2sock_host ?? "alarmdecoder.local")} onChange={(e) => setSetting(setSettings, "ser2sock_host", e.target.value)} /></label>
        <label>Network port<input value={settingValue(settings, "ser2sock_port", String(config?.ser2sock_port ?? 10000))} onChange={(e) => setSetting(setSettings, "ser2sock_port", e.target.value)} /></label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 18 }}>
          <input type="checkbox" checked={isTls} onChange={(e) => setSetting(setSettings, "ser2sock_tls", String(e.target.checked))} />
          Enable TLS on ser2sock
        </label>
        <label>Serial device path<input value={settingValue(settings, "serial_path", config?.serial_path ?? "/dev/ttyUSB0")} onChange={(e) => setSetting(setSettings, "serial_path", e.target.value)} /></label>
        <label>
          Serial baud rate
          <select value={currentBaud} onChange={(e) => setSetting(setSettings, "serial_baudrate", e.target.value)}>
            <option value="9600">9600</option>
            <option value="19200">19200</option>
            <option value="38400">38400</option>
            <option value="57600">57600</option>
            <option value="115200">115200</option>
          </select>
        </label>
        <label>Raw retention days<input value={settingValue(settings, "raw_retention_days", String(config?.raw_retention_days ?? 14))} onChange={(e) => setSetting(setSettings, "raw_retention_days", e.target.value)} /></label>
        <label>Event retention days<input value={settingValue(settings, "event_retention_days", String(config?.event_retention_days ?? 90))} onChange={(e) => setSetting(setSettings, "event_retention_days", e.target.value)} /></label>
      </div>

      <div style={{ marginTop: 14, padding: 12, border: "1px solid var(--color-border-subtle)", borderRadius: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <strong>Panel PIN (Hardware Keystroke Synthesis)</strong>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--color-text-muted)" }}>
              {pinStatus?.configured ? "✓ PIN is configured and encrypted." : "⚠️ No PIN configured. Real panel commands will be rejected."}
            </p>
          </div>
          <button type="button" onClick={onOpenPinModal}>
            {pinStatus?.configured ? "Change PIN" : "Configure PIN"}
          </button>
        </div>
      </div>

      <div className="button-row" style={{ marginTop: 12 }}>
        <button type="button" className="btn-primary" onClick={onSave}>Save Device Settings</button>
      </div>
    </div>
  );
}

function NotificationSettings({
  notifications,
  setNotifications,
  onSave,
  onTest,
}: {
  notifications: NotificationConfig[];
  setNotifications: Dispatch<SetStateAction<NotificationConfig[]>>;
  onSave: () => void;
  onTest: (notification: NotificationConfig) => Promise<void>;
}) {
  return (
    <div className="admin-section">
      <h3>Notifications</h3>
      {notifications.map((notification, index) => {
        const isWebhook = notification.provider === "webhook";
        const isSmtp = notification.provider === "smtp";

        return (
          <div className="notification-editor" key={notification.id ?? index}>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={notification.enabled}
                onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, enabled: e.target.checked }))}
              />
              Enabled
            </label>
            <label>
              Provider
              <select
                value={notification.provider}
                onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, provider: e.target.value as NotificationConfig["provider"] }))}
              >
                <option value="webhook">webhook</option>
                <option value="smtp">smtp</option>
                <option value="test">test</option>
              </select>
            </label>

            {isWebhook ? (
              <label>
                Webhook URL
                <input
                  value={String(notification.config.url ?? "")}
                  placeholder="https://example.com/webhook"
                  onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, url: e.target.value } }))}
                />
              </label>
            ) : null}

            {isSmtp ? (
              <div className="form-grid">
                <label>
                  SMTP Host
                  <input
                    value={String(notification.config.host ?? "")}
                    placeholder="smtp.example.com"
                    onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, host: e.target.value } }))}
                  />
                </label>
                <label>
                  Port
                  <input
                    value={String(notification.config.port ?? 587)}
                    placeholder="587"
                    onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, port: e.target.value } }))}
                  />
                </label>
                <label>
                  Sender (From)
                  <input
                    value={String(notification.config.sender ?? "")}
                    placeholder="alarm@example.com"
                    onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, sender: e.target.value } }))}
                  />
                </label>
                <label>
                  Recipient (To)
                  <input
                    value={String(notification.config.recipient ?? "")}
                    placeholder="you@example.com"
                    onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, recipient: e.target.value } }))}
                  />
                </label>
              </div>
            ) : null}

            <label>
              Event types (comma-separated: alarm, fire, panic, arm, disarm, zone_fault, trouble)
              <input
                value={Array.isArray(notification.config.event_types) ? notification.config.event_types.join(", ") : ""}
                placeholder="alarm, fire, panic, arm, disarm"
                onChange={(e) => setNotifications((curr) => replaceAt(curr, index, { ...notification, config: { ...notification.config, event_types: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } }))}
              />
            </label>

            <div className="button-row">
              <button type="button" onClick={() => void onTest(notification)}>Send Test Notification</button>
            </div>
          </div>
        );
      })}

      <div className="button-row" style={{ marginTop: 12 }}>
        <button type="button" onClick={() => setNotifications((curr) => [...curr, emptyWebhookNotification()])}>+ Add Notification</button>
        <button type="button" className="btn-primary" onClick={onSave}>Save Notifications</button>
      </div>
    </div>
  );
}

function KeypadSettings({
  buttons,
  onAdd,
  onReplaceCommand,
  onUpdate,
  onDelete,
}: {
  buttons: CustomButton[];
  onAdd: () => void;
  onReplaceCommand: (button: CustomButton) => void;
  onUpdate: (button: CustomButton, payload: Partial<CustomButton>) => Promise<unknown>;
  onDelete: (button: CustomButton) => Promise<unknown>;
}) {
  return (
    <div className="admin-section">
      <h3>Custom Keypad Buttons</h3>
      <button type="button" onClick={onAdd}>+ Add Custom Button</button>
      <div className="admin-list" style={{ marginTop: 10 }}>
        {buttons.map((button) => (
          <article key={button.id}>
            <input value={button.label} onChange={(e) => void onUpdate(button, { label: e.target.value })} />
            <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={button.enabled} onChange={(e) => void onUpdate(button, { enabled: e.target.checked })} />
              Enabled
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={button.dangerous} onChange={(e) => void onUpdate(button, { dangerous: e.target.checked })} />
              Confirm
            </label>
            <button type="button" onClick={() => onReplaceCommand(button)}>Edit Command</button>
            <button type="button" onClick={() => void onDelete(button)}>Delete</button>
          </article>
        ))}
      </div>
    </div>
  );
}

function UsersSettings({
  users,
  setUsers,
  onAdd,
  updateUser,
  deleteUser,
}: {
  users: User[];
  setUsers: Dispatch<SetStateAction<User[]>>;
  onAdd: () => void;
  updateUser: SettingsPanelProps["updateUser"];
  deleteUser: SettingsPanelProps["deleteUser"];
}) {
  return (
    <div className="admin-section">
      <h3>Users</h3>
      <button type="button" onClick={onAdd}>+ Add User</button>
      <div className="admin-list" style={{ marginTop: 10 }}>
        {users.map((user) => (
          <article key={user.username}>
            <strong>{user.username}</strong>
            <select
              value={user.role}
              onChange={(e) => void updateUser(user.username, { role: e.target.value as User["role"] }).then((next) => setUsers((curr) => curr.map((u) => (u.username === next.username ? next : u))))}
            >
              <option value="viewer">viewer</option>
              <option value="operator">operator</option>
              <option value="admin">admin</option>
            </select>
            <button
              type="button"
              onClick={() => void updateUser(user.username, { disabled: !user.disabled }).then((next) => setUsers((curr) => curr.map((u) => (u.username === next.username ? next : u))))}
            >
              {user.disabled ? "Enable" : "Disable"}
            </button>
            <button type="button" onClick={() => void deleteUser(user.username).then(() => setUsers((curr) => curr.filter((u) => u.username !== user.username)))}>
              Delete
            </button>
          </article>
        ))}
      </div>
    </div>
  );
}

function AccountSettings({
  authenticated,
  passkeys,
  onChangePassword,
  onOpenPasskeyModal,
  onDeletePasskey,
  onMessage,
}: {
  authenticated: boolean;
  passkeys: Passkey[];
  onChangePassword: (payload: { current_password: string; new_password: string }) => Promise<{ status: string }>;
  onOpenPasskeyModal: () => void;
  onDeletePasskey: (id: string) => Promise<void>;
  onMessage: (msg: string) => void;
}) {
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);

  const handleSubmitPassword = async () => {
    setPwError(null);
    if (!currentPw || !newPw) {
      setPwError("Both fields required.");
      return;
    }
    if (newPw.length < 8) {
      setPwError("New password must be at least 8 characters.");
      return;
    }
    try {
      await onChangePassword({ current_password: currentPw, new_password: newPw });
      setCurrentPw("");
      setNewPw("");
      onMessage("Password changed successfully.");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Password change failed.");
    }
  };

  if (!authenticated) {
    return <p className="read-only-note">Sign in to manage your account and passkeys.</p>;
  }

  return (
    <div className="admin-section">
      <h3>Change Password</h3>
      <div style={{ display: "grid", gap: 10, maxWidth: 360 }}>
        <label>Current Password<input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} /></label>
        <label>New Password (min 8 chars)<input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} /></label>
        {pwError ? <p className="modal-error">{pwError}</p> : null}
        <button type="button" onClick={handleSubmitPassword}>Update Password</button>
      </div>

      <h3 style={{ marginTop: 20 }}>🔑 Passkeys</h3>
      <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
        Use Face ID, Touch ID, or security keys to sign in without typing your password.
      </p>
      <button type="button" onClick={onOpenPasskeyModal} style={{ width: "fit-content" }}>
        + Register New Passkey
      </button>
      <div className="admin-list" style={{ marginTop: 8 }}>
        {passkeys.length === 0 ? (
          <p className="empty-text">No passkeys registered yet.</p>
        ) : (
          passkeys.map((pk) => (
            <article key={pk.id}>
              <strong>{pk.name}</strong>
              <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{new Date(pk.created_at).toLocaleDateString()}</span>
              <button type="button" onClick={() => void onDeletePasskey(pk.id)}>Remove</button>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

function TokenSettings({
  tokens,
  oneTimeToken,
  onCreate,
  onDelete,
}: {
  tokens: ApiToken[];
  oneTimeToken: string | null;
  onCreate: () => void;
  onDelete: (token: ApiToken) => Promise<unknown>;
}) {
  return (
    <div className="admin-section">
      <h3>API Keys</h3>
      <button type="button" onClick={onCreate}>+ Create Token</button>
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

function ImportExportSettings({
  importText,
  setImportText,
  onExport,
  onImport,
}: {
  importText: string;
  setImportText: (v: string) => void;
  onExport: () => void;
  onImport: (dryRun: boolean) => void;
}) {
  return (
    <div className="admin-section">
      <h3>Export / Import</h3>
      <div className="button-row">
        <button type="button" onClick={onExport}>Export Settings</button>
        <button type="button" onClick={() => onImport(true)}>Dry Run Import</button>
        <button type="button" onClick={() => onImport(false)}>Apply Import</button>
      </div>
      <textarea className="settings-json" value={importText} onChange={(e) => setImportText(e.target.value)} placeholder="Paste exported JSON here" />
    </div>
  );
}

function AdvancedSettings({
  auditEntries,
  config,
  settings,
}: {
  auditEntries: AuditEntry[];
  config: EffectiveConfig | null;
  settings: SettingItem[];
}) {
  return (
    <div className="admin-section">
      <h3>Diagnostics & Config</h3>
      <details open><summary>Effective Config</summary><pre>{JSON.stringify(config, null, 2)}</pre></details>
      <details><summary>Persisted Settings</summary><pre>{JSON.stringify(settings, null, 2)}</pre></details>
      <h3>Audit Trail</h3>
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
      return current.map((setting) => (setting.key === key ? { key, value } : setting));
    }
    return [...current, { key, value }];
  });
}

function replaceAt<T>(items: T[], index: number, next: T): T[] {
  return items.map((item, itemIndex) => (itemIndex === index ? next : item));
}

function sortButtons(a: CustomButton, b: CustomButton) {
  return a.sort_order - b.sort_order || a.label.localeCompare(b.label);
}
