import { useEffect, useState } from "react";
import { config } from "../config";
import type { StatsResponse } from "../api/types";

/**
 * Stats view (§2.1). Required behavior:
 *   - Aggregate counts by category and priority
 *   - Display whether the response was a cache hit, from the X-Cache header —
 *     the spec calls this out specifically: "Showing your own cache behaviour
 *     in the UI is unusual and is exactly the kind of thing that makes a
 *     portfolio repo memorable."
 */
export function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [cacheStatus, setCacheStatus] = useState<"HIT" | "MISS" | null>(null);

  useEffect(() => {
    // TODO(you): the generic api.getStats() in api/client.ts doesn't expose
    // response headers. Either add a dedicated fetch call here that reads
    // resp.headers.get("X-Cache"), or extend the client to return both body
    // and headers for this one endpoint. Example:
    //
    //   const resp = await fetch(`${config.apiBaseUrl}/stats`);
    //   setCacheStatus(resp.headers.get("X-Cache") as "HIT" | "MISS");
    //   setStats(await resp.json());
    void config; // remove once you actually use config above
  }, []);

  return (
    <div>
      <h1>Statistics</h1>

      {cacheStatus && (
        <p>
          Cache: <strong>{cacheStatus}</strong>
        </p>
      )}

      {/* TODO(you): render stats.by_category and stats.by_priority as simple
          bar lists or tables — no charting library is required by the spec. */}
      {!stats && <p>Loading…</p>}
    </div>
  );
}
