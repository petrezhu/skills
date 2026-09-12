param(
    [string]$Targets = "all",
    [switch]$SkipIndex
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnsureScript = Join-Path $ToolRoot "Ensure-CodeGraph.ps1"
$HookCommand = 'powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -Mode hook -Targets "{1}" -Quiet' -f $EnsureScript, $Targets

function Save-JsonFile {
    param([string]$Path, [object]$Value)

    $json = $Value | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Read-JsonFile {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $text = Get-Content -LiteralPath $Path -Raw
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            return $text | ConvertFrom-Json
        }
    }

    return [pscustomobject]@{}
}

function Add-MemberIfMissing {
    param([object]$Object, [string]$Name, [object]$Value)

    if (-not ($Object.PSObject.Properties.Name -contains $Name)) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Add-SessionStartHook {
    param([object]$Container, [string]$Command, [bool]$UseMatcher)

    Add-MemberIfMissing $Container "SessionStart" @()

    foreach ($group in @($Container.SessionStart)) {
        foreach ($hook in @($group.hooks)) {
            if ($hook.command -like "*Ensure-CodeGraph.ps1*") {
                if ($hook.command -ne $Command) {
                    $hook.command = $Command
                    return $true
                }
                return $false
            }
        }
    }

    $hook = [ordered]@{
        type = "command"
        command = $Command
        timeout = 120
        statusMessage = "Ensuring CodeGraph"
    }

    $group = [ordered]@{
        hooks = @($hook)
    }

    if ($UseMatcher) {
        $group.matcher = "startup|resume|clear|compact"
    }

    $Container.SessionStart = @($Container.SessionStart) + @([pscustomobject]$group)
    return $true
}

function Install-CodexHook {
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    New-Item -ItemType Directory -Force $codexHome | Out-Null

    $hooksPath = Join-Path $codexHome "hooks.json"
    $root = Read-JsonFile $hooksPath
    Add-MemberIfMissing $root "hooks" ([pscustomobject]@{})

    $changed = Add-SessionStartHook $root.hooks $HookCommand $true
    if ($changed) {
        Save-JsonFile $hooksPath $root
    }

    $configPath = Join-Path $codexHome "config.toml"
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $config = Get-Content -LiteralPath $configPath -Raw
    }
    else {
        $config = ""
    }

    if ($config -notmatch "(?m)^\[features\]") {
        Add-Content -LiteralPath $configPath -Value "`r`n[features]`r`nhooks = true" -Encoding UTF8
    }
    elseif ($config -notmatch "(?m)^hooks\s*=") {
        Add-Content -LiteralPath $configPath -Value "hooks = true" -Encoding UTF8
    }

    return $hooksPath
}

function Install-ClaudeHook {
    $claudeDir = Join-Path $HOME ".claude"
    New-Item -ItemType Directory -Force $claudeDir | Out-Null

    $settingsPath = Join-Path $claudeDir "settings.json"
    $settings = Read-JsonFile $settingsPath
    $changed = Add-SessionStartHook $settings $HookCommand $true
    if ($changed) {
        Save-JsonFile $settingsPath $settings
    }

    return $settingsPath
}

function Install-OpenCodeHook {
    $configDirs = @()
    if ($env:APPDATA) {
        $configDirs += (Join-Path $env:APPDATA "opencode")
    }
    $configDirs += (Join-Path $HOME ".config\opencode")

    $escapedScript = $EnsureScript.Replace("\", "\\")
    $content = @"
import { spawn } from "node:child_process";

function runCodeGraphBootstrap(cwd) {
  const args = [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "$escapedScript",
    "-Mode",
    "hook",
    "-Targets",
    "$Targets",
    "-ProjectPath",
    cwd || process.cwd(),
    "-Quiet",
  ];

  const child = spawn("powershell", args, { stdio: "ignore", detached: true });
  child.unref();
}

export const CodeGraphBootstrapPlugin = async ({ project }) => {
  return {
    event: async ({ event }) => {
      if (event?.type === "session.created") {
        runCodeGraphBootstrap(project?.directory || process.cwd());
      }
    },
  };
};
"@

    $written = @()
    foreach ($configDir in $configDirs | Select-Object -Unique) {
        $pluginsDir = Join-Path $configDir "plugins"
        New-Item -ItemType Directory -Force $pluginsDir | Out-Null
        $pluginPath = Join-Path $pluginsDir "codegraph-bootstrap.mjs"
        Set-Content -LiteralPath $pluginPath -Value $content -Encoding UTF8
        $written += $pluginPath
    }

    return ($written -join "; ")
}

function Install-HermesHook {
    $hermesDir = Join-Path $HOME ".hermes"
    New-Item -ItemType Directory -Force $hermesDir | Out-Null

    $configPath = Join-Path $hermesDir "config.yaml"
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        $yaml = Get-Content -LiteralPath $configPath -Raw
    }
    else {
        $yaml = ""
    }

    $pattern = "(?s)\r?\n?# CodeGraph bootstrap hook managed by ~/.codex/tools/codegraph/Install-CodeGraphBootstrap\.ps1.*?hooks_auto_accept:\s*true\r?\n?"
    $yaml = [regex]::Replace($yaml, $pattern, "")

    $hermesScript = $EnsureScript.Replace("\", "/")
    $snippet = @"

# CodeGraph bootstrap hook managed by ~/.codex/tools/codegraph/Install-CodeGraphBootstrap.ps1
hooks:
  on_session_start:
    - command: 'powershell -NoProfile -ExecutionPolicy Bypass -File "$hermesScript" -Mode hook -Targets "$Targets" -Quiet'
      timeout: 120
hooks_auto_accept: true
"@
    Set-Content -LiteralPath $configPath -Value ($yaml.TrimEnd() + $snippet) -Encoding UTF8

    return $configPath
}

Write-Host "Ensuring CodeGraph installation, project index, and MCP registration..."
$ensureArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $EnsureScript, "-Mode", "ensure", "-Targets", $Targets)
if ($SkipIndex) {
    $ensureArgs += "-SkipIndex"
}
& powershell @ensureArgs
if ($LASTEXITCODE -ne 0) {
    throw "Ensure-CodeGraph.ps1 failed with exit code $LASTEXITCODE."
}

$codexHook = Install-CodexHook
$claudeHook = Install-ClaudeHook
$opencodeHook = Install-OpenCodeHook
$hermesHook = Install-HermesHook

Write-Host "CodeGraph bootstrap hooks installed:"
Write-Host ("  Codex:      {0}" -f $codexHook)
Write-Host ("  ClaudeCode: {0}" -f $claudeHook)
Write-Host ("  OpenCode:   {0}" -f $opencodeHook)
Write-Host ("  Hermes:     {0}" -f $hermesHook)
Write-Host "Restart any already-running agents so they reload MCP servers and hooks."
