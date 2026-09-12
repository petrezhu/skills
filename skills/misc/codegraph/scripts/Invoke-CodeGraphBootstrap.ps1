param(
    [string]$Targets = "all",
    [switch]$SkipIndex
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $scriptRoot "Install-CodeGraphBootstrap.ps1"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    $installer = Join-Path $HOME ".codex\tools\codegraph\Install-CodeGraphBootstrap.ps1"
}

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "CodeGraph bootstrap installer not found: $installer"
}

$args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $installer, "-Targets", $Targets)
if ($SkipIndex) {
    $args += "-SkipIndex"
}

& powershell @args
exit $LASTEXITCODE
