# Quick Reference: Managing Your Roadmap

## 📁 Files Created

| File | Purpose |
|------|---------|
| `ROADMAP.md` | Master feature roadmap (edit this!) |
| `GITHUB_SETUP.md` | Complete guide to GitHub integration |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Template for new feature requests |

## 🏷️ Labels Created

- `planned` - Confirmed for roadmap
- `v5.2.0` - Next release
- `v5.3.0` - Following release  
- `performance` - Performance improvements
- `ux` - User experience

## 📋 Issues Created (12 total)

### Version 5.2.0 (9 issues)
- #1 - SQLite database migration
- #2 - Incremental scanning
- #3 - Background preview generation
- #4 - Dark/Light theme
- #5 - Customizable grid layout
- #6 - Keyboard shortcuts
- #7 - Advanced search
- #8 - Saved search filters
- #10 - Tag system

### Version 5.3.0 (3 issues)
- #9 - Duplicate detection
- #11 - Storage savings dashboard
- #12 - CSV/JSON export

## 🚀 Quick Commands

```bash
# View all issues
gh issue list

# View v5.2.0 issues
gh issue list --label "v5.2.0"

# Create new issue
gh issue create --title "Your feature" --label "enhancement,planned"

# Close completed issue
gh issue close 1 --comment "Completed!"
```

## ✏️ Editing the Roadmap

1. **Edit ROADMAP.md** - Add/remove/reorganize features
2. **Create GitHub issues** - For features you want to track
3. **Update CHANGELOG.md** - When features are completed
4. **Commit changes** - Keep everything in sync

## 🎯 Recommended Workflow

1. **Add feature to ROADMAP.md**
2. **Create GitHub issue** with appropriate labels
3. **Develop feature** in a branch
4. **Reference issue** in commits: `git commit -m "Add feature (#issue-number)"`
5. **Close issue** when merged
6. **Update CHANGELOG.md** for release notes

## 🔗 Quick Links

- [All Issues](https://github.com/ralksta/arcade-video-scanner/issues)
- [v5.2.0 Issues](https://github.com/ralksta/arcade-video-scanner/issues?q=is%3Aissue+is%3Aopen+label%3Av5.2.0)
- [v5.3.0 Issues](https://github.com/ralksta/arcade-video-scanner/issues?q=is%3Aissue+is%3Aopen+label%3Av5.3.0)

---

**Pro Tip:** The ROADMAP.md is your source of truth. GitHub issues are for tracking implementation. Keep both in sync!
