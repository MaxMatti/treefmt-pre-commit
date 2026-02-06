"""treefmt pre-commit hook package."""

from importlib.metadata import version, PackageNotFoundError


def _get_version() -> str:
    """Get package version from installed metadata."""
    try:
        return version("treefmt-pre-commit")
    except PackageNotFoundError:
        # Fallback for development environment
        import tomllib
        from pathlib import Path

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
            return pyproject["project"]["version"]
        except FileNotFoundError:
            return "unknown"


__version__ = _get_version()
