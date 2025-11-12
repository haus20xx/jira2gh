#!/usr/bin/env python3
"""
Orchestrate the workflow of selecting a Jira ticket and creating a PR.
"""
import subprocess
import sys
import json
import argparse
import os


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
            errors="ignore"
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr if hasattr(e, "stderr") else ""
        print(f"Error: {stderr}", file=sys.stderr)
        return None


def get_current_branch(repo_dir):
    """Get the current branch name from a git repository."""
    if not repo_dir or not os.path.isdir(os.path.join(repo_dir, ".git")):
        return None
    return run_command("git branch --show-current", cwd=repo_dir)


def prioritize_items_by_branch(items, current_branch):
    """Reorder items to prioritize those matching the current branch."""
    if not current_branch or not items:
        return items

    matching_items = []
    other_items = []

    for item in items:
        jira_key = item.get("key", "")
        # Check if the Jira key appears in the branch name (case insensitive)
        if jira_key.lower() in current_branch.lower():
            matching_items.append(item)
        else:
            other_items.append(item)

    # Return matching items first, then others
    return matching_items + other_items


def get_active_sprint_items(board_id=None):
    """Get active sprint items using list_sprint_items.py."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "list_sprint_items.py")

    # Build command
    cmd = f"python3 {script_path} -j"
    if board_id:
        cmd += f" -b {board_id}"

    print("Fetching active sprint items...\n")
    output = run_command(cmd)
    if not output:
        return None

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print("Error: Failed to parse sprint items", file=sys.stderr)
        return None


def display_and_select_item(items, current_branch=None):
    """Display items and let user select one."""
    if not items or len(items) == 0:
        print("No active items found in your sprints.")
        return None

    print(f"Active sprint items ({len(items)}):\n")
    for i, item in enumerate(items, 1):
        jira_key = item["key"]
        # Check if this item matches current branch
        matches_branch = (
            current_branch
            and jira_key.lower() in current_branch.lower()
        )
        marker = " [Current Branch]" if matches_branch else ""

        print(f"  {i}. [{jira_key}] {item['summary']}{marker}")
        print(
            f"     Sprint: {item['sprint_name']} | Status: {item['status']} | Priority: {item['priority']}"
        )
        print()

    while True:
        try:
            choice = input(
                f"Select item to create PR for (1-{len(items)}, or 'q' to quit): "
            ).strip()
            if choice.lower() == "q":
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
            else:
                print(f"Please enter a number between 1 and {len(items)}")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None


def create_pr_for_item(jira_key, jira_url, repo_dir, base_branch):
    """Create PR using create_jira_pr.py."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "create_jira_pr.py")

    # Build command
    cmd = f"python3 {script_path} {jira_key}"

    if jira_url:
        cmd += f' --url "{jira_url}"'

    if repo_dir:
        cmd += f' --dir "{repo_dir}"'

    if base_branch:
        cmd += f' --base "{base_branch}"'

    print(f"\nCreating PR for {jira_key}...")

    # Run the command interactively so user can see prompts
    result = subprocess.run(cmd, shell=True)

    if result.returncode == 0:
        return True
    else:
        print(f"\nFailed to create PR for {jira_key}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Select a Jira ticket from active sprints and create a PR"
    )
    parser.add_argument(
        "-b", "--board",
        type=int,
        metavar="BOARD_ID",
        help="Query only the specified board ID"
    )
    parser.add_argument(
        "--url",
        help="Jira base URL (default: auto-detect from acli)",
        default=os.environ.get("JIRA_BASE_URL", "")
    )
    parser.add_argument(
        "--dir",
        help="Repository directory for PR creation",
        default=None
    )
    parser.add_argument(
        "--base",
        help="Base branch for PR (default: auto-detect main/master)",
        default=None
    )

    args = parser.parse_args()

    # Get repository directory first to check current branch
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

    # Get current branch
    current_branch = get_current_branch(repo_dir)
    if current_branch:
        print(f"Current branch: {current_branch}\n")

    # Get active sprint items
    data = get_active_sprint_items(board_id=args.board)
    if not data:
        sys.exit(1)

    items = data.get("items", [])

    # Prioritize items that match the current branch
    if current_branch:
        items = prioritize_items_by_branch(items, current_branch)

    # Let user select an item
    selected_item = display_and_select_item(items, current_branch)
    if not selected_item:
        print("\nNo item selected.")
        sys.exit(0)

    print(f"\nSelected: [{selected_item['key']}] {selected_item['summary']}")

    # Create PR for the selected item
    success = create_pr_for_item(
        jira_key=selected_item["key"],
        jira_url=args.url,
        repo_dir=repo_dir,
        base_branch=args.base,
    )

    if success:
        print("\n✓ Workflow complete!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
