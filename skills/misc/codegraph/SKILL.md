---
name: codegraph-bootstrap
description: Ensure CodeGraph is installed, indexed for the current project, registered as an MCP server, and wired into startup hooks. Use when setting up or repairing CodeGraph for Hermes, MCP registration, or session-start hook automation.
---

# CodeGraph Bootstrap

Use this skill when the user wants CodeGraph to be available automatically across coding agents.

## Quick Start

Run the bundled wrapper:

```bash
# Install CodeGraph CLI if missing
npm install -g @colbymchenry/codegraph

# Initialize and index current project
codegraph init .
codegraph index .

# Register MCP for Hermes
codegraph install --target hermes --location global --yes
```

## What It Ensures

- Installs `@colbymchenry/codegraph` with npm when the `codegraph` CLI is missing.
- Initializes and indexes the current project if `.codegraph/codegraph.db` is absent.
- Runs `codegraph install --target hermes --location global --yes` to register MCP for Hermes.
- Installs startup hook wrappers for Hermes using the shared `Ensure-CodeGraph.ps1` (requires PowerShell Core).
- Logs status to `$HOME/.codegraph-agent-bootstrap.log`.

## SQL Fallback

When MCP tools are not visible in the current session or a custom graph query is needed, use:

```bash
# Query recipes are available in references/query-recipes.md
```

## Operational Notes

- Restart already-running agents after the first setup. New MCP server definitions and hooks usually load only at process startup.
- Use `--skip-index` when only repairing MCP/hook registration and avoiding a project indexing pass.
- Use `--target hermes` by default, or pass another CodeGraph-supported target list when needed.
- The hook script exits successfully even when bootstrap work fails, so agent startup is not blocked. Check the log file for details.
- Full user-facing documentation is in `README.md`.

## Verification

After running the wrapper, verify with:

```bash
codegraph status --json
```

## Linux Installation

On Linux systems without PowerShell Core, you can:

1. Install PowerShell Core via snap: `snap install powershell --classic`
2. Or manually execute the steps above without the hook automation

## Files

- `scripts/` - PowerShell scripts for automation (requires PowerShell Core)
- `references/` - Query recipes and documentation
- `README.md` - Full documentation