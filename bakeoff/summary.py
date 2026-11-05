"""One-line-per-PR summaries of a contest."""

from __future__ import annotations

from .matrix import Matrix

_CI = {"success": "pass", "failure": "FAIL", "pending": "running", "none": "none"}


def summary_lines(matrix: Matrix) -> list[str]:
    """One line per competing PR, in PR-number order."""
    total = len(matrix.items)
    lines = []
    for column in sorted(matrix.columns, key=lambda c: c.number):
        ci = _CI.get(column.ci, column.ci)
        if column.ci == "failure" and "claims pass, CI failed" in column.flags:
            ci += " (claimed pass)"
        met = sum(1 for cell in column.items if cell.status == "met")
        lines.append(f"#{column.number} {ci} {met}/{total} @{column.author}")
    return lines
