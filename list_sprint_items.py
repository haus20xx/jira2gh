#!/usr/bin/env python3
"""
List active work items in current sprints using acli.
"""
import subprocess
import json
import sys
import argparse
from typing import List, Dict, Tuple


def run_acli(command: str) -> Dict:
    """Execute ACLI command and return parsed JSON response."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error parsing JSON response", file=sys.stderr)
        sys.exit(1)


def get_boards() -> List[Dict]:
    """Get all available boards."""
    command = "acli jira board search --json"
    response = run_acli(command)
    return response.get("values", [])


def get_active_sprints(board_id: int) -> List[Dict]:
    """Get active sprints for a board."""
    command = f"acli jira board list-sprints --id {board_id} --state active --json"
    response = run_acli(command)
    return response.get("sprints", [])


def get_sprint_items(
    sprint_id: int, board_id: int, current_user_only: bool = False
) -> List[Dict]:
    """Get work items for a sprint, optionally filtered to current user."""
    jql_filter = "assignee = currentUser()" if current_user_only else ""
    jql_param = f'--jql "{jql_filter}"' if jql_filter else ""
    command = f"acli jira sprint list-workitems --sprint {sprint_id} --board {board_id} {jql_param} --json"
    response = run_acli(command)
    return response.get("issues", [])


def categorize_items(issues: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Categorize issues as open or closed based on status category."""
    open_items = []
    closed_items = []

    for issue in issues:
        status_key = issue["fields"]["status"]["statusCategory"]["key"]
        item = {
            "key": issue["key"],
            "summary": issue["fields"]["summary"],
            "type": issue["fields"]["issuetype"]["name"],
            "status": issue["fields"]["status"]["name"],
            "priority": issue["fields"]["priority"]["name"],
            "assignee": (
                issue["fields"]["assignee"]["displayName"]
                if issue["fields"].get("assignee")
                else "Unassigned"
            ),
        }

        if status_key == "done":
            closed_items.append(item)
        else:  # 'new' or 'indeterminate'
            open_items.append(item)

    return open_items, closed_items


def main():
    """Main function to list active sprint items."""
    parser = argparse.ArgumentParser(
        description="List active work items in current sprints using acli"
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print final summary, suppress detailed output",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output results as JSON for piping to other processes",
    )
    parser.add_argument(
        "-b",
        "--board",
        type=int,
        metavar="BOARD_ID",
        help="Query only the specified board ID instead of all boards",
    )
    args = parser.parse_args()

    verbose = not args.quiet and not args.json

    if verbose:
        print("Fetching boards and active sprints...\n")

    # Determine which boards to process
    if args.board:
        # Query specific board only
        boards_to_process = [{"id": args.board, "name": f"Board {args.board}", "type": "scrum"}]
    else:
        # Query all boards
        boards = get_boards()
        if not boards:
            print("No boards found.")
            return
        boards_to_process = boards

    total_open_items = 0
    all_open_items = []

    for board in boards_to_process:
        board_id = board["id"]
        board_name = board["name"]
        board_type = board.get("type", "scrum")  # Assume scrum if type not provided

        # Only process scrum boards (they have sprints)
        if board_type != "scrum" and not args.board:
            continue

        sprints = get_active_sprints(board_id)

        if not sprints:
            continue

        if verbose:
            print(f"Board: {board_name} (ID: {board_id})")
            print("=" * 80)

        for sprint in sprints:
            sprint_id = sprint["id"]
            sprint_name = sprint["name"]

            # Get all items in the sprint
            items = get_sprint_items(sprint_id, board_id, current_user_only=True)

            if not items:
                if verbose:
                    print(f"\n  Sprint: {sprint_name}")
                    print(f"  No items in this sprint\n")
                continue

            # Categorize items
            open_items, closed_items = categorize_items(items)

            total_open_items += len(open_items)

            # Store items with sprint context for quiet mode
            for item in open_items:
                item['sprint_name'] = sprint_name
                item['board_name'] = board_name
                all_open_items.append(item)

            if verbose:
                print(f"\n  Sprint: {sprint_name}")
                print(f"  Active Items: {len(open_items)} | Completed: {len(closed_items)}")
                print(f"  " + "-" * 76)

                if open_items:
                    for item in open_items:
                        print(f"    [{item['key']}] {item['summary']}")
                        print(
                            f"      Type: {item['type']} | Status: {item['status']} | Priority: {item['priority']}"
                        )
                        print(f"      Assignee: {item['assignee']}")
                        print()
                else:
                    print(f"    No active items\n")

        if verbose:
            print()

    # Print summary based on output mode
    if args.json:
        # Output as JSON for piping
        output = {
            "total_active_items": total_open_items,
            "items": all_open_items
        }
        print(json.dumps(output, indent=2))
    elif args.quiet and all_open_items:
        print(f"Active items across all sprints: {total_open_items}\n")
        for item in all_open_items:
            print(f"[{item['key']}] {item['summary']}")
            print(f"  Sprint: {item['sprint_name']} | Board: {item['board_name']}")
            print(f"  Type: {item['type']} | Status: {item['status']} | Priority: {item['priority']}")
            print()
    elif args.quiet:
        print(f"Total active items across all sprints: {total_open_items}")
    else:
        print(f"\nTotal active items across all sprints: {total_open_items}")


if __name__ == "__main__":
    main()
