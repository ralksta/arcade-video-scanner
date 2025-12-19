# GitHub Issues & Project Setup

## ✅ What's Been Created

### Labels
The following labels have been created for issue organization:
- `planned` - Feature is confirmed for the roadmap (green)
- `v5.2.0` - Planned for version 5.2.0 (blue)
- `v5.3.0` - Planned for version 5.3.0 (purple)
- `performance` - Performance improvements (light purple)
- `ux` - User experience improvements (light yellow)

### Issues Created

**Version 5.2.0 (12 issues):**
1. [Migrate from JSON to SQLite database](https://github.com/ralksta/arcade-video-scanner/issues/1)
2. [Implement incremental scanning](https://github.com/ralksta/arcade-video-scanner/issues/2)
3. [Add background worker for preview generation](https://github.com/ralksta/arcade-video-scanner/issues/3)
4. [Dark/Light theme toggle](https://github.com/ralksta/arcade-video-scanner/issues/4)
5. [Customizable grid layout](https://github.com/ralksta/arcade-video-scanner/issues/5)
6. [Keyboard shortcuts for common actions](https://github.com/ralksta/arcade-video-scanner/issues/6)
7. [Advanced search with multiple criteria](https://github.com/ralksta/arcade-video-scanner/issues/7)
8. [Saved search filters/presets](https://github.com/ralksta/arcade-video-scanner/issues/8)
10. [Tag system for custom categorization](https://github.com/ralksta/arcade-video-scanner/issues/10)

**Version 5.3.0 (3 issues):**
9. [Duplicate detection for videos](https://github.com/ralksta/arcade-video-scanner/issues/9)
11. [Storage savings dashboard](https://github.com/ralksta/arcade-video-scanner/issues/11)
12. [Export to CSV/JSON for external analysis](https://github.com/ralksta/arcade-video-scanner/issues/12)

---

## 🎯 Next Steps (Optional)

### Create a GitHub Project Board

To create a visual kanban board for your roadmap:

1. **Refresh GitHub CLI permissions** (if you want to use CLI):
   ```bash
   gh auth refresh -s project,read:project
   gh project create --owner ralksta --title "Arcade Video Scanner Roadmap"
   ```

2. **Or create manually on GitHub:**
   - Go to https://github.com/ralksta/arcade-video-scanner/projects
   - Click "New project"
   - Choose "Board" template
   - Name it "Arcade Video Scanner Roadmap"
   - Add custom columns:
     - 📋 Backlog
     - 🎯 v5.2.0
     - 🚀 v5.3.0
     - 🔮 Future
     - ✅ Done

3. **Add issues to the project:**
   - Click "Add items" in the project
   - Search for your issues
   - Drag them to appropriate columns

### Create Milestones

Milestones help group issues by release version:

```bash
gh milestone create "v5.2.0" --description "Next major release" --due-date 2026-02-01
gh milestone create "v5.3.0" --description "Following release" --due-date 2026-04-01
```

Then assign issues to milestones:
```bash
gh issue edit 1 --milestone "v5.2.0"
gh issue edit 2 --milestone "v5.2.0"
# ... etc
```

---

## 📝 Managing Your Roadmap

### Workflow

1. **Planning Phase:**
   - Review ROADMAP.md
   - Create GitHub issues for planned features
   - Label with appropriate version and category
   - Add to project board

2. **Development Phase:**
   - Move issue to "In Progress" on project board
   - Create a branch: `git checkout -b feature/issue-number-description`
   - Develop and commit
   - Reference issue in commits: `git commit -m "Add dark theme toggle (#4)"`

3. **Completion Phase:**
   - Create pull request
   - Link to issue: "Closes #4"
   - Merge PR (issue auto-closes)
   - Update ROADMAP.md to mark as completed
   - Update CHANGELOG.md

### Quick Commands

```bash
# List all open issues
gh issue list

# List issues for a specific milestone
gh issue list --milestone "v5.2.0"

# List issues with a specific label
gh issue list --label "v5.2.0"

# View issue details
gh issue view 1

# Close an issue
gh issue close 1 --comment "Completed in v5.2.0"

# Reopen an issue
gh issue reopen 1
```

---

## 🎨 Customizing Labels

Add more labels as needed:

```bash
# Create new labels
gh label create "breaking-change" --description "Breaking API changes" --color "D93F0B"
gh label create "documentation" --description "Documentation improvements" --color "0075CA"
gh label create "good-first-issue" --description "Good for newcomers" --color "7057FF"
gh label create "help-wanted" --description "Extra attention needed" --color "008672"

# Edit existing labels
gh label edit "v5.2.0" --description "Updated description" --color "NEWCOLOR"

# Delete a label
gh label delete "old-label"
```

---

## 📊 Tracking Progress

### View Project Status
```bash
# List all projects
gh project list --owner ralksta

# View project items (requires project number)
gh project item-list PROJECT_NUMBER --owner ralksta
```

### Generate Reports
```bash
# Export all issues to JSON
gh issue list --limit 1000 --json number,title,state,labels,milestone > issues.json

# Count issues by label
gh issue list --label "v5.2.0" --json number --jq 'length'
```

---

## 🔗 Useful Links

- [Your Repository](https://github.com/ralksta/arcade-video-scanner)
- [Issues](https://github.com/ralksta/arcade-video-scanner/issues)
- [Projects](https://github.com/ralksta/arcade-video-scanner/projects)
- [Milestones](https://github.com/ralksta/arcade-video-scanner/milestones)
- [ROADMAP.md](../ROADMAP.md)
- [CHANGELOG.md](../CHANGELOG.md)
