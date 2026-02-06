#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "packaging==23.1",
# ]
# ///
"""Manage version bumps and releases for treefmt-pre-commit.

This script:
- Reads the latest git tag to determine the current version
- Increments the 4th digit (tool version) automatically
- Updates pyproject.toml, README.md, and .pre-commit-config.yaml from templates
- Creates a git commit and annotated tag
- Optionally pushes changes to remote

The version scheme is MAJOR.MINOR.PATCH.TOOL_VERSION where:
- First 3 digits: treefmt binary version (managed by mirror.py)
- 4th digit: tool wrapper version (managed by this script)

Templates are stored in version-templates/ with {version} placeholders.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from packaging.version import Version


def main():
    parser = argparse.ArgumentParser(
        description="Bump version and create release tag",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Auto-increment 4th digit from latest tag
  %(prog)s --version 2.4.0.10       # Manually specify version
  %(prog)s --dry-run                # Preview changes without committing
  %(prog)s --push                   # Also push commit and tag to remote
  %(prog)s --no-commit              # Update files only, no git operations
        """,
    )
    parser.add_argument(
        "--version",
        help="Manually specify version (must be X.Y.Z.R format with 4 parts)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push commit and tag to remote after creating them",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Update files only, don't create commit or tag",
    )
    args = parser.parse_args()

    if args.push and args.no_commit:
        print("Error: --push and --no-commit are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    # Verify git working directory is clean (unless --no-commit)
    if not args.no_commit and not args.dry_run:
        if not check_git_clean():
            print(
                "Error: Git working directory is not clean. "
                "Commit or stash changes first.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Determine target version
    if args.version:
        if not validate_version(args.version):
            print(
                f"Error: Invalid version format '{args.version}'. "
                "Must be X.Y.Z.R with 4 parts.",
                file=sys.stderr,
            )
            sys.exit(1)
        target_version = args.version
    else:
        current_version = get_latest_tag_version()
        if current_version is None:
            print(
                "Error: No existing tags found. Use --version to specify initial version.",
                file=sys.stderr,
            )
            sys.exit(1)
        target_version = increment_version(current_version)

    # Check if tag already exists
    if not args.dry_run and tag_exists(target_version):
        print(f"Error: Tag v{target_version} already exists.", file=sys.stderr)
        sys.exit(1)

    print(f"Target version: {target_version}")

    # Check for manual changes to managed files (unless dry-run or no-commit)
    if not args.dry_run and not args.no_commit:
        current_version = get_latest_tag_version()
        if current_version is not None:
            files_with_changes = check_for_manual_changes(current_version)
            if files_with_changes:
                print(
                    "\nError: The following files have manual changes that would be lost:",
                    file=sys.stderr,
                )
                for file in sorted(files_with_changes):
                    print(f"  - {file}", file=sys.stderr)
                print(
                    "\nThese files are managed by templates in version-templates/",
                    file=sys.stderr,
                )
                print(
                    "Please update the corresponding template files instead of editing them directly.",
                    file=sys.stderr,
                )
                print(
                    "\nTo fix this:",
                    file=sys.stderr,
                )
                print(
                    "  1. Copy your changes to the corresponding file in version-templates/",
                    file=sys.stderr,
                )
                print(
                    "  2. Run this script again",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Discover template files
    template_dir = Path("version-templates")
    template_files = []
    for root, dirs, files in os.walk(template_dir):
        for filename in files:
            template_path = Path(root) / filename
            rel_path = template_path.relative_to(template_dir)
            template_files.append(str(rel_path))

    if args.dry_run:
        print("\nDry run - would update the following files:")
        for file in sorted(template_files):
            print(f"  - {file}")
        print(f"\nWould create commit: 'Bump version to {target_version}'")
        print(f"Would create tag: v{target_version}")
        if args.push:
            print("Would push commit and tag to remote")
        return

    # Update all files from templates
    updated_files = update_template_files(target_version)

    print("\nUpdated files:")
    for file in sorted(updated_files):
        print(f"  ✓ {file}")

    # Git operations
    if not args.no_commit:
        create_commit(target_version, updated_files)
        print(f"\n✓ Created commit: 'Bump version to {target_version}'")

        create_tag(target_version)
        print(f"✓ Created tag: v{target_version}")

        if args.push:
            push_changes(target_version)
            print("\n✓ Pushed commit and tag to remote")
        else:
            print(
                f"\nTo push changes, run:\n"
                f"  git push origin main\n"
                f"  git push origin v{target_version}"
            )
    else:
        print("\nFiles updated. Skipped git commit and tag creation.")


def get_latest_tag_version() -> str | None:
    """Get the latest version from git tags.

    Returns version string like "2.4.0.4" or None if no tags exist.
    Handles both 3-digit (from mirror.py) and 4-digit (from publish.py) versions.
    """
    try:
        result = subprocess.run(
            ["git", "tag", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get git tags: {e}", file=sys.stderr)
        sys.exit(1)

    tags = result.stdout.strip().split("\n")
    if not tags or tags == [""]:
        return None

    versions = []
    for tag in tags:
        # Remove 'v' prefix if present
        version_str = tag.lstrip("v")
        try:
            # Use packaging.Version for robust parsing
            versions.append(Version(version_str))
        except Exception:
            # Skip invalid version tags
            continue

    if not versions:
        return None

    # Get the highest version
    latest = max(versions)
    version_str = str(latest)

    # Ensure we have 4 parts (handle 3-digit versions from mirror.py)
    parts = version_str.split(".")
    if len(parts) == 3:
        # This is from mirror.py, needs .0 appended for first tool version
        version_str = f"{version_str}.0"

    return version_str


def increment_version(current_version: str) -> str:
    """Increment the 4th digit (tool version).

    Args:
        current_version: Version string like "2.4.0.4"

    Returns:
        Incremented version like "2.4.0.5"
    """
    parts = current_version.split(".")
    if len(parts) != 4:
        print(
            f"Error: Cannot increment version '{current_version}' - must have 4 parts",
            file=sys.stderr,
        )
        sys.exit(1)

    parts[3] = str(int(parts[3]) + 1)
    return ".".join(parts)


def validate_version(version: str) -> bool:
    """Check if version is valid X.Y.Z.R format with 4 parts."""
    parts = version.split(".")
    if len(parts) != 4:
        return False

    try:
        for part in parts:
            if int(part) < 0:
                return False
    except ValueError:
        return False

    return True


def check_git_clean() -> bool:
    """Check if git working directory is clean."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == ""
    except subprocess.CalledProcessError:
        return False


def tag_exists(version: str) -> bool:
    """Check if a git tag already exists for this version."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", f"v{version}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() != ""
    except subprocess.CalledProcessError:
        return False


def check_for_manual_changes(current_version: str) -> list[str]:
    """Check if managed files have manual changes that would be lost.

    Generates files from templates using the current version and compares
    them to actual file content. This detects manual changes that weren't
    made to the templates.

    Args:
        current_version: Current version string like "2.4.0.15"

    Returns:
        List of file paths that have unexpected manual changes
    """
    template_dir = Path("version-templates")
    files_with_changes = []

    for root, dirs, files in os.walk(template_dir):
        for filename in files:
            template_path = Path(root) / filename
            # Get relative path from template_dir
            rel_path = template_path.relative_to(template_dir)
            # Output to same relative path in main directory
            output_path = Path(rel_path.with_suffix(""))

            # Skip if the actual file doesn't exist yet
            if not output_path.exists():
                continue

            # Read template and replace version placeholder with CURRENT version
            template_content = template_path.read_text()
            expected_content = template_content.replace("{version}", current_version)

            # Read actual file content
            actual_content = output_path.read_text()

            # Compare normalized content (to handle line ending differences)
            expected_normalized = expected_content.replace("\r\n", "\n")
            actual_normalized = actual_content.replace("\r\n", "\n")

            if expected_normalized != actual_normalized:
                files_with_changes.append(str(output_path))

    return files_with_changes


def update_template_files(version: str) -> list[str]:
    """Update all files from version-templates directory.

    Walks through version-templates/ and for each file:
    - Reads the template
    - Replaces {version} placeholder
    - Writes to corresponding path in main directory

    Returns:
        List of updated file paths (relative to repo root)
    """
    template_dir = Path("version-templates")
    updated_files = []

    for root, dirs, files in os.walk(template_dir):
        for filename in files:
            template_path = Path(root) / filename
            # Get relative path from template_dir
            rel_path = template_path.relative_to(template_dir)
            # Output to same relative path in main directory
            output_path = Path(rel_path.with_suffix(""))

            # Read template and replace version placeholder
            content = template_path.read_text()
            new_content = content.replace("{version}", version)

            # Write to output file
            output_path.write_text(new_content)
            updated_files.append(str(output_path))

    return updated_files


def create_commit(version: str, files: list[str]):
    """Create git commit with updated files."""
    try:
        subprocess.run(["git", "add", *files], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Bump version to {version}"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to create commit: {e}", file=sys.stderr)
        sys.exit(1)


def create_tag(version: str):
    """Create annotated git tag."""
    try:
        subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to create tag: {e}", file=sys.stderr)
        sys.exit(1)


def push_changes(version: str):
    """Push commit and tag to remote."""
    try:
        # Get current branch name
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        # Push commit
        subprocess.run(["git", "push", "origin", branch], check=True)

        # Push tag
        subprocess.run(["git", "push", "origin", f"v{version}"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to push changes: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
