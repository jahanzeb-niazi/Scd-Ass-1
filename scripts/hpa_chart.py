"""Plot HPA replicas against offered load, from real recordings.

    k6 run --out csv=docs/evidence/k6-results.csv load/k6-script.js
    ./scripts/record-hpa.sh > docs/evidence/hpa-samples.csv
    python scripts/hpa_chart.py docs/evidence/k6-results.csv docs/evidence/hpa-samples.csv \
        -o docs/evidence/hpa-scaling.png

Offered load = k6 requests started per 5-second bucket (metric `http_reqs`).
Requires matplotlib (pip install matplotlib). Also prints the lag between load
rising and replicas rising — the number ENGINEERING-NOTES Q5 asks for.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def load_rps(path: Path, bucket: int = 5) -> dict[int, float]:
    counts: Counter[int] = Counter()
    with path.open() as f:
        for row in csv.DictReader(f):
            if row.get("metric_name") == "http_reqs":
                t = int(float(row["timestamp"]))
                counts[t - t % bucket] += int(float(row.get("metric_value") or 1))
    return {t: n / bucket for t, n in sorted(counts.items())}


def load_hpa(path: Path) -> list[tuple[int, int | None, int | None]]:
    out = []
    with path.open() as f:
        for row in csv.DictReader(f):
            reps = row["current_replicas"]
            cpu = row["cpu_utilisation_pct"]
            out.append(
                (int(row["epoch_s"]), int(reps) if reps else None, int(cpu) if cpu else None)
            )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("k6_csv", type=Path)
    ap.add_argument("hpa_csv", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("docs/evidence/hpa-scaling.png"))
    args = ap.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rps = load_rps(args.k6_csv)
    hpa = load_hpa(args.hpa_csv)
    t0 = min([*rps.keys(), *(t for t, _, _ in hpa)])

    fig, ax1 = plt.subplots(figsize=(10, 4.8))
    ax1.plot(
        [t - t0 for t in rps], list(rps.values()), color="#2a78b8", label="offered load (req/s)"
    )
    ax1.set_xlabel("time since start (s)")
    ax1.set_ylabel("offered load (req/s)", color="#2a78b8")

    ax2 = ax1.twinx()
    pts = [(t - t0, r) for t, r, _ in hpa if r is not None]
    ax2.step(
        [p[0] for p in pts],
        [p[1] for p in pts],
        where="post",
        color="#d9622b",
        linewidth=2,
        label="backend replicas",
    )
    ax2.set_ylabel("replicas", color="#d9622b")
    ax2.set_ylim(0, max([p[1] for p in pts] + [10]) + 1)

    fig.suptitle("CivicPulse backend: HPA replicas vs offered load")
    fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.9))
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"chart written to {args.out}")

    # Lag: first load sample above 50 % of peak → first replica count above the minimum.
    peak = max(rps.values())
    load_up = next(t for t, v in rps.items() if v >= 0.5 * peak)
    base = min(p[1] for p in pts)
    scale_up = next((t + t0 for t, r in pts if r > base), None)
    if scale_up is None:
        print("replicas never rose above the minimum — check requests / metrics-server")
    else:
        print(
            f"load rose at t={load_up - t0}s, replicas rose at t={scale_up - t0}s "
            f"→ lag {scale_up - load_up}s"
        )


if __name__ == "__main__":
    main()
