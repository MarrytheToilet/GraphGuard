#!/usr/bin/env python3
"""Synchronize the paper's figure inputs with the canonical asset copies.

Figure producers write to ``assets/figures``.  The private manuscript reads
from ``paper/figures``.  The default mode is read-only and checks every active
figure byte-for-byte; ``--write`` performs the explicit synchronization.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "figures"
TARGET = ROOT / "paper" / "figures"

ACTIVE_FIGURES = (
    "fig_contract_overview.png",
    "fig_crossrun_violations.png",
    "fig_noise_floor.png",
    "fig_calibration.png",
    "fig_2d_sensitivity.png",
    "fig_strict_vs_soft.png",
    "fig_magnitude.png",
    "fig_amp_crossrun.png",
    "fig_extqueries.png",
    "fig_auroc.png",
    "fig_gate.png",
    "fig_riskcoverage.png",
    "fig_budget_planner.png",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="copy canonical assets into the private manuscript tree",
    )
    args = parser.parse_args()

    if not TARGET.parent.is_dir():
        raise FileNotFoundError(
            "private manuscript directory is absent: "
            f"{TARGET.parent.relative_to(ROOT)}"
        )
    if args.write:
        TARGET.mkdir(parents=True, exist_ok=True)

    mismatches = []
    for name in ACTIVE_FIGURES:
        source = SOURCE / name
        target = TARGET / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if args.write:
            shutil.copy2(source, target)
        if not target.is_file() or sha256_file(source) != sha256_file(target):
            mismatches.append(name)

    if mismatches:
        print("[FAIL] paper figure mismatch: " + ", ".join(mismatches))
        return 1
    action = "synchronized" if args.write else "verified"
    print(f"[PASS] {action} {len(ACTIVE_FIGURES)} active paper figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
