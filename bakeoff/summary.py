"""One-line summaries of competing PRs: lightweight terminal view of the contest."""

from __future__ import annotations

from .matrix import Matrix


def summary_lines(matrix: Matrix) -> list[str]:
    """Generate one-line summaries for each PR in the matrix.
    
    Format: #<number> <CI> <items met>/<items> @<author>
    
    Where <CI> is one of: pass, FAIL, running, none
    (or FAIL (claimed pass) if the PR claims tests pass but CI shows failure)
    """
    lines = []
    for col in matrix.columns:
        # Determine CI status with claim-check
        if col.ci == "success":
            ci_status = "pass"
        elif col.ci == "failure":
            # Check if this PR claims tests pass despite CI failure
            if any(f.startswith("claims pass") for f in col.flags):
                ci_status = "FAIL (claimed pass)"
            else:
                ci_status = "FAIL"
        elif col.ci == "pending":
            ci_status = "running"
        elif col.ci == "none":
            ci_status = "none"
        else:
            ci_status = col.ci  # fallback for unknown statuses
        
        # Count items met
        items_met = sum(1 for cell in col.items if cell.status == "met")
        total_items = len(col.items)
        
        # Build the line
        line = f"#{col.number} {ci_status} {items_met}/{total_items} @{col.author}"
        lines.append(line)
    
    return lines
