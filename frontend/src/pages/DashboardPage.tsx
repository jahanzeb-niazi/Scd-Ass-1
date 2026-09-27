import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Category, ComplaintOut, ComplaintStatus, Priority } from "../api/types";

/**
 * Dashboard view (§2.1). Required behavior:
 *   - Paginated, filterable list (category, priority, status)
 *   - Operator can advance status
 *   - An invalid transition must surface the SERVER's 409 message verbatim,
 *     not a generic "error" — this is graded explicitly (§2.1, rubric B)
 */
export function DashboardPage() {
  const [items, setItems] = useState<ComplaintOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [categoryFilter, setCategoryFilter] = useState<Category | "">("");
  const [priorityFilter, setPriorityFilter] = useState<Priority | "">("");
  const [statusFilter, setStatusFilter] = useState<ComplaintStatus | "">("");

  const [transitionError, setTransitionError] = useState<string | null>(null);

  useEffect(() => {
    // TODO(you): call api.listComplaints({ category: categoryFilter || undefined, ...,
    // page, page_size: pageSize }) and setItems/setTotal from the response.
    // Re-run whenever page or any filter changes (this effect's dependency array).
  }, [page, categoryFilter, priorityFilter, statusFilter]);

  async function advanceStatus(id: string, newStatus: ComplaintStatus) {
    setTransitionError(null);
    try {
      // TODO(you): await api.updateStatus(id, newStatus); then refresh the list
      // (or optimistically update the single row).
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // TODO(you): err.body should contain the server's message naming the
        // attempted transition (per backend §2.2) — render it VERBATIM here,
        // not a generic string. Adjust the field name to match your backend's
        // actual 409 body shape.
        setTransitionError(
          typeof err.body === "object" && err.body && "error" in err.body
            ? String((err.body as { error: unknown }).error)
            : "Invalid transition",
        );
      } else {
        setTransitionError("Could not update status.");
      }
    }
  }

  return (
    <div>
      <h1>Operations Dashboard</h1>

      {/* TODO(you): filter controls — bind to categoryFilter/priorityFilter/statusFilter,
          reset page to 1 whenever a filter changes */}

      {transitionError && <p role="alert">{transitionError}</p>}

      {/* TODO(you): render `items` as a table: text, location, category, priority,
          status, and controls to advance status (respecting the state machine —
          you can either let the server be the sole source of truth and just
          attempt any transition, showing the 409 on failure, or mirror the
          transition table client-side to disable invalid buttons — document
          whichever you choose). */}

      <div>
        {/* TODO(you): pagination controls using `page`, `total`, `pageSize` */}
        <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Previous
        </button>
        <span>
          Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
        </span>
        <button
          disabled={page * pageSize >= total}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
