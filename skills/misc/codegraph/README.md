# CodeGraph Installer Skill

[中文说明](README.zh-CN.md)

This Codex skill keeps CodeGraph available to coding agents on a local machine. It installs the CodeGraph CLI when needed, initializes project indexes, registers the CodeGraph MCP server with supported agents, and adds startup hooks so new sessions can repair missing setup automatically.

The current implementation targets the Colby McHenry CodeGraph CLI package (`@colbymchenry/codegraph`) and uses its own installer for agent MCP registration.

## What This Adds

- A portable Codex skill directory that can be cloned into `~/.codex/skills/codegraph-bootstrap/`.
- Shared bootstrap scripts under this skill's `scripts/` directory.
- Startup hook entries for Codex and Claude Code.
- Local startup plugin files for OpenCode.
- Hermes `on_session_start` shell hook configuration.
- SQLite query fallback recipes inspired by `bennett-lee/codegraph-skill`, adapted for the current CodeGraph schema and C# `method` nodes.

## File Layout

```text
codegraph-bootstrap/
  SKILL.md
  README.md
  agents/openai.yaml
  scripts/
    Ensure-CodeGraph.ps1
    Install-CodeGraphBootstrap.ps1
    Invoke-CodeGraphBootstrap.ps1
    Invoke-CodeGraphSql.ps1
  references/query-recipes.md
```

Agent configuration touched by setup:

```text
~/.codex/config.toml
~/.codex/hooks.json
~/.codex/AGENTS.md
~/.claude.json
~/.claude/settings.json
~/.claude/CLAUDE.md
~/AppData/Roaming/opencode/opencode.jsonc
~/AppData/Roaming/opencode/AGENTS.md
~/AppData/Roaming/opencode/plugins/codegraph-bootstrap.mjs
~/.config/opencode/plugins/codegraph-bootstrap.mjs
~/.hermes/config.yaml
```

`codegraph install --target all` may also update other agents supported by the installed CodeGraph version, such as Cursor, Gemini CLI, Antigravity, or Kiro.

## Quick Start

Run this from any project root. It clones the skill if needed, then installs/repairs CodeGraph, indexes the current project, registers MCP servers, and installs startup hooks:

```powershell
$skill = "$HOME\.codex\skills\codegraph-bootstrap"
if (-not (Test-Path -LiteralPath $skill)) {
  git clone https://github.com/petrezhu/codegraph-installer-skill.git $skill
}
powershell -NoProfile -ExecutionPolicy Bypass -File "$skill\scripts\Invoke-CodeGraphBootstrap.ps1"
```

If the skill is already installed, the short form is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphBootstrap.ps1"
```

Then restart already-running agents so they reload MCP servers and startup hooks.

## Main Scripts

### Ensure-CodeGraph.ps1

Checks and repairs the runtime state.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Ensure-CodeGraph.ps1" -Mode ensure
```

Modes:

- `check`: verify the CodeGraph CLI exists, installing it when npm is available.
- `ensure`: verify CLI, initialize or sync the current project index, and register MCP.
- `hook`: same repair flow but emits hook-safe JSON and exits successfully so agent startup is not blocked.

Useful options:

- `-ProjectPath <path>`: index a specific project.
- `-Targets all`: pass target agent ids to `codegraph install`.
- `-SkipIndex`: repair MCP/hook registration without indexing.
- `-Quiet`: write to log only.

### Install-CodeGraphBootstrap.ps1

Runs `Ensure-CodeGraph.ps1` and writes startup hooks.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Install-CodeGraphBootstrap.ps1" -Targets all
```

This is the normal setup entry point.

### Invoke-CodeGraphSql.ps1

Queries `.codegraph/codegraph.db` without requiring `sqlite3.exe`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe stats
```

List available recipes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -ListRecipes
```

## Startup Hook Behavior

The hook does not keep a standalone CodeGraph server running. MCP clients launch `codegraph serve --mcp` from their own MCP configuration when they start.

The startup hook only verifies that:

- the CLI exists;
- the current project has `.codegraph/codegraph.db`, unless `-SkipIndex` is used;
- MCP registration exists for supported agents;
- failures are logged without blocking the agent session.

Logs are written to:

```text
~/.codegraph-agent-bootstrap.log
```

## Agent Notes

### Codex

MCP registration is stored in:

```toml
[mcp_servers.codegraph]
command = "codegraph"
args = ["serve", "--mcp"]
```

The setup also enables the `hooks` feature and writes `~/.codex/hooks.json`.

Verify:

```powershell
codex mcp get codegraph
```

### Claude Code

CodeGraph writes MCP settings to `~/.claude.json` and allowlisted CodeGraph tools to `~/.claude/settings.json`. The bootstrap adds a `SessionStart` command hook to the same settings file.

Restart Claude Code after setup.

### OpenCode

CodeGraph writes MCP config to `~/AppData/Roaming/opencode/opencode.jsonc` on this Windows machine. The bootstrap writes local plugin files to both:

```text
~/AppData/Roaming/opencode/plugins/codegraph-bootstrap.mjs
~/.config/opencode/plugins/codegraph-bootstrap.mjs
```

OpenCode loads JavaScript or TypeScript files from its plugin directories at startup.

### Hermes

CodeGraph MCP is configured under `mcp_servers.codegraph` in `~/.hermes/config.yaml`. The bootstrap adds a shell hook under:

```yaml
hooks:
  on_session_start:
    - command: 'powershell -NoProfile -ExecutionPolicy Bypass -File ".../Ensure-CodeGraph.ps1" -Mode hook -Targets "all" -Quiet'
      timeout: 120
hooks_auto_accept: true
```

Hermes may require a new session or `/reload-mcp` after MCP changes.

## SQL Fallback

Use SQL fallback when:

- the current agent session has not loaded CodeGraph MCP tools yet;
- you need a custom graph query that MCP does not expose;
- you want compact structured output for scripts or reports.

Examples:

```powershell
# Search symbol names, qualified names, docstrings, and signatures
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe search -Symbol FloorManagementService -Json

# Direct callers
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe callers -Symbol SaveFloors

# Recursive impact
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe impact -Symbol SaveFloors -Depth 4 -Limit 100

# Symbols in one file
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Invoke-CodeGraphSql.ps1" -Recipe file-symbols -FilePath "Services/Floor/FloorManagementService.cs"
```

More recipes live in:

```text
~/.codex/skills/codegraph-bootstrap/references/query-recipes.md
```

## Verification

Check CLI:

```powershell
codegraph --version
```

Check project index:

```powershell
codegraph status --json
```

Check Codex MCP:

```powershell
codex mcp list
```

Check hook-safe output:

```powershell
'{"cwd":"E:\\C#\\ZDBim.Revit.BimMaster\\ZDZS.DecorateDesign\\DockPanel","hook_event_name":"SessionStart"}' |
  powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.codex\skills\codegraph-bootstrap\scripts\Ensure-CodeGraph.ps1" -Mode hook -Quiet -SkipIndex
```

Expected output is a single JSON object.

## Troubleshooting

### MCP tools do not appear

Restart the agent. MCP server definitions are usually loaded only at process startup.

### Hook appears to do nothing

Check:

```powershell
Get-Content -Tail 80 "$HOME\.codegraph-agent-bootstrap.log"
```

### `sqlite3` is not installed

Use `Invoke-CodeGraphSql.ps1`; it uses Python's built-in `sqlite3` module.

### Index exists but is stale

Run:

```powershell
codegraph sync .
```

or run the bootstrap script again from the project root.

### Project has no index

Run:

```powershell
codegraph init .
codegraph index .
```

or use the bootstrap script from the project root.

## Rollback

Remove CodeGraph MCP registrations:

```powershell
codegraph uninstall --target all --location global --yes
```

Remove bootstrap hooks and scripts:

```powershell
Remove-Item -LiteralPath "$HOME\.codex\hooks.json" -Force
Remove-Item -LiteralPath "$HOME\.codex\skills\codegraph-bootstrap" -Recurse -Force
```

Manual cleanup may still be needed for hook snippets in:

```text
~/.claude/settings.json
~/.hermes/config.yaml
~/AppData/Roaming/opencode/plugins/codegraph-bootstrap.mjs
~/.config/opencode/plugins/codegraph-bootstrap.mjs
```

Restart affected agents after rollback.

## References

- Colby McHenry CodeGraph: https://colbymchenry.github.io/codegraph/
- CodeGraph MCP server reference: https://colbymchenry.github.io/codegraph/reference/mcp-server/
- Bennett Lee CodeGraph skill: https://github.com/bennett-lee/codegraph-skill
- OpenCode plugin docs: https://dev.opencode.ai/docs/plugins/
- Hermes shell hook docs: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/hooks.md
- Hermes MCP config reference: https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference/
