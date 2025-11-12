# Jira Utilities

Python scripts for working with Jira and GitHub.

## Prerequisites

- **acli** (Atlassian CLI) - for Jira operations
- **gh** (GitHub CLI) - for GitHub operations
- Python 3.6 or higher

## Scripts

### 1. jira_pr_workflow.py (Recommended)

**Complete workflow**: Select a Jira ticket from your active sprints and create a PR for it.

This script orchestrates the other two scripts to provide a seamless workflow.

**Usage:**
```bash
./jira_pr_workflow.py [OPTIONS]
```

**Options:**
- `-h, --help` - Show help message
- `-b BOARD_ID, --board BOARD_ID` - Query specific board only
- `--url URL` - Jira base URL (default: auto-detect from acli)
- `--dir DIR` - Repository directory for PR creation
- `--base BRANCH` - Base branch for PR (default: auto-detect main/master)

**Examples:**
```bash
# Basic usage (will fetch all your active sprint items)
./jira_pr_workflow.py

# With Jira URL pre-configured
./jira_pr_workflow.py --url https://jira.company.com

# Specific board and repo directory
./jira_pr_workflow.py -b 173 --dir ~/repos/myproject

# All options
./jira_pr_workflow.py -b 173 --url https://jira.company.com --dir ~/repos/myproject --base master

# Using environment variable for Jira URL
export JIRA_BASE_URL=https://jira.company.com
./jira_pr_workflow.py
```

**How it works:**
1. Prompts for repository directory (or uses --dir argument)
2. Auto-detects current git branch
3. Auto-detects Jira URL from acli (or uses provided URL)
4. Fetches your active sprint items using `list_sprint_items.py`
5. Prioritizes items matching your current branch (shows them first)
6. Displays items with [Current Branch] marker for matches
7. Takes your selection and calls `create_jira_pr.py` to create the PR
8. **Checks if branch is pushed** and warns if not
9. Handles branch matching and PR creation automatically

---

### 2. list_sprint_items.py

Lists active work items in current sprints for the authenticated user.

**Usage:**
```bash
./list_sprint_items.py [OPTIONS]
```

**Options:**
- `-h, --help` - Show help message
- `-q, --quiet` - Only show final summary
- `-j, --json` - Output as JSON
- `-b BOARD_ID, --board BOARD_ID` - Query specific board only

**Examples:**
```bash
# Verbose output
./list_sprint_items.py

# Quiet mode
./list_sprint_items.py -q

# JSON output
./list_sprint_items.py -j

# Specific board
./list_sprint_items.py -b 173

# Pipe to jq
./list_sprint_items.py -j | jq '.items[].key'
```

### 3. create_jira_pr.py

Create a GitHub pull request from a Jira ticket (used by workflow script, but can be run standalone).

**Usage:**
```bash
./create_jira_pr.py JIRA_ID [OPTIONS]
```

**Arguments:**
- `JIRA_ID` - Jira ticket ID (e.g., PROJ-123)

**Options:**
- `-h, --help` - Show help message
- `--url URL` - Jira base URL (default: auto-detect from acli)
- `--dir DIR` - Repository directory (default: current directory)
- `--base BRANCH` - Base branch for PR (default: auto-detect main/master)

**Examples:**
```bash
# Basic usage (auto-detects URL from acli, prompts for directory)
./create_jira_pr.py PROJ-123

# With URL specified
./create_jira_pr.py PROJ-123 --url https://jira.company.com

# With all options
./create_jira_pr.py PROJ-123 --url https://jira.company.com --dir ~/repos/myproject --base master

# Using environment variable
export JIRA_BASE_URL=https://jira.company.com
./create_jira_pr.py PROJ-123
```

**How it works:**
1. Auto-detects Jira URL from acli (if not provided)
2. Searches for branches matching the Jira ID
3. If multiple matches, prompts you to select one
4. If no matches, offers to use current branch
5. **Checks if branch is pushed to remote**
   - Warns if branch doesn't exist on remote
   - Warns if branch has unpushed commits
   - Asks for confirmation to proceed
6. Auto-detects the base branch (main/master)
7. Creates PR with Jira ticket link in the body

## PR Template Customization

You can customize the PR title and description by creating a `.pr_template` file in your repository.

**Template Variables:**
- `{JIRA_ID}` - The Jira ticket ID (e.g., PROJ-123)
- `{JIRA_URL}` - Full URL to the Jira ticket
- `{BRANCH_SUFFIX}` - Branch name with Jira ID removed (e.g., `feature/PROJ-123-add-auth` → `add-auth`)

**Format:**
- First line: PR title template
- Remaining lines: PR body template

**Example `.pr_template`:**
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

If no template is found, the default format will be used: `[JIRA-ID]: ` with a simple link to the ticket.

## Setup

Make scripts executable:
```bash
chmod +x jira_pr_workflow.py list_sprint_items.py create_jira_pr.py
```

Set environment variable for Jira URL (optional):
```bash
# Add to ~/.bashrc or ~/.zshrc
export JIRA_BASE_URL=https://jira.company.com
```

## Installation

**Install acli:**
```bash
# Follow instructions at https://bobswift.atlassian.net/wiki/spaces/ACLI/overview
```

**Install gh:**
```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Then authenticate
gh auth login
```
