"""Fail (exit 1) if a JMeter .jtl has errors or a p95 over budget.

    python loadtest/check_results.py loadtest/results/results.jtl
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict

P95_BUDGET_MS = {"POST login": 1500}  # scrypt is slow on purpose
DEFAULT_P95_BUDGET_MS = 500
MAX_ERROR_RATE = 0.0


def percentile(values: list[int], pct: float) -> float:
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered)) - 1
    return float(ordered[max(0, rank)])


def main(path: str) -> int:
    samples: dict[str, list[int]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            label = row["label"]
            samples[label].append(int(row["elapsed"]))
            errors[label] += row["success"].lower() != "true"
    if not samples:
        print("no samples in results file")
        return 1

    failed = False
    print(f"{'request':<20}{'count':>7}{'errors':>8}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}{'budget':>9}  result")
    for label in sorted(samples):
        times = samples[label]
        p95 = percentile(times, 95)
        budget = P95_BUDGET_MS.get(label, DEFAULT_P95_BUDGET_MS)
        error_rate = errors[label] / len(times)
        ok = p95 <= budget and error_rate <= MAX_ERROR_RATE
        failed |= not ok
        print(f"{label:<20}{len(times):>7}{errors[label]:>8}{percentile(times, 50):>9.0f}{p95:>9.0f}"
              f"{max(times):>9}{budget:>9}  {'PASS' if ok else 'FAIL'}")
    total = sum(len(v) for v in samples.values())
    print(f"\n{total} requests, {sum(errors.values())} errors -> {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "loadtest/results/results.jtl"))
