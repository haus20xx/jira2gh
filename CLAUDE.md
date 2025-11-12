# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains Python utilities for integrating Jira (via acli) with GitHub (via gh CLI). The scripts automate the workflow of selecting Jira tickets from active sprints and creating pull requests.

## Prerequisites

- **acli** (Atlassian CLI) - Must be installed and authenticated for Jira operations
- **gh** (GitHub CLI) - Must be installed and authenticated for GitHub operations
- Python 3.6 or higher

## Common Commands

### Running the Scripts

**Primary workflow (recommended):**
```bash
./jira_pr_workflow.py                    # Interactive workflow: select ticket → create PR
./jira_pr_workflow.py -b 173             # Query specific board only
./jira_pr_workflow.py --url https://jira.company.com --dir ~/repos/myproject
```

**List sprint items:**
```bash
./list_sprint_items.py                   # Verbose output
./list_sprint_items.py -q                # Quiet mode (summary only)
./list_sprint_items.py -j                # JSON output
./list_sprint_items.py -b 173            # Specific board only
```

**Create PR from Jira ticket:**
```bash
./create_jira_pr.py PROJ-123            # Auto-detect URL, interactive prompts
./create_jira_pr.py PROJ-123 --url https://jira.company.com --dir ~/repos/myproject
```

### Making Scripts Executable

```bash
chmod +x jira_pr_workflow.py list_sprint_items.py create_jira_pr.py
```

## Architecture

### Script Orchestration

The repository uses a **composition pattern** where the main workflow script delegates to specialized scripts:

1. **jira_pr_workflow.py** (orchestrator)
   - Entry point for the complete workflow
   - Calls `list_sprint_items.py` to fetch Jira items (via subprocess with `-j` flag)
   - Parses JSON output to get active sprint items
   - Prioritizes items matching current git branch (shows `[Current Branch]` marker)
   - Calls `create_jira_pr.py` to create PR (via subprocess with command-line args)

2. **list_sprint_items.py** (data fetcher)
   - Standalone script that queries Jira via acli
   - Operates in three modes: verbose, quiet (`-q`), or JSON (`-j`)
   - When used by workflow script, always invoked with `-j` flag for programmatic parsing
   - Filters to current user's assigned items only
   - Categorizes items as open/closed based on status category

3. **create_jira_pr.py** (PR creator)
   - Standalone script that creates GitHub PR via gh CLI
   - Can be used independently or called by workflow script
   - Performs branch matching logic (searches for branches containing Jira ID)
   - Validates branch push status before creating PR
   - Auto-detects Jira URL from acli if not provided

### Key Design Patterns

**Branch Matching Logic** (create_jira_pr.py:72-76, jira_pr_workflow.py:39-56):
- Uses case-insensitive regex search to find branches containing Jira ID
- Prioritizes matching branches in workflow UI
- Falls back to current branch if no matches found

**Remote Branch Validation** (create_jira_pr.py:101-123):
- Checks if branch exists on remote before creating PR
- Warns if branch has unpushed commits
- Requires user confirmation to proceed if issues detected

**Jira URL Auto-detection** (create_jira_pr.py:32-46):
- Parses `acli jira auth status` output to extract Jira site
- Constructs HTTPS URL automatically
- Falls back to environment variable `JIRA_BASE_URL` or manual input

### Data Flow

```
jira_pr_workflow.py
  ├─> list_sprint_items.py -j [--board BOARD_ID]
  │     └─> acli jira board search --json
  │     └─> acli jira board list-sprints --state active --json
  │     └─> acli jira sprint list-workitems --jql "assignee = currentUser()" --json
  │     └─> Returns: {"total_active_items": N, "items": [...]}
  │
  └─> create_jira_pr.py JIRA_KEY [--url URL] [--dir DIR] [--base BRANCH]
        └─> git branch -a (find matching branches)
        └─> git fetch (update remote refs)
        └─> git ls-remote --heads origin BRANCH (check if pushed)
        └─> gh pr create --head BRANCH --base BASE --title "[JIRA_KEY]: " --body "Jira Ticket: [JIRA_KEY](URL)"
```

## Important Implementation Details

### Subprocess Communication

All inter-script communication uses subprocess with proper encoding:
- `encoding="utf-8"` with `errors="ignore"` to handle special characters
- JSON mode for structured data (workflow ↔ list_sprint_items)
- Command-line args for simple values (workflow → create_jira_pr)

### Sprint Item Categorization

Items are categorized by `statusCategory.key`:
- `"done"` → closed items
- `"new"` or `"indeterminate"` → open items

### Git Operations

The scripts assume:
- Repository has a remote named `origin`
- Default branch is one of: `main`, `master`, or `develop` (checked in that order)
- Branch names may contain Jira ticket IDs

### Error Handling

- All subprocess calls use `check=True` with try/except CalledProcessError
- JSON parsing errors are caught and reported to stderr
- Directory validation checks for `.git` folder to confirm git repo
- Empty outputs are handled gracefully (None returns)

## PR Template Support

The scripts support customizable PR templates via a `.pr_template` file in the repository directory.

### Template Format

- **First line**: PR title template
- **Remaining lines**: PR body template

### Template Variables

- `{JIRA_ID}` - The Jira ticket ID (e.g., `PROJ-123`)
- `{JIRA_URL}` - The full Jira ticket URL (e.g., `https://jira.company.com/browse/PROJ-123`)
- `{BRANCH_SUFFIX}` - The branch name with Jira ID removed (e.g., `feature/PROJ-123-add-auth` → `add-auth`)

### Example Template

Create a `.pr_template` file in your repository:

```markdown
[{JIRA_ID}] {BRANCH_SUFFIX}

## Jira Ticket
{JIRA_URL}

## Changes
-

## Testing
- [ ] Unit tests pass
- [ ] Manual testing completed
```

### Behavior

- If `.pr_template` exists, it will be used for PR creation
- If not found, falls back to default format: `[JIRA-ID]: ` (title) and `Jira Ticket: [JIRA-ID](URL)` (body)
- Template is loaded from the repository directory (where the PR is being created)

## Environment Variables

- `JIRA_BASE_URL` - Optional, sets default Jira URL (e.g., `https://jira.company.com`)

## Testing Individual Functions

When modifying the scripts, you can test individual functions:

```python
# Test branch matching
python3 -c "from create_jira_pr import find_matching_branches; print(find_matching_branches(['feature/PROJ-123-foo', 'main'], 'PROJ-123'))"

# Test Jira URL detection
python3 -c "from create_jira_pr import get_jira_url_from_acli; print(get_jira_url_from_acli())"

# Test sprint item categorization
python3 -c "from list_sprint_items import categorize_items; import json; print(categorize_items(json.loads(open('test_items.json').read())))"
```
