import { useEffect, useState } from "react";
import {
  ApiError,
  getProviders,
  getStats,
  type CacheState,
  type Providers,
  type Stats,
} from "../api/client";
import { ProviderTag } from "../components/Badges";
import { Spinner } from "../components/Spinner";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  PRIORITIES,
  PRIORITY_LABEL,
  STATUSES,
  STATUS_LABEL,
} from "../labels";

export function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cache, setCache] = useState<CacheState>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    // State is only set from the async callbacks, and `cancelled` drops a
    // response that arrives after the user has refreshed again or left the page.
    let cancelled = false;
    Promise.all([getStats(), getProviders()]).then(
      ([s, p]) => {
        if (cancelled) return;
        setStats(s.stats);
        setCache(s.cache);
        setProviders(p);
        setFetchedAt(new Date());
        setLoading(false);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load statistics.");
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function refresh() {
    setLoading(true);
    setError(null);
    setReloadKey((k) => k + 1);
  }

  return (
    <section className="page">
      <header className="page__head page__head--row">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Statistics</h1>
        </div>
        <button type="button" className="btn btn--ghost" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && (
        <div className="notice notice--error" role="alert">
          {error}
        </div>
      )}
      {loading && !stats && <Spinner label="Loading statistics…" />}

      {stats && (
        <>
          <div className="stat-hero panel">
            <div>
              <p className="label">Total complaints</p>
              <p className="stat-hero__value">{stats.total.toLocaleString()}</p>
            </div>
            <CacheIndicator state={cache} fetchedAt={fetchedAt} />
          </div>

          <div className="grid-3">
            <Breakdown
              title="By category"
              total={stats.total}
              rows={CATEGORIES.map((c) => [c, CATEGORY_LABEL[c], stats.by_category[c] ?? 0])}
              kind="cat"
            />
            <Breakdown
              title="By priority"
              total={stats.total}
              rows={PRIORITIES.map((p) => [p, PRIORITY_LABEL[p], stats.by_priority[p] ?? 0])}
              kind="pri"
            />
            <Breakdown
              title="By status"
              total={stats.total}
              rows={STATUSES.map((s) => [s, STATUS_LABEL[s], stats.by_status[s] ?? 0])}
              kind="status"
            />
          </div>
        </>
      )}

      {providers && <ProvidersPanel providers={providers} />}
    </section>
  );
}

function CacheIndicator({ state, fetchedAt }: { state: CacheState; fetchedAt: Date | null }) {
  const text =
    state === "HIT"
      ? "Served from the Redis cache — no database query was run."
      : state === "MISS"
        ? "Computed from PostgreSQL, then cached for 30 s (or until the next write)."
        : "Cache state not reported by the server.";
  return (
    <div className={`cache cache--${(state ?? "unknown").toLowerCase()}`} data-testid="cache-indicator">
      <p className="label">X-Cache</p>
      <p className="cache__state">{state ?? "—"}</p>
      <p className="muted small">{text}</p>
      {fetchedAt && <p className="muted small">Fetched {fetchedAt.toLocaleTimeString()}</p>}
    </div>
  );
}

function Breakdown(props: {
  title: string;
  total: number;
  rows: [string, string, number][];
  kind: "cat" | "pri" | "status";
}) {
  const max = Math.max(1, ...props.rows.map(([, , n]) => n));
  return (
    <section className="panel breakdown" aria-label={props.title}>
      <h2 className="breakdown__title">{props.title}</h2>
      <ul>
        {props.rows.map(([key, label, n]) => (
          <li key={key} className="bar">
            <span className="bar__label">{label}</span>
            <span className="bar__track" aria-hidden="true">
              <span className={`bar__fill bar__fill--${props.kind}-${key}`} style={{ width: `${(n / max) * 100}%` }} />
            </span>
            <span className="bar__value">
              {n}
              <span className="muted small">
                {" "}
                {props.total ? `${Math.round((n / props.total) * 100)}%` : ""}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ProvidersPanel({ providers: p }: { providers: Providers }) {
  const rate = p.cache.hit_rate;
  return (
    <section className="panel providers" aria-label="Triage provider">
      <h2 className="breakdown__title">AI triage</h2>
      <dl className="kv">
        <div>
          <dt>Active provider</dt>
          <dd>
            <ProviderTag value={p.active} /> {p.model && <code>{p.model}</code>}
          </dd>
        </div>
        <div>
          <dt>Fallback</dt>
          <dd>
            <ProviderTag value={p.fallback} />
          </dd>
        </div>
        <div>
          <dt>Timeout</dt>
          <dd>{p.timeout_s} s</dd>
        </div>
        <div>
          <dt>Triage cache hit rate</dt>
          <dd>
            {rate === null ? "no lookups yet" : `${(rate * 100).toFixed(1)}%`}{" "}
            <span className="muted small">
              ({p.cache.hits} hits / {p.cache.misses} misses)
            </span>
          </dd>
        </div>
      </dl>

      <h3 className="label">Last {p.recent.length} triage outcomes</h3>
      {p.recent.length === 0 ? (
        <p className="muted">No complaints triaged since the cache was last cleared.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Provider</th>
                <th scope="col" className="num">
                  Latency
                </th>
                <th scope="col">Fallback</th>
                <th scope="col">Cache</th>
                <th scope="col">Error</th>
              </tr>
            </thead>
            <tbody>
              {p.recent.map((r) => (
                <tr key={`${r.complaint_id}-${r.at}`} className={r.fallback ? "row--warn" : ""}>
                  <td>{new Date(r.at).toLocaleTimeString()}</td>
                  <td>
                    <ProviderTag value={r.provider} />
                  </td>
                  <td className="num">{r.latency_ms} ms</td>
                  <td>{r.fallback ? "yes" : "no"}</td>
                  <td>{r.cache_hit ? "hit" : "—"}</td>
                  <td>
                    <code>{r.error ?? ""}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
