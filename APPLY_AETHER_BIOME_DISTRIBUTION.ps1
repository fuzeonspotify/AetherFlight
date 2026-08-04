[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "The old replacement-material biome pass has been retired."
Write-Host "Forwarding to the safe Sensei biome-tuning pass..."
Write-Host ""

$replacement = Join-Path $PSScriptRoot "APPLY_AETHER_SENSEI_BIOME_TUNING.ps1"
if (!(Test-Path -LiteralPath $replacement)) {
    throw "Safe Sensei biome-tuning launcher was not found: $replacement"
}

& $replacement
exit $LASTEXITCODE
