import { useCallback, useEffect, useState } from "react";
import type { CustomButton, PanelState } from "../types";

type KeypadProps = {
  state: PanelState;
  muted: boolean;
  disabled: boolean;
  disabledReason: string;
  flash: boolean;
  commandError?: string | null;
  onClearCommandError?: () => void;
  onMuteChange: (muted: boolean) => void;
  onCommand: (command: string, confirm?: boolean) => void;
  customButtons: CustomButton[];
  onLoadCustomButtons: () => void;
  onCreateCustomButton: () => void;
  onSendCustomButton: (id: number, confirm?: boolean) => void;
};

interface KeypadButtonDef {
  key: string;
  label: string;
  command: string;
  confirm?: boolean;
  isCircular?: boolean;
  normalImg: string;
  activeImg: string;
}

const ADEMCO_ROWS: KeypadButtonDef[][] = [
  [
    {
      key: "F1",
      label: "F1 Fire Emergency",
      command: "F1",
      confirm: true,
      isCircular: true,
      normalImg: "/img/f1-fire.png",
      activeImg: "/img/f1-fire-on.png",
    },
    {
      key: "1",
      label: "1 OFF",
      command: "1",
      normalImg: "/img/1-large.png",
      activeImg: "/img/1-large-on.png",
    },
    {
      key: "2",
      label: "2 AWAY",
      command: "2",
      normalImg: "/img/2-large.png",
      activeImg: "/img/2-large-on.png",
    },
    {
      key: "3",
      label: "3 STAY",
      command: "3",
      normalImg: "/img/3-large.png",
      activeImg: "/img/3-large-on.png",
    },
  ],
  [
    {
      key: "F2",
      label: "F2 Police Emergency",
      command: "F2",
      confirm: true,
      isCircular: true,
      normalImg: "/img/f2-police.png",
      activeImg: "/img/f2-police-on.png",
    },
    {
      key: "4",
      label: "4 MAX",
      command: "4",
      normalImg: "/img/4-large.png",
      activeImg: "/img/4-large-on.png",
    },
    {
      key: "5",
      label: "5 TEST",
      command: "5",
      normalImg: "/img/5-large.png",
      activeImg: "/img/5-large-on.png",
    },
    {
      key: "6",
      label: "6 BYPASS",
      command: "6",
      normalImg: "/img/6-large.png",
      activeImg: "/img/6-large-on.png",
    },
  ],
  [
    {
      key: "F3",
      label: "F3 Medical Emergency",
      command: "F3",
      confirm: true,
      isCircular: true,
      normalImg: "/img/f3-medical.png",
      activeImg: "/img/f3-medical-on.png",
    },
    {
      key: "7",
      label: "7 INSTANT",
      command: "7",
      normalImg: "/img/7-large.png",
      activeImg: "/img/7-large-on.png",
    },
    {
      key: "8",
      label: "8 CODE",
      command: "8",
      normalImg: "/img/8-large.png",
      activeImg: "/img/8-large-on.png",
    },
    {
      key: "9",
      label: "9 CHIME",
      command: "9",
      normalImg: "/img/9-large.png",
      activeImg: "/img/9-large-on.png",
    },
  ],
  [
    {
      key: "F4",
      label: "F4 Function",
      command: "F4",
      confirm: true,
      isCircular: true,
      normalImg: "/img/f4-led-text.png",
      activeImg: "/img/f4-led-text-on.png",
    },
    {
      key: "*",
      label: "* READY",
      command: "*",
      normalImg: "/img/star-large.png",
      activeImg: "/img/star-large-on.png",
    },
    {
      key: "0",
      label: "0",
      command: "0",
      normalImg: "/img/0-large.png",
      activeImg: "/img/0-large-on.png",
    },
    {
      key: "#",
      label: "#",
      command: "#",
      normalImg: "/img/pound-large.png",
      activeImg: "/img/pound-large-on.png",
    },
  ],
];

const DSC_ROWS: KeypadButtonDef[][] = [
  [
    {
      key: "STAY",
      label: "Arm Stay",
      command: "STAY",
      isCircular: true,
      normalImg: "/img/f1-fire.png",
      activeImg: "/img/f1-fire-on.png",
    },
    { key: "1", label: "1", command: "1", normalImg: "/img/dsc-1-large.png", activeImg: "/img/dsc-1-large-on.png" },
    { key: "2", label: "2", command: "2", normalImg: "/img/dsc-2-large.png", activeImg: "/img/dsc-2-large-on.png" },
    { key: "3", label: "3", command: "3", normalImg: "/img/dsc-3-large.png", activeImg: "/img/dsc-3-large-on.png" },
  ],
  [
    {
      key: "AWAY",
      label: "Arm Away",
      command: "AWAY",
      isCircular: true,
      normalImg: "/img/f2-police.png",
      activeImg: "/img/f2-police-on.png",
    },
    { key: "4", label: "4", command: "4", normalImg: "/img/dsc-4-large.png", activeImg: "/img/dsc-4-large-on.png" },
    { key: "5", label: "5", command: "5", normalImg: "/img/dsc-5-large.png", activeImg: "/img/dsc-5-large-on.png" },
    { key: "6", label: "6", command: "6", normalImg: "/img/dsc-6-large.png", activeImg: "/img/dsc-6-large-on.png" },
  ],
  [
    {
      key: "CHIME",
      label: "Chime Toggle",
      command: "CHIME",
      isCircular: true,
      normalImg: "/img/f3-medical.png",
      activeImg: "/img/f3-medical-on.png",
    },
    { key: "7", label: "7", command: "7", normalImg: "/img/dsc-7-large.png", activeImg: "/img/dsc-7-large-on.png" },
    { key: "8", label: "8", command: "8", normalImg: "/img/dsc-8-large.png", activeImg: "/img/dsc-8-large-on.png" },
    { key: "9", label: "9", command: "9", normalImg: "/img/dsc-9-large.png", activeImg: "/img/dsc-9-large-on.png" },
  ],
  [
    {
      key: "RESET",
      label: "Sensor Reset",
      command: "RESET",
      confirm: true,
      isCircular: true,
      normalImg: "/img/f4-led-text.png",
      activeImg: "/img/f4-led-text-on.png",
    },
    { key: "*", label: "*", command: "*", normalImg: "/img/dsc-star-large.png", activeImg: "/img/dsc-star-large-on.png" },
    { key: "0", label: "0", command: "0", normalImg: "/img/dsc-0-large.png", activeImg: "/img/dsc-0-large-on.png" },
    { key: "#", label: "#", command: "#", normalImg: "/img/dsc-pound-large.png", activeImg: "/img/dsc-pound-large-on.png" },
  ],
];

const PRELOAD_IMAGES = [
  "/img/f1-fire.png",
  "/img/f1-fire-on.png",
  "/img/f2-police.png",
  "/img/f2-police-on.png",
  "/img/f3-medical.png",
  "/img/f3-medical-on.png",
  "/img/f4-led-text.png",
  "/img/f4-led-text-on.png",
  "/img/led-on.png",
  "/img/led-on-red.png",
  "/img/led-off.png",
  "/img/chime.png",
  "/img/star-large.png",
  "/img/star-large-on.png",
  "/img/pound-large.png",
  "/img/pound-large-on.png",
  "/img/0-large.png",
  "/img/0-large-on.png",
  ...Array.from({ length: 9 }, (_, i) => `/img/${i + 1}-large.png`),
  ...Array.from({ length: 9 }, (_, i) => `/img/${i + 1}-large-on.png`),
];

export function Keypad({
  state,
  muted,
  disabled,
  disabledReason,
  flash,
  commandError,
  onClearCommandError,
  customButtons,
  onMuteChange,
  onCommand,
  onLoadCustomButtons,
  onCreateCustomButton,
  onSendCustomButton,
}: KeypadProps) {
  const [pressedKey, setPressedKey] = useState<string | null>(null);
  const [showCustomButtons, setShowCustomButtons] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);

  useEffect(() => {
    onLoadCustomButtons();
  }, [onLoadCustomButtons]);

  // Preload button images for zero-latency tactile presses
  useEffect(() => {
    PRELOAD_IMAGES.forEach((src) => {
      const img = new Image();
      img.src = src;
    });
  }, []);

  // Physical keyboard key listener
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target instanceof HTMLButtonElement
      ) {
        return;
      }
      if (disabled) return;

      const key = event.key.toUpperCase();
      if (/^[0-9]$/.test(key) || key === "*" || key === "#") {
        event.preventDefault();
        onClearCommandError?.();
        setPressedKey(key);
        window.setTimeout(() => {
          setPressedKey((prev) => (prev === key ? null : prev));
        }, 120);
        onCommand(key);
      } else if (key === "F1" || key === "F2" || key === "F3" || key === "F4") {
        event.preventDefault();
        onClearCommandError?.();
        setPressedKey(key);
        window.setTimeout(() => {
          setPressedKey((prev) => (prev === key ? null : prev));
        }, 120);
        onCommand(key, true);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [disabled, onCommand, onClearCommandError]);

  const handlePointerDown = (key: string) => {
    if (!disabled) {
      onClearCommandError?.();
      setPressedKey(key);
    }
  };

  const handlePointerUp = (key: string) => {
    if (pressedKey === key) {
      setPressedKey(null);
    }
  };

  const handlePointerLeave = (key: string) => {
    if (pressedKey === key) {
      setPressedKey(null);
    }
  };

  const isDsc = state.panel_type === "DSC";
  const rows = isDsc ? DSC_ROWS : ADEMCO_ROWS;

  return (
    <div className="panel-wrapper">
      {/* ── Authentic Dot-Matrix LCD Screen ── */}
      <div
        className={`panel-lcd-display ${flash ? "lcd-flash" : ""}`}
        role="log"
        aria-live="polite"
        aria-atomic="true"
        aria-label="Alarm Keypad Display"
      >
        <LcdLine
          text={state.display_line1 || (state.ready ? "READY TO ARM" : state.armed ? "ARMED" : "PLEASE WAIT")}
          cursorLocation={state.cursor_location}
          lineOffset={0}
        />
        <LcdLine
          text={state.display_line2 || ""}
          cursorLocation={state.cursor_location}
          lineOffset={16}
        />
      </div>

      {/* ── Status Indicator LEDs ── */}
      <div className="panel-led-row" aria-label="Panel status indicators">
        <div className="panel-led-item">
          <span className="panel-led-label">Armed:</span>
          <img
            src={state.armed ? "/img/led-on-red.png" : "/img/led-off.png"}
            alt={state.armed ? "Armed LED Illuminated" : "Armed LED Off"}
            className="panel-led-img"
          />
        </div>
        <div className="panel-led-item">
          <span className="panel-led-label">Ready:</span>
          <img
            src={state.ready ? "/img/led-on.png" : "/img/led-off.png"}
            alt={state.ready ? "Ready LED Illuminated" : "Ready LED Off"}
            className="panel-led-img"
          />
        </div>
        {state.chime ? (
          <div className="panel-led-item" title="Chime enabled">
            <img src="/img/chime.png" alt="Chime enabled" className="panel-chime-img" />
          </div>
        ) : null}
      </div>

      {/* ── Prominent Command Error / Rejection Notice ── */}
      {commandError ? (
        <div className="panel-command-alert" role="alert">
          <span className="panel-command-alert-icon">⚠️</span>
          <span className="panel-command-alert-msg">{commandError}</span>
          {onClearCommandError ? (
            <button
              type="button"
              className="panel-command-alert-dismiss"
              onClick={onClearCommandError}
              aria-label="Dismiss error"
            >
              ×
            </button>
          ) : null}
        </div>
      ) : null}

      {/* ── 4x4 Tactile Keypad Grid ── */}
      <div className="panel-grid-container">
        <div className="panel-keypad-grid" role="group" aria-label="Control panel keypad buttons">
          {rows.map((row) =>
            row.map((btn) => (
              <button
                key={btn.key}
                type="button"
                className={`panel-btn ${btn.isCircular ? "panel-btn-circle" : "panel-btn-rect"}`}
                disabled={disabled}
                onPointerDown={() => handlePointerDown(btn.key)}
                onPointerUp={() => handlePointerUp(btn.key)}
                onPointerLeave={() => handlePointerLeave(btn.key)}
                onPointerCancel={() => handlePointerLeave(btn.key)}
                onClick={() => onCommand(btn.command, btn.confirm)}
                aria-label={btn.label}
              >
                <img
                  src={pressedKey === btn.key ? btn.activeImg : btn.normalImg}
                  alt={btn.label}
                  draggable={false}
                  className="panel-btn-img"
                />
              </button>
            ))
          )}
        </div>
      </div>

      {/* ── Mute Sounds Checkbox ── */}
      <div className="panel-controls-bottom">
        <label className="panel-mute-label">
          <input
            type="checkbox"
            id="panel-check-mute"
            checked={muted}
            onChange={(e) => onMuteChange(e.target.checked)}
          />
          <span>Mute Sounds</span>
        </label>
      </div>

      {/* ── Disabled / Read-Only Warning Notice ── */}
      {disabled ? (
        <div className="panel-disabled-notice" role="status">
          <span>🔒 {disabledReason}</span>
        </div>
      ) : null}

      {/* ── Secondary Drawers for Custom Buttons and Quick Actions ── */}
      <div className="panel-aux-actions">
        {customButtons.length > 0 ? (
          <button
            type="button"
            className="panel-aux-toggle"
            onClick={() => setShowCustomButtons(!showCustomButtons)}
          >
            {showCustomButtons ? "▲ Hide Custom Buttons" : `▼ Custom Buttons (${customButtons.length})`}
          </button>
        ) : null}

        <button
          type="button"
          className="panel-aux-toggle"
          onClick={() => setShowQuickActions(!showQuickActions)}
        >
          {showQuickActions ? "▲ Hide Quick Actions" : "▼ Quick Actions"}
        </button>
      </div>

      {showCustomButtons && customButtons.length > 0 ? (
        <div className="panel-drawer-section">
          <div className="panel-drawer-header">
            <h4>Custom Buttons</h4>
            <button
              type="button"
              className="panel-drawer-add-btn"
              disabled={disabled}
              onClick={onCreateCustomButton}
            >
              + Add Button
            </button>
          </div>
          <div className="panel-drawer-grid">
            {customButtons.map((button) => (
              <button
                key={button.id}
                type="button"
                className="panel-drawer-btn"
                disabled={disabled || !button.enabled}
                onClick={() => onSendCustomButton(button.id, button.dangerous)}
              >
                {button.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {showQuickActions ? (
        <div className="panel-drawer-section">
          <div className="panel-drawer-header">
            <h4>Quick Actions</h4>
          </div>
          <div className="panel-drawer-grid">
            <button type="button" className="panel-drawer-btn" disabled={disabled} onClick={() => onCommand("STAY")}>
              Stay
            </button>
            <button type="button" className="panel-drawer-btn" disabled={disabled} onClick={() => onCommand("AWAY")}>
              Away
            </button>
            <button type="button" className="panel-drawer-btn danger" disabled={disabled} onClick={() => onCommand("DISARM", true)}>
              Disarm
            </button>
            <button type="button" className="panel-drawer-btn" disabled={disabled} onClick={() => onCommand("CHIME")}>
              Chime
            </button>
            <button type="button" className="panel-drawer-btn" disabled={disabled} onClick={() => onCommand("FAULT")}>
              Fault
            </button>
            <button type="button" className="panel-drawer-btn" disabled={disabled} onClick={() => onCommand("RESTORE")}>
              Restore
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LcdLine({
  text,
  cursorLocation,
  lineOffset = 0,
}: {
  text: string;
  cursorLocation: number | null;
  lineOffset?: number;
}) {
  const lineText = text ?? "";
  if (!lineText.trim()) {
    return <div className="lcd-line">&nbsp;</div>;
  }

  const hasCursor =
    cursorLocation !== null &&
    cursorLocation >= lineOffset &&
    cursorLocation < lineOffset + lineText.length;

  if (!hasCursor) {
    return <div className="lcd-line">{lineText}</div>;
  }

  return (
    <div className="lcd-line">
      {lineText.split("").map((ch, idx) => {
        const isCursor = cursorLocation === lineOffset + idx;
        return (
          <span key={idx} className={isCursor ? "lcd-cursor-char" : ""}>
            {ch === " " ? "\u00a0" : ch}
          </span>
        );
      })}
    </div>
  );
}
