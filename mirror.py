# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "packaging==23.1",
#   "urllib3==2.0.5",
# ]
# ///
"""Update treefmt-pre-commit to the latest version of treefmt."""

import re
import subprocess
import tomllib
import typing
from pathlib import Path

import urllib3
from packaging.version import Version


def main():
    with open(Path(__file__).parent / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    all_versions = get_all_versions()
    current_version = get_current_version(pyproject=pyproject)
    target_versions = [v for v in all_versions if v > current_version]

    for version in target_versions:
        paths = process_version(version)
        if subprocess.check_output(["git", "status", "-s"]).strip():
            subprocess.run(["git", "add", *paths], check=True)
            subprocess.run(["git", "commit", "-m", f"Mirror: {version}"], check=True)
            subprocess.run(["git", "tag", f"v{version}"], check=True)
        else:
            print(f"No change v{version}")


def get_all_versions() -> list[Version]:
    """Fetch all treefmt versions from GitHub releases."""
    http = urllib3.PoolManager()
    response = http.request(
        "GET",
        "https://api.github.com/repos/numtide/treefmt/releases",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "treefmt-pre-commit-mirror",
        },
    )

    if response.status != 200:
        raise RuntimeError(
            f"Failed to fetch versions from GitHub: HTTP {response.status}"
        )

    import json

    releases = json.loads(response.data.decode("utf-8"))

    # Filter out pre-releases and parse version tags
    versions = []
    for release in releases:
        if release.get("prerelease", False) or release.get("draft", False):
            continue

        tag_name = release["tag_name"]
        # Remove 'v' prefix if present
        version_str = tag_name.lstrip("v")

        try:
            versions.append(Version(version_str))
        except Exception as e:
            print(f"Warning: Could not parse version from tag {tag_name}: {e}")
            continue

    return sorted(versions)


def get_current_version(pyproject: dict) -> Version:
    """Get current version from pyproject.toml."""
    version_str = pyproject["project"]["version"]
    return Version(version_str)


def process_version(version: Version) -> typing.Sequence[str]:
    """Update files with new version."""

    def replace_pyproject_toml(content: str) -> str:
        return re.sub(r'version = ".*"', f'version = "{version}"', content)

    def replace_readme_md(content: str) -> str:
        # Update the rev: line in YAML examples
        content = re.sub(r"rev: v\d+\.\d+\.\d+", f"rev: v{version}", content)
        # Update any version badges or references
        content = re.sub(r"treefmt/\d+\.\d+\.\d+", f"treefmt/{version}", content)
        return content

    paths = {
        "pyproject.toml": replace_pyproject_toml,
        "README.md": replace_readme_md,
    }

    for path, replacer in paths.items():
        with open(path) as f:
            content = replacer(f.read())
        with open(path, mode="w") as f:
            f.write(content)

    return tuple(paths.keys())


if __name__ == "__main__":
    main()
