export function Spinner({ label }: { label: string }) {
  return (
    <span className="spinner" role="status" aria-live="polite">
      <span className="spinner__ring" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
