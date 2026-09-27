import type { Category, Priority, Status } from "../api/client";
import { CATEGORY_LABEL, PRIORITY_LABEL, STATUS_LABEL, providerLabel } from "../labels";

export function CategoryBadge({ value }: { value: Category }) {
  return <span className={`badge badge--cat badge--cat-${value}`}>{CATEGORY_LABEL[value]}</span>;
}

export function PriorityBadge({ value }: { value: Priority }) {
  return (
    <span className={`badge badge--pri badge--pri-${value}`}>
      <span className="dot" aria-hidden="true" />
      {PRIORITY_LABEL[value]}
    </span>
  );
}

export function StatusBadge({ value }: { value: Status }) {
  return <span className={`badge badge--status badge--status-${value}`}>{STATUS_LABEL[value]}</span>;
}

export function ProviderTag({ value }: { value: string }) {
  const kind = value.startsWith("llm:") ? "llm" : value === "rules:fallback" ? "fallback" : "rules";
  return (
    <span className={`provider provider--${kind}`} title={value}>
      {providerLabel(value)}
    </span>
  );
}
