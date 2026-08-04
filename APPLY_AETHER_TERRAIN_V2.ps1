[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$replacement = Join-Path $PSScriptRoot "APPLY_AETHER_SURFACE_DETAIL.ps1"

Write-Warning "APPLY_AETHER_TERRAIN_V2.ps1 is retired for the current AetherWorld workflow."
Write-Host "The active terrain already contains the color/biome work that V2 was intended to add."
Write-Host "Forwarding to the safe surface-detail updater instead."
Write-Host ""

if (!(Test-Path -LiteralPath $replacement)) {
    throw "Replacement updater was not found: $replacement"
}

& $replacement
