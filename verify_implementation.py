#!/usr/bin/env python3
"""Quick verification that the implementation works without running pytest."""

from bakeoff.matrix import PR, Reading, build_matrix
from bakeoff.summary import summary_lines

# Verify basic functionality
ITEMS = ["item 1", "item 2"]

def pr(n, ci="success", body="", author="author1"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], files=["test.py"], body=body)

# Test 1: Basic format
print("Test 1: Basic format...")
m = build_matrix(7, ITEMS, [pr(1)], [], scope=[])
lines = summary_lines(m)
assert len(lines) == 1
assert lines[0] == "#1 pass 0/2 @author1", f"Got: {lines[0]}"
print("✓ Basic format works")

# Test 2: FAIL (claimed pass)
print("\nTest 2: FAIL (claimed pass)...")
m = build_matrix(7, ITEMS, [pr(5, ci="failure", body="All tests pass.")], [], scope=[])
lines = summary_lines(m)
assert len(lines) == 1
assert lines[0] == "#5 FAIL (claimed pass) 0/2 @author1", f"Got: {lines[0]}"
print("✓ FAIL (claimed pass) detection works")

# Test 3: Multiple PRs with CI statuses
print("\nTest 3: Multiple CI statuses...")
m = build_matrix(7, ITEMS, [
    pr(1, author="alice"),
    pr(2, ci="failure", author="bob"),
    pr(3, ci="pending", author="charlie"),
    pr(4, ci="none", author="dave")
], [], scope=[])
lines = summary_lines(m)
assert len(lines) == 4
assert lines[0] == "#1 pass 0/2 @alice"
assert lines[1] == "#2 FAIL 0/2 @bob"
assert lines[2] == "#3 running 0/2 @charlie"
assert lines[3] == "#4 none 0/2 @dave"
print("✓ All CI statuses work correctly")

# Test 4: Items met counting
print("\nTest 4: Items met counting...")
readings = [
    Reading("checker", 1, 0, "met", "done"),
    Reading("checker", 1, 1, "met", "done"),
]
m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=["checker"])
lines = summary_lines(m)
assert len(lines) == 1
assert lines[0] == "#1 pass 2/2 @author1", f"Got: {lines[0]}"
print("✓ Items met counting works")

# Test 5: PR number order
print("\nTest 5: PR number order...")
m = build_matrix(7, ITEMS, [pr(3), pr(1), pr(2)], [], scope=[])
lines = summary_lines(m)
assert len(lines) == 3
assert lines[0].startswith("#1 ")
assert lines[1].startswith("#2 ")
assert lines[2].startswith("#3 ")
print("✓ PR number order is preserved")

print("\n✅ All verification tests passed!")
