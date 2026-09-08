import { useEffect, useState } from "react";

export type ThemePreference = "auto" | "light" | "dark";

const STORAGE_KEY = "ad2-theme";

/** Read the stored preference, defaulting to 'auto'. */
export function getThemePreference(): ThemePreference {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "auto") return stored;
  return "auto";
}

/** Apply the preference to the <html> element and return the effective theme. */
export function applyThemePreference(pref: ThemePreference): void {
  const root = document.documentElement;
  if (pref === "light") {
    root.dataset.theme = "light";
  } else if (pref === "dark") {
    root.dataset.theme = "dark";
  } else {
    delete root.dataset.theme; // let @media (prefers-color-scheme) take over
  }
  localStorage.setItem(STORAGE_KEY, pref);
}

/**
 * 3-way theme toggle: Auto | Light | Dark.
 *
 * - "Auto" removes [data-theme] and defers to the OS prefers-color-scheme media query.
 * - "Light" / "Dark" sets [data-theme="light"|"dark"] on <html>, overriding the media query.
 * - Preference persisted to localStorage under 'ad2-theme'.
 * - Initializes theme on mount so the app respects a previously saved preference.
 */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference);

  // Apply stored preference on mount
  useEffect(() => {
    applyThemePreference(preference);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const select = (next: ThemePreference) => {
    setPreference(next);
    applyThemePreference(next);
  };

  return (
    <div className="theme-toggle" role="group" aria-label="Color theme">
      <button
        type="button"
        className={preference === "light" ? "active" : ""}
        aria-label="Light theme"
        aria-pressed={preference === "light"}
        title="Light"
        onClick={() => select("light")}
      >
        ☀️
      </button>
      <button
        type="button"
        className={preference === "auto" ? "active" : ""}
        aria-label="Auto theme (follows OS setting)"
        aria-pressed={preference === "auto"}
        title="Auto"
        onClick={() => select("auto")}
      >
        ◑
      </button>
      <button
        type="button"
        className={preference === "dark" ? "active" : ""}
        aria-label="Dark theme"
        aria-pressed={preference === "dark"}
        title="Dark"
        onClick={() => select("dark")}
      >
        🌙
      </button>
    </div>
  );
}
