"""Build script for creating platform-specific wheels with treefmt binaries."""

import argparse
import io
import os
import platform
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path
from urllib.request import urlopen

# Version of treefmt binary to download from GitHub releases
TREEFMT_VERSION = "2.4.0"


def get_package_version() -> str:
    """Read package version from pyproject.toml."""
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]["version"]


GITHUB_RELEASE_URL = "https://github.com/numtide/treefmt/releases/download"

# Mapping from Python platform tags to treefmt release asset name templates
# The {version} placeholder will be replaced with the actual version
PLATFORM_MAPPING = {
    "macosx_10_9_x86_64": "treefmt_{version}_darwin_amd64.tar.gz",
    "macosx_11_0_arm64": "treefmt_{version}_darwin_arm64.tar.gz",
    "manylinux_2_17_x86_64": "treefmt_{version}_linux_amd64.tar.gz",
    "manylinux_2_17_aarch64": "treefmt_{version}_linux_arm64.tar.gz",
}


def download_binary(version: str, asset_name: str) -> bytes:
    """Download treefmt binary from GitHub releases."""
    url = f"{GITHUB_RELEASE_URL}/v{version}/{asset_name}"
    print(f"Downloading {url}...", file=sys.stderr)

    with urlopen(url) as response:
        if response.status != 200:
            raise RuntimeError(f"Failed to download {url}: HTTP {response.status}")
        return response.read()


def extract_binary(data: bytes, asset_name: str) -> bytes:
    """Extract treefmt binary from archive."""
    if asset_name.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            # The binary is named "treefmt" in the archive
            member = tar.getmember("treefmt")
            f = tar.extractfile(member)
            if f is None:
                raise RuntimeError("Could not extract treefmt from archive")
            return f.read()
    else:
        raise RuntimeError(f"Unknown archive format: {asset_name}")


def get_current_platform() -> str:
    """Determine the current platform tag."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "arm64":
            return "macosx_11_0_arm64"
        else:
            return "macosx_10_9_x86_64"
    elif system == "linux":
        if machine == "aarch64":
            return "manylinux_2_17_aarch64"
        else:
            return "manylinux_2_17_x86_64"
    elif system == "windows":
        return "win_amd64"
    else:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")


def create_wheel_for_platform(
    package_version: str,
    treefmt_version: str,
    platform_tag: str,
    output_dir: Path,
) -> Path:
    """Create a platform-specific wheel with the treefmt binary."""
    asset_name = PLATFORM_MAPPING[platform_tag].format(version=treefmt_version)

    # Download and extract binary
    data = download_binary(treefmt_version, asset_name)
    binary_data = extract_binary(data, asset_name)

    # Create temporary directory for wheel contents
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create wheel structure
        pkg_info_dir = tmppath / "treefmt_pre_commit.egg-info"
        pkg_info_dir.mkdir(parents=True)

        # Write PKG-INFO
        with open(pkg_info_dir / "PKG-INFO", "w") as f:
            f.write(
                f"""Metadata-Version: 2.1
Name: treefmt-pre-commit
Version: {package_version}
Summary: Pre-commit hooks for treefmt
Home-page: https://github.com/MaxMatti/treefmt-pre-commit
License: MIT OR Apache-2.0
"""
            )

        # Write SOURCES.txt
        with open(pkg_info_dir / "SOURCES.txt", "w") as f:
            f.write("PKG-INFO\n")

        # Write top_level.txt
        with open(pkg_info_dir / "top_level.txt", "w") as f:
            f.write("treefmt_pre_commit\n")

        # Create scripts directory for the binary
        scripts_dir = tmppath / "treefmt_pre_commit.data" / "scripts"
        scripts_dir.mkdir(parents=True)

        # Write binary
        binary_name = "treefmt"
        binary_path = scripts_dir / binary_name
        with open(binary_path, "wb") as f:
            f.write(binary_data)

        # Make binary executable
        os.chmod(binary_path, 0o755)

        # Create wheel file
        output_dir.mkdir(parents=True, exist_ok=True)
        wheel_name = f"treefmt_pre_commit-{package_version}-py3-none-{platform_tag}.whl"
        wheel_path = output_dir / wheel_name

        print(f"Creating wheel: {wheel_name}", file=sys.stderr)

        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as whl:
            for root, dirs, files in os.walk(tmppath):
                for file in files:
                    filepath = Path(root) / file
                    arcname = filepath.relative_to(tmppath)
                    whl.write(filepath, arcname)

            # Write WHEEL metadata
            wheel_metadata = f"""Wheel-Version: 1.0
Generator: treefmt-pre-commit-build
Root-Is-Purelib: false
Tag: py3-none-{platform_tag}
"""
            whl.writestr(
                f"treefmt_pre_commit-{package_version}.dist-info/WHEEL",
                wheel_metadata,
            )

            # Write METADATA
            whl.writestr(
                f"treefmt_pre_commit-{package_version}.dist-info/METADATA",
                f"""Metadata-Version: 2.1
Name: treefmt-pre-commit
Version: {package_version}
Summary: Pre-commit hooks for treefmt
Home-page: https://github.com/MaxMatti/treefmt-pre-commit
License: MIT OR Apache-2.0
Platform: {platform_tag}
""",
            )

            # Write RECORD (simplified - just listing files)
            record_lines = []
            for root, dirs, files in os.walk(tmppath):
                for file in files:
                    filepath = Path(root) / file
                    arcname = filepath.relative_to(tmppath)
                    record_lines.append(f"{arcname},,\n")

            record_lines.append(
                f"treefmt_pre_commit-{package_version}.dist-info/WHEEL,,\n"
            )
            record_lines.append(
                f"treefmt_pre_commit-{package_version}.dist-info/METADATA,,\n"
            )
            record_lines.append(
                f"treefmt_pre_commit-{package_version}.dist-info/RECORD,,\n"
            )

            whl.writestr(
                f"treefmt_pre_commit-{package_version}.dist-info/RECORD",
                "".join(record_lines),
            )

    return wheel_path


def main():
    parser = argparse.ArgumentParser(
        description="Build platform-specific wheels for treefmt-pre-commit"
    )
    parser.add_argument(
        "--package-version",
        default=get_package_version(),
        help="Package version for wheel metadata (default: read from pyproject.toml)",
    )
    parser.add_argument(
        "--treefmt-version",
        default=TREEFMT_VERSION,
        help=f"treefmt binary version to download (default: {TREEFMT_VERSION})",
    )
    parser.add_argument(
        "--version",
        help="Alias for --package-version (for backwards compatibility)",
    )
    parser.add_argument(
        "--platform",
        choices=list(PLATFORM_MAPPING.keys()) + ["current", "all"],
        default="current",
        help="Platform to build for (default: current)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for wheels (default: dist)",
    )

    args = parser.parse_args()

    # Handle backwards compatibility: --version is alias for --package-version
    package_version = args.version if args.version else args.package_version
    treefmt_version = args.treefmt_version

    if args.platform == "all":
        platforms = list(PLATFORM_MAPPING.keys())
    elif args.platform == "current":
        platforms = [get_current_platform()]
    else:
        platforms = [args.platform]

    print(f"Building wheels for package version {package_version}", file=sys.stderr)
    print(f"Using treefmt binary version {treefmt_version}", file=sys.stderr)
    print(f"Platforms: {', '.join(platforms)}", file=sys.stderr)

    for platform_tag in platforms:
        try:
            wheel_path = create_wheel_for_platform(
                package_version,
                treefmt_version,
                platform_tag,
                args.output_dir,
            )
            print(f"Successfully created: {wheel_path}")
        except Exception as e:
            print(f"Failed to build wheel for {platform_tag}: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
