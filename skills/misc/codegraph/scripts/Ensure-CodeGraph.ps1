param(
    [ValidateSet("check", "ensure", "hook")]
    [string]$Mode = "ensure",

    [string]$ProjectPath = "",

    [string]$Targets = "all",

    [switch]$SkipIndex,

    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$LogPath = Join-Path $HOME ".codegraph-agent-bootstrap.log"

function Write-BootstrapLog {
    param([string]$Message)

    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if (-not $Quiet) {
        Write-Host $line
    }
}

function Invoke-LoggedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    $output = & $FilePath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in @($output)) {
        if ($null -ne $line -and -not [string]::IsNullOrWhiteSpace($line.ToString())) {
            Write-BootstrapLog $line.ToString()
        }
    }

    if ($exitCode -ne 0) {
        throw "$FailureMessage failed with exit code $exitCode."
    }
}

function Resolve-ProjectPath {
    param([string]$Candidate)

    if (-not [string]::IsNullOrWhiteSpace($Candidate) -and (Test-Path -LiteralPath $Candidate -PathType Container)) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $stdinText = ""
    if (-not [Console]::IsInputRedirected) {
        return (Get-Location).Path
    }

    try {
        $stdinText = [Console]::In.ReadToEnd()
        if (-not [string]::IsNullOrWhiteSpace($stdinText)) {
            $payload = $stdinText | ConvertFrom-Json
            if ($payload.cwd -and (Test-Path -LiteralPath $payload.cwd -PathType Container)) {
                return (Resolve-Path -LiteralPath $payload.cwd).Path
            }
        }
    }
    catch {
        Write-BootstrapLog ("Hook input parse skipped: {0}" -f $_.Exception.Message)
    }

    if ($env:CLAUDE_PROJECT_DIR -and (Test-Path -LiteralPath $env:CLAUDE_PROJECT_DIR -PathType Container)) {
        return (Resolve-Path -LiteralPath $env:CLAUDE_PROJECT_DIR).Path
    }

    return (Get-Location).Path
}

function Ensure-CodeGraphCli {
    $command = Get-Command codegraph -ErrorAction SilentlyContinue
    if ($command) {
        Write-BootstrapLog ("CodeGraph CLI found: {0}" -f $command.Source)
        return
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "CodeGraph CLI is missing and npm is not available for automatic installation."
    }

    Write-BootstrapLog "CodeGraph CLI missing; installing @colbymchenry/codegraph globally."
    Invoke-LoggedCommand "npm" @("install", "-g", "@colbymchenry/codegraph") "npm install -g @colbymchenry/codegraph"
}

function Ensure-CodeGraphIndex {
    param([string]$Path)

    if ($SkipIndex) {
        Write-BootstrapLog "Project index check skipped by parameter."
        return
    }

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Write-BootstrapLog ("Project path does not exist, index skipped: {0}" -f $Path)
        return
    }

    $dbPath = Join-Path $Path ".codegraph\codegraph.db"
    if (Test-Path -LiteralPath $dbPath -PathType Leaf) {
        Write-BootstrapLog ("CodeGraph index already exists: {0}" -f $dbPath)
        try {
            Invoke-LoggedCommand "codegraph" @("sync", $Path) "codegraph sync"
        }
        catch {
            Write-BootstrapLog ("CodeGraph sync failed; keeping existing index. {0}" -f $_.Exception.Message)
        }
        return
    }

    Write-BootstrapLog ("CodeGraph index missing; initializing project: {0}" -f $Path)
    Invoke-LoggedCommand "codegraph" @("init", $Path) "codegraph init"
    Invoke-LoggedCommand "codegraph" @("index", $Path) "codegraph index"

    Write-BootstrapLog "CodeGraph index initialized."
}

function Ensure-McpRegistration {
    param([string]$TargetIds)

    Write-BootstrapLog ("Ensuring CodeGraph MCP registration for targets: {0}" -f $TargetIds)
    Invoke-LoggedCommand "codegraph" @("install", "--target", $TargetIds, "--location", "global", "--yes") "codegraph install"
}

function Write-HookJson {
    param([bool]$Success, [string]$Message)

    if ($Mode -ne "hook") {
        return
    }

    $payload = [ordered]@{
        continue = $true
        suppressOutput = $false
        systemMessage = $Message
    }

    if (-not $Success) {
        $payload.systemMessage = "CodeGraph bootstrap did not complete: $Message"
    }

    $payload | ConvertTo-Json -Compress
}

try {
    $resolvedPath = Resolve-ProjectPath $ProjectPath
    Write-BootstrapLog ("Mode={0}; ProjectPath={1}" -f $Mode, $resolvedPath)

    if ($Mode -eq "check") {
        Ensure-CodeGraphCli
        Write-BootstrapLog "Check complete."
        exit 0
    }

    Ensure-CodeGraphCli
    Ensure-CodeGraphIndex $resolvedPath
    Ensure-McpRegistration $Targets

    $message = "CodeGraph is installed, indexed when needed, and MCP registration has been ensured. Restart the agent if MCP tools were just added."
    Write-BootstrapLog $message
    Write-HookJson $true $message
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-BootstrapLog ("ERROR: {0}" -f $message)
    Write-HookJson $false $message
    if ($Mode -eq "hook") {
        exit 0
    }

    throw
}
