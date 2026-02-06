"""Main entry point for treefmt pre-commit hook."""

import io
import os
import platform
import sys
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

TREEFMT_VERSION = "2.4.0"
GITHUB_RELEASE_URL = "https://github.com/numtide/treefmt/releases/download"
LOCK_TIMEOUT = 60  # Maximum time to wait for lock in seconds


def get_cache_dir() -> Path:
    """Get the cache directory for treefmt binaries."""
    # Use XDG_CACHE_HOME if available, otherwise use platform-specific cache
    if cache_home := os.environ.get("XDG_CACHE_HOME"):
        cache_dir = Path(cache_home)
    elif sys.platform == "darwin":
        cache_dir = Path.home() / "Library" / "Caches"
    elif sys.platform == "win32":
        cache_dir = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
    else:
        cache_dir = Path.home() / ".cache"

    return cache_dir / "treefmt-pre-commit" / TREEFMT_VERSION


def get_platform_info() -> tuple[str, str]:
    """Get platform-specific asset name."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "arm64":
            return ("darwin", "arm64")
        else:
            return ("darwin", "amd64")
    elif system == "linux":
        if machine == "aarch64":
            return ("linux", "arm64")
        elif machine in ("x86_64", "amd64"):
            return ("linux", "amd64")

    raise RuntimeError(f"Unsupported platform: {system} {machine}")


def acquire_lock(lock_path: Path) -> bool:
    """Try to acquire a lock file. Returns True if acquired, False otherwise."""
    try:
        # Try to create lock file exclusively
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock(lock_path: Path) -> None:
    """Release the lock file."""
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def wait_for_lock(lock_path: Path, timeout: float = LOCK_TIMEOUT) -> None:
    """Wait for lock to be released, with timeout."""
    start_time = time.time()
    while lock_path.exists():
        if time.time() - start_time > timeout:
            raise RuntimeError(f"Timeout waiting for lock: {lock_path}")
        time.sleep(0.1)


def download_treefmt() -> Path:
    """Download treefmt binary if not cached."""
    cache_dir = get_cache_dir()
    binary_path = cache_dir / "treefmt"
    lock_path = cache_dir / ".treefmt.lock"

    # Quick check without lock - return immediately if binary exists
    if binary_path.exists():
        return binary_path

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Try to acquire lock
    if not acquire_lock(lock_path):
        # Another process is downloading, wait for it to finish
        wait_for_lock(lock_path)
        # After lock is released, binary should exist
        if binary_path.exists():
            return binary_path
        # If not, try to acquire lock ourselves
        if not acquire_lock(lock_path):
            raise RuntimeError("Failed to acquire lock after waiting")

    try:
        # Double-check binary doesn't exist (another process might have created it)
        if binary_path.exists():
            return binary_path

        # Download and extract
        system, arch = get_platform_info()
        asset_name = f"treefmt_{TREEFMT_VERSION}_{system}_{arch}.tar.gz"
        url = f"{GITHUB_RELEASE_URL}/v{TREEFMT_VERSION}/{asset_name}"

        print(f"Downloading treefmt from {url}...", file=sys.stderr)

        try:
            with urlopen(url, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to download: HTTP {response.status}")
                data = response.read()
        except Exception as e:
            raise RuntimeError(f"Failed to download treefmt: {e}")

        # Extract binary from tar.gz to a temporary file first
        temp_path = cache_dir / f".treefmt.tmp.{os.getpid()}"
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                member = tar.getmember("treefmt")
                f = tar.extractfile(member)
                if f is None:
                    raise RuntimeError("Could not extract treefmt from archive")

                # Write to temporary file
                with open(temp_path, "wb") as out:
                    out.write(f.read())

                os.chmod(temp_path, 0o755)

                # Atomically move to final location
                temp_path.rename(binary_path)
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to extract treefmt: {e}")

        print(f"treefmt installed to {binary_path}", file=sys.stderr)
        return binary_path
    finally:
        # Always release lock
        release_lock(lock_path)


def main():
    """Main entry point - download treefmt if needed and execute it."""
    try:
        binary_path = download_treefmt()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Execute treefmt with the same arguments
    os.execv(binary_path, [str(binary_path)] + sys.argv[1:])


if __name__ == "__main__":
    main()
