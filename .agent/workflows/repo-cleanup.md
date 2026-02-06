---
description: Clean up repository by organizing test files, moving markdown documentation to dev-docs, and general housekeeping
---

# Repository Cleanup Workflow

This workflow organizes the Immich Refiner repository by:
- Moving development/internal markdown files to `dev-docs/`
- Moving test and script files to appropriate directories
- Cleaning up root directory clutter

## Pre-Cleanup Checklist

1. Ensure all changes are committed before cleanup
// turbo
2. Run `git status` to verify clean working tree

## Step 1: Move Internal Markdown Files to dev-docs/

Internal documentation that should live in `dev-docs/`:
- `security_best_practices_report.md` → `dev-docs/security-best-practices.md`
- Any implementation plans, audit reports, or internal notes

**DO NOT move these (they belong in root):**
- `README.md` - Main project documentation
- `LICENSE` - License file
- `FEATURES.md` - User-facing feature documentation
- `THEMING.md` - User-facing theming guide

// turbo
3. Move security report:
```bash
mv security_best_practices_report.md dev-docs/security-best-practices.md
```

4. Check for other stray markdown files in root that should be moved:
```bash
ls -la *.md
```

## Step 2: Organize Test Files

Test files should be co-located with their source or in a `__tests__` directory.

5. If test files exist in `scripts/`, evaluate if they should move to `src/__tests__/`:
```bash
# Create tests directory if needed
mkdir -p src/__tests__

# Move test files (adjust as needed)
# mv scripts/perf-test.ts src/__tests__/perf-test.ts
```

**Note:** `scripts/` is fine for utility scripts like `verify-contrast.cjs` and `perf-test.ts` that are dev tools, not unit tests.

## Step 3: Clean Up Artifacts and Temp Files

// turbo
6. Remove macOS metadata files:
```bash
find . -name ".DS_Store" -type f -delete
```

7. Update `.gitignore` if needed to prevent these from being committed:
```bash
# Ensure .DS_Store is in .gitignore
grep -q ".DS_Store" .gitignore || echo ".DS_Store" >> .gitignore
```

## Step 4: Verify and Commit

// turbo
8. Review changes:
```bash
git status
```

9. Stage and commit cleanup:
```bash
git add -A && git commit -m "chore: organize repository structure

- Move internal docs to dev-docs/
- Clean up root directory
- Remove temp/metadata files"
```

// turbo
10. Push changes:
```bash
git push
```

## Directory Structure Reference

After cleanup, the repo should follow this structure:

```
immich-refiner/
├── .agent/             # Agent workflows and configs
├── assets/             # Screenshots, images for docs
├── dev-docs/           # Internal development documentation
│   ├── IDEAS.md
│   ├── security-*.md
│   ├── *-algorithm.md
│   └── tech-stack.md
├── public/             # Static public assets
├── scripts/            # Development utility scripts
├── src/                # Source code
│   ├── __tests__/      # Test files (if needed)
│   ├── api/
│   ├── components/
│   ├── context/
│   ├── hooks/
│   ├── services/
│   ├── types/
│   └── utils/
├── src-tauri/          # Tauri desktop app source
├── FEATURES.md         # User-facing features
├── README.md           # Main readme
├── THEMING.md          # Theming guide
└── LICENSE
```
