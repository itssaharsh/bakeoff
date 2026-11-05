"""Generate one-line summaries of PRs in a contest matrix."""

from __future__ import annotations

from .matrix import Matrix


def summary_lines(matrix: Matrix) -> list[str]:
    """Return one line per PR in number order: #<number> <CI> <items met>/<items> @<author>."""
    lines = []
    for col in matrix.columns:
        ci_status = _format_ci(col.ci, "claims pass, CI failed" in col.flags)
        items_met = sum(1 for cell in col.items if cell.status == "met")
        total_items = len(col.items)
        line = f"#{col.number} {ci_status} {items_met}/{total_items} @{col.author}"
        lines.append(line)
    return lines


def _format_ci(ci: str, claimed_pass: bool) -> str:
    """Map CI status to display string, with special handling for claimed pass."""
    mapping = {
        "success": "pass",
        "failure": "FAIL",
        "pending": "running",
        "none": "none",
    }
    status = mapping.get(ci, ci)
    if claimed_pass and status == "FAIL":
        return "FAIL (claimed pass)"
    return status
