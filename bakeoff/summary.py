"""The contest at a glance: one line per competing PR, for a terminal."""

from __future__ import annotations

from .matrix import Matrix

_CI = {"success": "pass", "failure": "FAIL", "pending": "running", "none": "none"}
_CLAIMED_PASS = "claims pass, CI failed"  # the flag build_matrix sets


def summary_lines(matrix: Matrix) -> list[str]:
    """`#<number> <CI> <items met>/<items> @<author>` for each PR, in PR-number order.

    A PR whose body claims its tests pass while GitHub's CI failed shows
    `FAIL (claimed pass)`. An item counts as met only when every reader marked it met.
    """
    lines = []
    for col in sorted(matrix.columns, key=lambda c: c.number):
        ci = _CI.get(col.ci, col.ci)
        if col.ci == "failure" and _CLAIMED_PASS in col.flags:
            ci += " (claimed pass)"
        met = sum(cell.status == "met" for cell in col.items)
        lines.append(f"#{col.number} {ci} {met}/{len(matrix.items)} @{col.author}")
    return lines
