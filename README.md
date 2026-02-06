# This project is not ready to use yet.

I'm developing it live of github instead of locally because it uses lots of github actions.

# Below is the vibe-coded README:

# treefmt-pre-commit

[![Actions status](https://github.com/MaxMatti/treefmt-pre-commit/workflows/main/badge.svg)](https://github.com/MaxMatti/treefmt-pre-commit/actions)
[![PyPI](https://img.shields.io/pypi/v/treefmt-pre-commit.svg)](https://pypi.org/project/treefmt-pre-commit/)

A [pre-commit](https://pre-commit.com/) hook for [treefmt](https://github.com/numtide/treefmt).

Distributed as a standalone repository to enable installing treefmt via prebuilt wheels from [PyPI](https://pypi.org/project/treefmt-pre-commit/).

## What is treefmt?

[treefmt](https://github.com/numtide/treefmt) is a language-agnostic formatter multiplexer that allows you to run multiple formatters in parallel with a single command. It's designed to be fast, incremental, and easy to configure.

Unlike language-specific formatters, treefmt can format your entire codebase - Python, JavaScript, Go, Rust, Markdown, YAML, and more - with one tool.

## Installation

### Using pre-commit

Add the following to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt
```

This will automatically install treefmt and run it on your files.

## Available Hooks

### `treefmt`

Formats files automatically using treefmt.

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt
```

This hook will:

- Format files in place
- Pass filenames to treefmt for efficient incremental formatting
- Allow the commit to proceed

### `treefmt-check`

Checks if files need formatting without modifying them. Useful for CI pipelines.

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt-check
```

This hook will:

- Check if any files need formatting
- Fail the commit if files are not formatted
- Not modify any files

## Configuration

treefmt requires a `treefmt.toml` configuration file in your repository root. This file defines which formatters to run and on which files.

### Example `treefmt.toml`

```toml
# Format Python files with ruff
[formatter.ruff]
command = "ruff"
options = ["format"]
includes = ["*.py"]

# Format JavaScript/TypeScript with prettier
[formatter.prettier]
command = "prettier"
options = ["--write"]
includes = ["*.js", "*.ts", "*.json", "*.md"]

# Format Rust code
[formatter.rustfmt]
command = "rustfmt"
options = ["--edition", "2021"]
includes = ["*.rs"]
```

For more configuration options and formatters, see the [treefmt documentation](https://numtide.github.io/treefmt/).

## Usage Examples

### Basic Usage

Format all files:

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt
```

### CI/CD Pipeline

Use the check mode in CI to ensure all files are formatted:

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt-check
```

In your CI configuration (e.g., `.github/workflows/ci.yml`):

```yaml
- name: Check formatting
  run: pre-commit run treefmt-check --all-files
```

### Excluding Files

treefmt respects the `excludes` configuration in your `treefmt.toml`:

```toml
[formatter.prettier]
command = "prettier"
options = ["--write"]
includes = ["*.js", "*.ts"]
excludes = ["node_modules", "dist"]
```

### Using with Specific File Types

You can limit which files pre-commit passes to treefmt:

```yaml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt
        files: \.(py|js|ts|md)$
```

## How It Works

This repository packages the official treefmt binary into Python wheels for easy installation. When you use these pre-commit hooks:

1. The treefmt binary is automatically downloaded and installed via pip
2. Pre-commit runs treefmt on your staged files
3. treefmt determines which formatters to run based on your `treefmt.toml`
4. All applicable formatters run in parallel for maximum speed

## Advantages Over Direct Formatter Hooks

Instead of configuring multiple pre-commit hooks for different formatters:

```yaml
# Without treefmt - multiple hooks to configure
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.0.0
    hooks:
      - id: prettier
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.0.0
    hooks:
      - id: eslint
```

You can use a single treefmt hook:

```yaml
# With treefmt - single hook, configured in treefmt.toml
repos:
  - repo: https://github.com/MaxMatti/treefmt-pre-commit
    rev: v2.4.0.19
    hooks:
      - id: treefmt
```

Benefits:

- **Parallel execution**: All formatters run simultaneously
- **Incremental formatting**: Only changed files are processed
- **Single source of truth**: All formatter configuration in `treefmt.toml`
- **Faster pre-commit**: One hook instead of many

## Version Mirroring

This repository automatically mirrors new treefmt releases. When a new version of treefmt is released on GitHub, this repository will:

1. Detect the new version
2. Build wheels for all supported platforms
3. Publish to PyPI
4. Create a corresponding git tag and GitHub release

This ensures you always have access to the latest treefmt version.

## Supported Platforms

Pre-built wheels are available for:

- Linux (x86_64, aarch64)
- macOS (x86_64, arm64)

Note: Windows is not currently supported by treefmt upstream.

## Attribution

This project is based on [ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit) by Astral Software Inc., which pioneered the approach of distributing pre-commit hooks with prebuilt binaries. The automation and mirroring infrastructure was adapted from their work.

## License

treefmt-pre-commit is licensed under either of:

- Apache License, Version 2.0, ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

The treefmt binary is developed by [numtide](https://numtide.com/) and is also MIT licensed. See the [treefmt repository](https://github.com/numtide/treefmt) for more information.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in treefmt-pre-commit by you, as defined in the Apache-2.0 license, shall be dually licensed as above, without any additional terms or conditions.
