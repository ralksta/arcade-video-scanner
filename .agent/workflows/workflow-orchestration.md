---
description: Core principles for planning, subagents, improvement, verification, and bug fixing
---

# Workflow Orchestration

## 1. Plan Mode Default
Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)

If something goes sideways, STOP and re-plan immediately – don't keep pushing

Use plan mode for verification steps, not just building

Write detailed specs upfront to reduce ambiguity

## 2. Subagent Strategy
Use subagents liberally to keep main context window clean

Offload research, exploration, and parallel analysis to subagents

For complex problems, throw more compute at it via subagents

One task per subagent for focused execution

## 3. Self-Improvement Loop
After ANY correction from the user: update tasks/lessons.md with the pattern

Write rules for yourself that prevent the same mistake

Ruthlessly iterate on these lessons until mistake rate drops

Review lessons at session start for relevant project

## 4. Verification Before Done
Never mark a task complete without proving it works

Diff behavior between main and your changes when relevant

Ask yourself: "Would a staff engineer approve this?"

Run tests, check logs, demonstrate correctness

## 7. Mandatory Test Execution — ALWAYS
**After EVERY code change, no exceptions:**

```bash
cd /Users/ralfo/git/arcade-video-scanner && python3 -m pytest tests/ -v --tb=short
```

This covers:
- JS syntax validity for all static/*.js files
- JS module completeness (disk ↔ dashboard_template.py)
- Generated HTML correctness (timestamps, script load order, globals)
- Python backend contracts (routes, DB, scanner)

**Do NOT declare a task done if any test is red.**
If a test fails after your change: fix it first, then continue.
This is non-negotiable — it's how the JS refactor bugs were caught.

## 5. Demand Elegance (Balanced)
For non-trivial changes: pause and ask "is there a more elegant way?"

If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"

Skip this for simple, obvious fixes – don't over-engineer

Challenge your own work before presenting it

## 6. Autonomous Bug Fixing
When given a bug report: just fix it. Don't ask for hand-holding

Point at logs, errors, failing tests – then resolve them

Zero context switching required from the user

Go fix failing CI tests without being told how

# Task Management
- **Plan First:** Write plan to tasks/todo.md with checkable items
- **Verify Plan:** Check in before starting implementation
- **Track Progress:** Mark items complete as you go
- **Explain Changes:** High-level summary at each step
- **Document Results:** Add review section to tasks/todo.md
- **Capture Lessons:** Update tasks/lessons.md after corrections

# Core Principles
- **Simplicity First:** Make every change as simple as possible. Impact minimal code.
- **No Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.
