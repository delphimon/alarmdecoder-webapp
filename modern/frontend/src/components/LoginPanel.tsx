import { type FormEvent, useEffect, useState } from "react";

type LoginPanelProps = {
  onLogin: (username: string, password: string) => Promise<void>;
  onLoginWithPasskey?: () => Promise<void>;
};

export function LoginPanel({ onLogin, onLoginWithPasskey }: LoginPanelProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [passkeyAvailable, setPasskeyAvailable] = useState(false);
  const [loadingPasskey, setLoadingPasskey] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && Boolean(window.PublicKeyCredential)) {
      setPasskeyAvailable(true);
    }
  }, []);

  const handlePasskey = async () => {
    if (!onLoginWithPasskey) return;
    setError(null);
    setLoadingPasskey(true);
    try {
      await onLoginWithPasskey();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passkey sign in cancelled or failed.");
    } finally {
      setLoadingPasskey(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await onLogin(username, password);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid username or password.");
    }
  };

  return (
    <section className="login-panel" aria-label="Sign in">
      <h2>🔐 AlarmDecoder Sign In</h2>

      {passkeyAvailable && onLoginWithPasskey ? (
        <>
          <button
            type="button"
            className="login-passkey-btn"
            onClick={handlePasskey}
            disabled={loadingPasskey}
          >
            {loadingPasskey ? "Waiting for device..." : "🔑 Sign in with Passkey"}
          </button>
          <div className="login-divider">
            <span>or sign in with password</span>
          </div>
        </>
      ) : null}

      <form onSubmit={submit} noValidate>
        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
            aria-describedby={error ? "login-error" : undefined}
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            required
            aria-describedby={error ? "login-error" : undefined}
          />
        </label>
        <button type="submit">Sign In</button>
      </form>
      {error ? (
        <p id="login-error" role="alert" className="command-error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
