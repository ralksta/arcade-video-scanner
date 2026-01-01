# Contributing to the Roadmap

Thank you for your interest in contributing to Arcade Video Scanner! This guide will help you suggest features and contribute to the project roadmap.

## 🗺️ Understanding the Roadmap

The roadmap is organized into versions:
- **v5.2.0** - Next release (near-term features)
- **v5.3.0** - Following release (medium-term features)
- **v6.0.0** - Major features (long-term vision)
- **Future Ideas** - Brainstorming (no timeline)

## 💡 Suggesting a Feature

### 1. Check Existing Resources
Before suggesting a feature, check if it already exists:
- Review [ROADMAP.md](ROADMAP.md)
- Search [existing issues](https://github.com/ralksta/arcade-video-scanner/issues)
- Check [closed issues](https://github.com/ralksta/arcade-video-scanner/issues?q=is%3Aissue+is%3Aclosed)

### 2. Create a Feature Request
If your feature is new, create a GitHub issue:

```bash
gh issue create --title "Your feature title" --label "enhancement" --body "
## Description
Describe the feature in detail

## Use Case
Why is this feature valuable?

## Proposed Solution
How should it work?

## Additional Context
Screenshots, examples, etc.
"
```

Or use the web interface: [New Issue](https://github.com/ralksta/arcade-video-scanner/issues/new/choose)

### 3. Discuss & Refine
- Engage in discussion on the issue
- Provide additional context if requested
- Be open to feedback and alternative approaches

## 🛠️ Contributing Code

### Getting Started
1. **Fork the repository**
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/arcade-video-scanner.git
   cd arcade-video-scanner
   ```

3. **Create a branch:**
   ```bash
   git checkout -b feature/issue-number-description
   # Example: git checkout -b feature/4-dark-theme
   ```

### Development Workflow
1. **Make your changes**
2. **Test thoroughly**
3. **Commit with clear messages:**
   ```bash
   git commit -m "Add dark theme toggle (#4)"
   ```

4. **Push to your fork:**
   ```bash
   git push origin feature/issue-number-description
   ```

5. **Create a Pull Request:**
   - Reference the issue: "Closes #4"
   - Describe what you changed
   - Include screenshots/videos if UI changes

### Code Standards
- Follow existing code style
- Add comments for complex logic
- Update documentation if needed
- Test on both Windows and macOS if possible

## 📝 Documentation Updates

When adding features, update:
- `README.md` - If it's a major feature
- `CHANGELOG.md` - Add to the "Unreleased" section
- `ROADMAP.md` - Move from planned to completed

## 🏷️ Issue Labels

| Label | Meaning |
|-------|---------|
| `enhancement` | New feature request |
| `bug` | Something isn't working |
| `planned` | Confirmed for roadmap |
| `v5.2.0`, `v5.3.0` | Target version |
| `performance` | Performance improvement |
| `ux` | User experience |
| `good-first-issue` | Good for newcomers |
| `help-wanted` | Looking for contributors |

## 🎯 Priority Guidelines

Features are prioritized based on:
1. **Impact** - How many users benefit?
2. **Effort** - Development time required
3. **Dependencies** - Does it unlock other features?
4. **Community Interest** - Number of 👍 reactions

## ❓ Questions?

- **General questions:** Open a [Discussion](https://github.com/ralksta/arcade-video-scanner/discussions)
- **Bug reports:** Create an [Issue](https://github.com/ralksta/arcade-video-scanner/issues)
- **Feature requests:** Create an [Issue](https://github.com/ralksta/arcade-video-scanner/issues)

## 🙏 Thank You!

Every contribution, whether it's code, documentation, bug reports, or feature suggestions, helps make Arcade Video Scanner better for everyone!

---

*For more details, see [ROADMAP.md](ROADMAP.md) and [GITHUB_SETUP.md](.github/GITHUB_SETUP.md)*
