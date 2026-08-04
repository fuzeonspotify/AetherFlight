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
$integrationScript = Join-Path $projectRoot "Content\Python\IntegrateSenseiTerrain_Aether_UE58.py"

if (!(Test-Path -LiteralPath $projectRoot)) {
    throw "AetherFlight project folder was not found: $projectRoot"
}

if (!(Test-Path -LiteralPath $integrationScript)) {
    throw "Sensei integration script was not found: $integrationScript"
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

$runningEditor = Get-Process UnrealEditor -ErrorAction SilentlyContinue
if ($runningEditor) {
    throw "Close Unreal Editor before installing the Sensei assets, then run this script again."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

$archivePrefix = "SenseiTerrain/Content/SenseiTerrain/"
$requiredEntry = "${archivePrefix}Materials/M_SenseiTerrain.uasset"
$targetRoot = Join-Path $projectContent "SenseiTerrain"
$copied = New-Object System.Collections.Generic.List[string]

$archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $entryNames = @($archive.Entries | ForEach-Object { $_.FullName })
    if ($entryNames -notcontains $requiredEntry) {
        throw "This ZIP does not contain the UE 5.8 Sensei Terrain master material: $requiredEntry"
    }

    foreach ($entry in $archive.Entries) {
        if ([string]::IsNullOrWhiteSpace($entry.Name)) {
            continue
        }

        $name = $entry.FullName
        $include =
            $name.StartsWith("${archivePrefix}MaterialFunctions/") -or
            $name.StartsWith("${archivePrefix}Textures/") -or
            $name -eq $requiredEntry

        if (!$include) {
            continue
        }

        $relative = $name.Substring($archivePrefix.Length).Replace("/", "\")
        $destination = Join-Path $targetRoot $relative
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

        if ((Test-Path -LiteralPath $destination) -and !$Force) {
            $existing = Get-Item -LiteralPath $destination
            if ($existing.Length -eq $entry.Length) {
                $copied.Add($destination)
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

        $copied.Add($destination)
    }
}
finally {
    $archive.Dispose()
}

$masterMaterial = Join-Path $targetRoot "Materials\M_SenseiTerrain.uasset"
$functionCount = @(Get-ChildItem -LiteralPath (Join-Path $targetRoot "MaterialFunctions") -Filter "*.uasset" -File).Count
$textureCount = @(Get-ChildItem -LiteralPath (Join-Path $targetRoot "Textures") -Filter "*.uasset" -File).Count

if (!(Test-Path -LiteralPath $masterMaterial)) {
    throw "The Sensei master material was not installed."
}
if ($functionCount -ne 14) {
    throw "Expected 14 Sensei material functions, found $functionCount."
}
if ($textureCount -ne 4) {
    throw "Expected 4 Sensei utility textures, found $textureCount."
}

Write-Host ""
Write-Host "Sensei Terrain core assets installed locally."
Write-Host "Master material: $masterMaterial"
Write-Host "Material functions: $functionCount"
Write-Host "Utility textures: $textureCount"
Write-Host "The supplied MPD, example maps, config, and external actors were intentionally skipped."

if ($NoLaunch) {
    Write-Host ""
    Write-Host "Unreal launch skipped. Run IntegrateSenseiTerrain_Aether_UE58.py from Unreal's Output Log when ready."
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
    ('-ExecutePythonScript="{0}"' -f $integrationScript)
)

Write-Host ""
Write-Host "Launching Unreal Engine 5.8 with the Aether Sensei integration script..."
Start-Process -FilePath $editor -ArgumentList $arguments
