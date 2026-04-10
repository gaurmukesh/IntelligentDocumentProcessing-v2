---
name: Always use requirements.txt for pip installs
description: Do not run ad-hoc pip install commands — use requirements.txt
type: feedback
---

Always install dependencies via `pip install -r requirements.txt`, not ad-hoc `pip install <package>` commands. Dependencies are tracked in requirements.txt and should be kept up to date there first.

**Why:** User caught this — running separate pip installs bypasses the requirements file, which is the source of truth for the project's dependencies.

**How to apply:** Before running any pip install, check requirements.txt first. If a package is missing from requirements.txt, add it there first, then run `pip install -r requirements.txt`.
