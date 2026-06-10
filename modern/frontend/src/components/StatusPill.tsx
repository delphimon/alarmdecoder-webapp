type StatusPillProps = {
  label: string;
  active: boolean;
  tone?: "green" | "red" | "amber" | "blue";
};

export function StatusPill({ label, active, tone = "green" }: StatusPillProps) {
  return (
    <span className={`status-pill ${active ? `is-${tone}` : ""}`}>
      <span className="status-dot" />
      {label}
    </span>
  );
}
