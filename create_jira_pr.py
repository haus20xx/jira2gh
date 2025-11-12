#!/usr/bin/env python3
"""
Create a GitHub PR from a Jira ticket.
"""
import subprocess
import sys
import argparse
import os
import re


def run_command(command, cwd=None):
    """Execute a command and return the output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            encoding="utf-8",
            errors="ignore",  # Ignore encoding errors from special characters
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr if hasattr(e, "stderr") else ""
        print(f"Error: {stderr}", file=sys.stderr)
        return None


def get_jira_url_from_acli():
    """Get Jira URL from acli configuration file or auth status."""
    # Try reading from config file first (faster)
    config_path = os.path.expanduser("~/.config/acli/jira_config.yaml")

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse the YAML-like structure (simple parsing for this specific format)
            # Find the site from the first profile (or current profile)
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- site:") or line.startswith("site:"):
                    # Extract site value
                    site = line.split(":", 1)[1].strip()
                    if site:
                        return f"https://{site}"
        except Exception:
            # If config file reading fails, fall back to acli command
            pass

    # Fallback: use acli command
    output = run_command("acli jira auth status")
    if not output:
        return None

    # Parse the Site line from acli auth status
    for line in output.split("\n"):
        if "Site:" in line:
            site = line.split("Site:")[1].strip()
            # Construct URL from site
            if site:
                return f"https://{site}"

    return None


def get_branches(repo_dir):
    """Get all branches (local and remote)."""
    output = run_command("git branch -a", cwd=repo_dir)
    if not output:
        return []

    branches = []
    for line in output.split("\n"):
        # Remove leading * and whitespace
        branch = line.strip().lstrip("* ").strip()
        # Skip HEAD reference
        if "HEAD" in branch:
            continue
        # Remove remote prefix
        if branch.startswith("remotes/origin/"):
            branch = branch.replace("remotes/origin/", "")
        # Avoid duplicates
        if branch and branch not in branches:
            branches.append(branch)

    return branches


def find_matching_branches(branches, jira_id):
    """Find branches that contain the Jira ID."""
    pattern = re.compile(re.escape(jira_id), re.IGNORECASE)
    return [b for b in branches if pattern.search(b)]


def extract_branch_suffix(branch_name, jira_id):
    """Extract branch name suffix after removing Jira ID and delimiters."""
    # Find and remove the Jira ID (case insensitive)
    pattern = re.compile(re.escape(jira_id), re.IGNORECASE)
    match = pattern.search(branch_name)

    if not match:
        # If Jira ID not found in branch, return the whole branch name
        return branch_name

    # Remove the Jira ID
    suffix = branch_name[match.end() :]

    # Strip leading delimiters (- or /)
    suffix = suffix.lstrip("-/")

    # If nothing left after Jira ID, try getting the part before it
    if not suffix:
        suffix = branch_name[: match.start()].rstrip("-/")

    return suffix if suffix else branch_name


def get_current_branch(repo_dir):
    """Get the current branch name."""
    return run_command("git branch --show-current", cwd=repo_dir)


def get_default_branch(repo_dir):
    """Get the default branch (main/master)."""
    # Try to get the default branch from remote
    output = run_command("git remote show origin", cwd=repo_dir)
    if output:
        for line in output.split("\n"):
            if "HEAD branch:" in line:
                return line.split(":")[1].strip()

    # Fallback to common names
    branches = get_branches(repo_dir)
    for name in ["main", "master", "develop"]:
        if name in branches:
            return name

    return "main"


def check_branch_on_remote(repo_dir, branch_name):
    """Check if a branch exists on remote (using local refs after fetch)."""
    # Check if origin/branch_name ref exists locally
    # This is fast because it just checks local refs (after fetch at script start)
    output = run_command(f"git rev-parse --verify origin/{branch_name}", cwd=repo_dir)
    return output is not None and len(output.strip()) > 0


def check_branch_pushed(repo_dir, branch_name):
    """Check if local branch is up to date with remote."""
    if not check_branch_on_remote(repo_dir, branch_name):
        return False

    # Check if there are unpushed commits
    output = run_command(
        f"git rev-list origin/{branch_name}..{branch_name}", cwd=repo_dir
    )
    # If output is empty, branch is up to date with remote
    # If output has commits, there are unpushed changes
    return output is not None and len(output.strip()) == 0


def load_pr_template(repo_dir):
    """Load PR template from .pr_template file if it exists."""
    template_path = os.path.join(repo_dir, ".pr_template")

    if not os.path.isfile(template_path):
        return None

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split into lines
        lines = content.split("\n", 1)

        if len(lines) == 0:
            return None

        # First line is title, rest is body
        title_template = lines[0].strip()
        body_template = lines[1].strip() if len(lines) > 1 else ""

        return {"title": title_template, "body": body_template}

    except Exception as e:
        print(f"Warning: Could not read .pr_template: {e}", file=sys.stderr)
        return None


def select_branch(branches, jira_id):
    """Interactively select a branch from a list."""
    if len(branches) == 0:
        print(f"No branches found matching '{jira_id}'")
        return None

    if len(branches) == 1:
        print(f"Found branch: {branches[0]}")
        return branches[0]

    print(f"\nFound {len(branches)} branches matching '{jira_id}':")
    for i, branch in enumerate(branches, 1):
        print(f"  {i}. {branch}")

    while True:
        try:
            choice = input(f"\nSelect branch (1-{len(branches)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(branches):
                return branches[idx]
            else:
                print(f"Please enter a number between 1 and {len(branches)}")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return None


def create_pr(repo_dir, head_branch, base_branch, jira_id, jira_url):
    """Create a pull request using gh CLI."""
    # Try to load template
    template = load_pr_template(repo_dir)
    branch_suffix = extract_branch_suffix(head_branch, jira_id)

    if template:
        # Extract branch suffix for template variable

        # Replace template variables
        title = template["title"].replace("{JIRA_ID}", jira_id)
        title = title.replace("{JIRA_URL}", jira_url)
        title = title.replace("{BRANCH_SUFFIX}", branch_suffix)

        body = template["body"].replace("{JIRA_ID}", jira_id)
        body = body.replace("{JIRA_URL}", jira_url)
        body = body.replace("{BRANCH_SUFFIX}", branch_suffix)

        print(f"Using PR template from .pr_template")
    else:
        # Use default hardcoded format
        title = f"[{jira_id}]: {branch_suffix}"
        body = f"Jira Ticket: [{jira_id}]({jira_url}) \n\n"

    # Use gh CLI to create PR
    cmd = f'gh pr create --head "{head_branch}" --base "{base_branch}" --title "{title}" --body "{body}"'

    print(f"\nCreating PR:")
    print(f"  From: {head_branch}")
    print(f"  To: {base_branch}")
    print(f"  Jira: {jira_url}")

    result = run_command(cmd, cwd=repo_dir)
    if result:
        print(f"\n✓ Pull request created successfully!")
        print(f"  {result}")
        return result
    else:
        print("\n✗ Failed to create pull request", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Create a GitHub PR from a Jira ticket"
    )
    parser.add_argument("jira_id", help="Jira ticket ID (e.g., PROJ-123)")
    parser.add_argument(
        "--url",
        help="Jira base URL (default: auto-detect from acli)",
        default=os.environ.get("JIRA_BASE_URL", ""),
    )
    parser.add_argument(
        "--dir", help="Repository directory (default: current directory)", default=None
    )
    parser.add_argument(
        "--base",
        help="Base branch for PR (default: auto-detect main/master)",
        default=None,
    )

    args = parser.parse_args()

    # Get Jira URL - try auto-detection first
    jira_url = args.url
    if not jira_url:
        # Try to auto-detect from acli
        jira_url = get_jira_url_from_acli()
        if jira_url:
            print(f"Auto-detected Jira URL from acli: {jira_url}")
        else:
            # Fallback to manual entry
            jira_url = input(
                "Enter Jira base URL (e.g., https://jira.company.com): "
            ).strip()
            if not jira_url:
                print("Error: Jira URL is required", file=sys.stderr)
                sys.exit(1)

    # Ensure URL doesn't end with /
    jira_url = jira_url.rstrip("/")

    # Construct full Jira ticket URL
    jira_ticket_url = f"{jira_url}/browse/{args.jira_id}"

    # Get repository directory
    if args.dir:
        repo_dir = args.dir
    else:
        default_dir = os.getcwd()
        user_input = input(f"Repository directory [{default_dir}]: ").strip()
        repo_dir = user_input if user_input else default_dir

    # Verify directory exists and is a git repo
    if not os.path.isdir(repo_dir):
        print(f"Error: Directory '{repo_dir}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        print(f"Error: Directory '{repo_dir}' is not a git repository", file=sys.stderr)
        sys.exit(1)

    # Fetch once at the start to update remote refs
    print("\nFetching latest remote refs...")
    run_command("git fetch", cwd=repo_dir)

    print(f"\nSearching for branches matching '{args.jira_id}'...")

    # Get all branches
    branches = get_branches(repo_dir)
    if not branches:
        print("Error: Could not retrieve branches", file=sys.stderr)
        sys.exit(1)

    # Find matching branches
    matching_branches = find_matching_branches(branches, args.jira_id)

    # If no matches, check current branch
    if not matching_branches:
        current = get_current_branch(repo_dir)
        if current:
            print(f"\nNo branches found matching '{args.jira_id}'")
            use_current = (
                input(f"Use current branch '{current}'? (y/n): ").strip().lower()
            )
            if use_current == "y":
                matching_branches = [current]

    # Select branch
    selected_branch = select_branch(matching_branches, args.jira_id)
    if not selected_branch:
        sys.exit(1)

    # Check if branch is pushed to remote
    print(f"\nChecking if branch '{selected_branch}' is pushed to remote...")
    branch_on_remote = check_branch_on_remote(repo_dir, selected_branch)

    if not branch_on_remote:
        print(f"\n⚠️  Warning: Branch '{selected_branch}' does not exist on remote!")
        print(
            "   The PR will be created with whatever exists on remote (likely nothing)."
        )
        print("   You may want to push your branch first with: git push -u origin HEAD")
        proceed = input("\nDo you want to proceed anyway? (y/n): ").strip().lower()
        if proceed != "y":
            print("Cancelled.")
            sys.exit(0)
    else:
        # Check if there are unpushed commits
        is_pushed = check_branch_pushed(repo_dir, selected_branch)
        if not is_pushed:
            print(f"\n⚠️  Warning: Branch '{selected_branch}' has unpushed commits!")
            print("   The PR will only include commits that are already on remote.")
            print("   You may want to push your changes first with: git push")
            proceed = input("\nDo you want to proceed anyway? (y/n): ").strip().lower()
            if proceed != "y":
                print("Cancelled.")
                sys.exit(0)
        else:
            print(f"✓ Branch '{selected_branch}' is up to date with remote")

    # Get base branch
    base_branch = args.base if args.base else get_default_branch(repo_dir)
    print(f"Base branch: {base_branch}")

    # Create PR
    pr_url = create_pr(
        repo_dir, selected_branch, base_branch, args.jira_id, jira_ticket_url
    )

    if not pr_url:
        sys.exit(1)


if __name__ == "__main__":
    main()
