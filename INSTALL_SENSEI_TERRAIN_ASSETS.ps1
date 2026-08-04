[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ZipPath,

    [switch]$NoLaunch,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$projectContent = Join-Path $projectRoot "Content"
$repairScript = Join-Path $projectRoot "Content\Python\DisableAetherSenseiDisplacement_UE58.py"

if (!(Test-Path -LiteralPath $projectRoot)) {
    throw "AetherFlight project folder was not found: $projectRoot"
}
if (!(Test-Path -LiteralPath $repairScript)) {
    throw "Sensei repair script was not found: $repairScript"
}

if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    $searchRoots = @(
        (Join-Path $projectRoot "SourceAssets\ThirdParty"),
        (Join-Path $env:USERPROFILE "Downloads"),
        $repoRoot
    ) | Where-Object { Test-Path -LiteralPath $_ }

    $candidate = $searchRoots |
        ForEach-Object {
            Get-ChildItem -LiteralPath $_ -Filter "*SenseiTerrain*.zip" -File -ErrorAction SilentlyContinue
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $candidate) {
        throw "No SenseiTerrain ZIP was found. Pass its path, for example: .\INSTALL_SENSEI_TERRAIN_ASSETS.ps1 `"C:\Users\$env:USERNAME\Downloads\SenseiTerrainEA.zip`""
    }

    $ZipPath = $candidate.FullName
}

$ZipPath = (Resolve-Path -LiteralPath $ZipPath).Path

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close Unreal Editor completely before installing the Sensei assets."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

$archivePrefix = "SenseiTerrain/Content/SenseiTerrain/"
$requiredMaster = "${archivePrefix}Materials/M_SenseiTerrain.uasset"
$requiredDefinition = "${archivePrefix}Materials/MPD_SenseiTerrain.uasset"
$targetRoot = Join-Path $projectContent "SenseiTerrain"
$copied = 0
$skipped = 0

$archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $entryNames = @($archive.Entries | ForEach-Object { $_.FullName })

    foreach ($required in @($requiredMaster, $requiredDefinition)) {
        if ($entryNames -notcontains $required) {
            throw "The selected ZIP is missing a required Sensei Terrain asset: $required"
        }
    }

    foreach ($entry in $archive.Entries) {
        if ([string]::IsNullOrWhiteSpace($entry.Name)) {
            continue
        }

        $name = $entry.FullName
        if (!$name.StartsWith($archivePrefix)) {
            continue
        }

        $relative = $name.Substring($archivePrefix.Length).Replace("/", "\")
        $destination = Join-Path $targetRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null

        if ((Test-Path -LiteralPath $destination) -and !$Force) {
            $existing = Get-Item -LiteralPath $destination
            if ($existing.Length -eq $entry.Length) {
                $skipped++
                continue
            }
        }

        $sourceStream = $entry.Open()
        try {
            $destinationStream = [System.IO.File]::Open(
                $destination,
                [System.IO.FileMode]::Create,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::None
            )
            try {
                $sourceStream.CopyTo($destinationStream)
            }
            finally {
                $destinationStream.Dispose()
            }
        }
        finally {
            $sourceStream.Dispose()
        }

        $copied++
    }
}
finally {
    $archive.Dispose()
}

$masterMaterial = Join-Path $targetRoot "Materials\M_SenseiTerrain.uasset"
$senseiDefinition = Join-Path $targetRoot "Materials\MPD_SenseiTerrain.uasset"

if (!(Test-Path -LiteralPath $masterMaterial)) {
    throw "The Sensei master material was not installed: $masterMaterial"
}
if (!(Test-Path -LiteralPath $senseiDefinition)) {
    throw "The Sensei dependency MPD was not installed: $senseiDefinition"
}

$assetCount = @(Get-ChildItem -LiteralPath $targetRoot -Filter "*.uasset" -File -Recurse).Count

Write-Host ""
Write-Host "Sensei Terrain assets installed locally."
Write-Host "ZIP:          $ZipPath"
Write-Host "Copied:       $copied"
Write-Host "Unchanged:    $skipped"
Write-Host "Total assets: $assetCount"
Write-Host "Master:       $masterMaterial"
Write-Host "Dependency:   $senseiDefinition"
Write-Host ""
Write-Host "The complete /Game/SenseiTerrain asset namespace was copied so Unreal can resolve internal package references."
Write-Host "No Sensei project Config files were copied, and MPD_AetherWorld remains the active Aether definition."

if ($NoLaunch) {
    Write-Host ""
    Write-Host "Unreal launch skipped. Launch the project with -nosound and run DisableAetherSenseiDisplacement_UE58.py."
    exit 0
}

$editorCandidates = @(
    "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe",
    "C:\Program Files\Epic Games\UE_5.8EA\Engine\Binaries\Win64\UnrealEditor.exe"
)
$editor = $editorCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$editor) {
    throw "UnrealEditor.exe for UE 5.8 was not found. Re-run with -NoLaunch, then launch Unreal manually."
}

$project = Get-ChildItem -LiteralPath $projectRoot -Filter "*.uproject" -File | Select-Object -First 1
if ($null -eq $project) {
    throw "No .uproject file was found in $projectRoot"
}

$arguments = @(
    ('"{0}"' -f $project.FullName),
    "-nosound",
    ('-ExecutePythonScript="{0}"' -f $repairScript)
)

Write-Host ""
Write-Host "Launching Unreal Engine 5.8 with no sound and running the Aether Sensei repair..."
Start-Process -FilePath $editor -ArgumentList $arguments
