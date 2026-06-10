import { FormEvent, useState } from "react";

type LoginPanelProps = {
  onLogin: (username: string, password: string) => Promise<void>;
};

export function LoginPanel({ onLogin }: LoginPanelProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await onLogin(username, password);
      setPassword("");
    } catch {
      setError("Invalid username or password.");
    }
  };

  return (
    <section className="login-panel" aria-label="Login">
      <h2>Sign In</h2>
      <form onSubmit={submit}>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        <button type="submit">Sign in</button>
      </form>
      {error ? <p className="command-error">{error}</p> : null}
    </section>
  );
}
