import { useEffect } from "react";
import type { CustomButton, PanelState } from "../types";

type KeypadProps = {
  state: PanelState;
  muted: boolean;
  disabled: boolean;
  disabledReason: string;
  flash: boolean;
  onMuteChange: (muted: boolean) => void;
  onCommand: (command: string, confirm?: boolean) => void;
  customButtons: CustomButton[];
  onLoadCustomButtons: () => void;
  onCreateCustomButton: () => void;
  onSendCustomButton: (id: number, confirm?: boolean) => void;
};

const digitRows = [
  ["1", "2", "3"],
  ["4", "5", "6"],
  ["7", "8", "9"],
  ["*", "0", "#"],
];

export function Keypad({
  state,
  muted,
  disabled,
  disabledReason,
  flash,
  customButtons,
  onMuteChange,
  onCommand,
  onLoadCustomButtons,
  onCreateCustomButton,
  onSendCustomButton,
}: KeypadProps) {
  useEffect(() => {
    onLoadCustomButtons();
  }, [onLoadCustomButtons]);

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
      if (disabled) {
        return;
      }
      const key = event.key.toUpperCase();
      if (/^[0-9]$/.test(key) || key === "*" || key === "#") {
        event.preventDefault();
        onCommand(key);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [disabled, onCommand]);

  const panelType = state.panel_type === "DSC" ? "DSC" : "ADEMCO";

  return (
    <section className="keypad-panel" aria-label="Alarm keypad">
      <div className={`lcd ${flash ? "lcd-flash" : ""}`}>
        <LcdLine text={state.display_line1} start={0} cursorLocation={state.cursor_location} />
        <LcdLine text={state.display_line2} start={16} cursorLocation={state.cursor_location} />
      </div>

      <div className="indicator-strip" aria-label="Panel indicators">
        <Indicator label="Armed" active={state.armed} tone="red" />
        <Indicator label="Ready" active={state.ready} tone="green" />
        <Indicator label="Chime" active={state.chime} tone="blue" />
      </div>

      {panelType === "DSC" ? (
        <DscKeys disabled={disabled} onCommand={onCommand} />
      ) : (
        <AdemcoKeys disabled={disabled} onCommand={onCommand} />
      )}

      {disabled ? <p className="read-only-note">{disabledReason}</p> : null}

      <div className="custom-buttons" aria-label="Custom keypad buttons">
        <div className="custom-buttons-header">
          <h3>Custom</h3>
          <button type="button" disabled={disabled} onClick={onCreateCustomButton}>Add</button>
        </div>
        {customButtons.length ? (
          <div className="custom-button-list">
            {customButtons.map((button) => (
              <button
                key={button.id}
                type="button"
                disabled={disabled || !button.enabled}
                onClick={() => onSendCustomButton(button.id, button.dangerous)}
              >
                {button.label}
              </button>
            ))}
          </div>
        ) : (
          <p className="muted-text">No custom buttons configured.</p>
        )}
      </div>

      <label className="mute-toggle">
        <input
          type="checkbox"
          checked={!muted}
          onChange={(event) => onMuteChange(!event.target.checked)}
        />
        Sounds
      </label>
    </section>
  );
}

function LcdLine({ text, start, cursorLocation }: { text: string; start: number; cursorLocation: number | null }) {
  const chars = (text || "").padEnd(16, " ").slice(0, 16).split("");
  return (
    <div className="lcd-line">
      {chars.map((char, index) => {
        const position = start + index;
        return (
          <span key={`${start}-${index}`} className={cursorLocation === position ? "lcd-cursor" : ""}>
            {char === " " ? "\u00a0" : char}
          </span>
        );
      })}
    </div>
  );
}

function AdemcoKeys({ disabled, onCommand }: { disabled: boolean; onCommand: (command: string, confirm?: boolean) => void }) {
  return (
    <>
      <div className="keypad-grid">
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("F1", true)}>
          F1
          <span>Fire</span>
        </button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("F2", true)}>
          F2
          <span>Panic</span>
        </button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("F3", true)}>
          F3
          <span>Aux</span>
        </button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("F4")}>
          F4
          <span>Prog</span>
        </button>

        {digitRows.flat().map((key) => (
          <button className="key" type="button" key={key} disabled={disabled} onClick={() => onCommand(key)}>
            {key}
          </button>
        ))}
      </div>

      <div className="quick-actions" aria-label="Alarm commands">
        <button type="button" disabled={disabled} onClick={() => onCommand("STAY")}>Stay</button>
        <button type="button" disabled={disabled} onClick={() => onCommand("AWAY")}>Away</button>
        <button type="button" disabled={disabled} onClick={() => onCommand("DISARM", true)}>Disarm</button>
        <button type="button" disabled={disabled} onClick={() => onCommand("CHIME")}>Chime</button>
        <button type="button" disabled={disabled} onClick={() => onCommand("FAULT")}>Fault</button>
        <button type="button" disabled={disabled} onClick={() => onCommand("RESTORE")}>Restore</button>
      </div>
    </>
  );
}

function DscKeys({ disabled, onCommand }: { disabled: boolean; onCommand: (command: string, confirm?: boolean) => void }) {
  return (
    <>
      <div className="dsc-command-grid" aria-label="DSC controls">
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("STAY")}>Stay</button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("AWAY")}>Away</button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("CHIME")}>Chime</button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("RESET", true)}>Reset</button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("EXIT")}>Exit</button>
        <button className="key function" type="button" disabled={disabled} onClick={() => onCommand("PANIC", true)}>Panic</button>
      </div>

      <div className="keypad-grid dsc-grid">
        {digitRows.flat().map((key) => (
          <button className="key" type="button" key={key} disabled={disabled} onClick={() => onCommand(key)}>
            {key}
          </button>
        ))}
        <button className="key nav-key" type="button" disabled={disabled} onClick={() => onCommand("LEFT")}>Left</button>
        <button className="key nav-key" type="button" disabled={disabled} onClick={() => onCommand("RIGHT")}>Right</button>
        <button className="key nav-key" type="button" disabled={disabled} onClick={() => onCommand("UP")}>Up</button>
        <button className="key nav-key" type="button" disabled={disabled} onClick={() => onCommand("DOWN")}>Down</button>
      </div>
    </>
  );
}

function Indicator({ label, active, tone }: { label: string; active: boolean; tone: string }) {
  return (
    <div className={`indicator ${active ? `indicator-${tone}` : ""}`}>
      <span />
      {label}
    </div>
  );
}
