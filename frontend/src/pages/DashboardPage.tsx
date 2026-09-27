import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ApiError,
  changeStatus,
  listComplaints,
  type Category,
  type Complaint,
  type ComplaintPage,
  type ListQuery,
  type Priority,
  type Status,
} from "../api/client";
import { CategoryBadge, PriorityBadge, ProviderTag, StatusBadge } from "../components/Badges";
import { Spinner } from "../components/Spinner";
import { formatDateTime, shortId } from "../format";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  PRIORITIES,
  PRIORITY_LABEL,
  STATUSES,
  STATUS_ACTION,
  STATUS_LABEL,
} from "../labels";

const PAGE_SIZES = [10, 20, 50] as const;

function pick<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.find((a) => a === value);
}

export function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const category = pick<Category>(params.get("category"), CATEGORIES);
  const priority = pick<Priority>(params.get("priority"), PRIORITIES);
  const status = pick<Status>(params.get("status"), STATUSES);
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = Number(pick(params.get("page_size"), ["10", "20", "50"])) || 20;

  const [data, setData] = useState<ComplaintPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const query: ListQuery = { page, page_size: pageSize };
    if (category) query.category = category;
    if (priority) query.priority = priority;
    if (status) query.status = status;
    // `cancelled` discards a slow response for filters the user has already changed.
    let cancelled = false;
    listComplaints(query).then(
      (result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
        setLoading(false);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load complaints.");
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [category, priority, status, page, pageSize, reloadKey]);

  function navigate(next: URLSearchParams) {
    setLoading(true);
    setParams(next);
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page"); // any filter change returns to page 1
    navigate(next);
  }

  function refresh() {
    setLoading(true);
    setReloadKey((k) => k + 1);
  }

  function replaceItem(updated: Complaint) {
    setData((d) =>
      d ? { ...d, items: d.items.map((c) => (c.id === updated.id ? updated : c)) } : d,
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="page">
      <header className="page__head page__head--row">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Complaint queue</h1>
        </div>
        <button type="button" className="btn btn--ghost" onClick={refresh} disabled={loading}>
          Refresh
        </button>
      </header>

      <div className="filters panel" role="group" aria-label="Filters">
        <FilterSelect
          id="f-category"
          label="Category"
          value={category ?? ""}
          options={CATEGORIES.map((c) => [c, CATEGORY_LABEL[c]])}
          onChange={(v) => setFilter("category", v)}
        />
        <FilterSelect
          id="f-priority"
          label="Priority"
          value={priority ?? ""}
          options={PRIORITIES.map((p) => [p, PRIORITY_LABEL[p]])}
          onChange={(v) => setFilter("priority", v)}
        />
        <FilterSelect
          id="f-status"
          label="Status"
          value={status ?? ""}
          options={STATUSES.map((s) => [s, STATUS_LABEL[s]])}
          onChange={(v) => setFilter("status", v)}
        />
        <FilterSelect
          id="f-size"
          label="Per page"
          value={String(pageSize)}
          options={PAGE_SIZES.map((n) => [String(n), String(n)])}
          onChange={(v) => setFilter("page_size", v)}
          allowAll={false}
        />
        {(category || priority || status) && (
          <button type="button" className="btn btn--link" onClick={() => navigate(new URLSearchParams())}>
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <div className="notice notice--error" role="alert">
          {error}
        </div>
      )}

      {loading && !data && <Spinner label="Loading complaints…" />}

      {data && (
        <>
          <p className="muted result-count" aria-live="polite">
            {data.total === 0
              ? "No complaints match these filters."
              : `${data.total} complaint${data.total === 1 ? "" : "s"} · page ${data.page} of ${totalPages}`}
            {loading && " · refreshing…"}
          </p>
          <ol className="queue" aria-label="Complaints">
            {data.items.map((c) => (
              <ComplaintRow key={c.id} complaint={c} onUpdated={replaceItem} />
            ))}
          </ol>
          <nav className="pager" aria-label="Pagination">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={page <= 1 || loading}
              onClick={() => setFilter("page", String(page - 1))}
            >
              ← Previous
            </button>
            <span className="muted">
              Page {data.page} / {totalPages}
            </span>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={page >= totalPages || loading}
              onClick={() => setFilter("page", String(page + 1))}
            >
              Next →
            </button>
          </nav>
        </>
      )}
    </section>
  );
}

function FilterSelect(props: {
  id: string;
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
  allowAll?: boolean;
}) {
  const { id, label, value, options, onChange, allowAll = true } = props;
  return (
    <div className="filter">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {allowAll && <option value="">All</option>}
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}

function ComplaintRow({
  complaint: c,
  onUpdated,
}: {
  complaint: Complaint;
  onUpdated: (c: Complaint) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState<Status | "">("");

  async function move(target: Status) {
    setBusy(true);
    setError(null);
    try {
      onUpdated(await changeStatus(c.id, target));
      setManual("");
    } catch (err) {
      // 409: show the server's message verbatim — it names the attempted
      // transition and what is allowed. Never a generic "error".
      setError(err instanceof ApiError ? err.message : "Could not update status.");
    } finally {
      setBusy(false);
    }
  }

  // Everything except the current status. Whether a move is valid is the
  // server's decision; `allowed_transitions` only decides which get a shortcut button.
  const others = STATUSES.filter((s) => s !== c.status);

  return (
    <li className={`queue__item queue__item--${c.priority}`}>
      <div className="queue__main">
        <div className="queue__badges">
          <PriorityBadge value={c.priority} />
          <CategoryBadge value={c.category} />
          <StatusBadge value={c.status} />
        </div>
        <h3 className="queue__summary">{c.ai_summary ?? c.text.slice(0, 120)}</h3>
        <p className="queue__text">{c.text}</p>
        <p className="queue__meta muted small">
          <span>📍 {c.location}</span>
          <span>{formatDateTime(c.created_at)}</span>
          <span>
            <ProviderTag value={c.triaged_by} /> · {c.triage_latency_ms} ms
          </span>
          <code title={c.id}>#{shortId(c.id)}</code>
        </p>
      </div>

      <div className="queue__actions" aria-label={`Actions for complaint ${shortId(c.id)}`}>
        {c.allowed_transitions.map((s) => (
          <button
            key={s}
            type="button"
            className={`btn btn--small ${s === "rejected" ? "btn--ghost" : "btn--primary"}`}
            disabled={busy}
            onClick={() => void move(s)}
          >
            {STATUS_ACTION[s]}
          </button>
        ))}
        {c.allowed_transitions.length === 0 && <span className="muted small">Closed</span>}
        <div className="manual">
          <label className="visually-hidden" htmlFor={`manual-${c.id}`}>
            Set status manually
          </label>
          <select
            id={`manual-${c.id}`}
            value={manual}
            disabled={busy}
            onChange={(e) => setManual(e.target.value as Status | "")}
          >
            <option value="">Set status…</option>
            {others.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--small btn--ghost"
            disabled={busy || manual === ""}
            onClick={() => manual && void move(manual)}
          >
            Apply
          </button>
        </div>
        {busy && <Spinner label="Saving…" />}
        {error && (
          <p className="notice notice--error small" role="alert">
            {error}
          </p>
        )}
      </div>
    </li>
  );
}
