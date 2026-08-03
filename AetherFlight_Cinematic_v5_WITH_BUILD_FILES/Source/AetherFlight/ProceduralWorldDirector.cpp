#include "ProceduralWorldDirector.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "KismetProceduralMeshLibrary.h"
#include "LandscapeProxy.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AProceduralWorldDirector::AProceduralWorldDirector()
{
    PrimaryActorTick.bCanEverTick = true;

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    Terrain = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ProceduralTerrain"));
    Terrain->SetupAttachment(Root);
    Terrain->bUseAsyncCooking = true;
    Terrain->SetCollisionProfileName(TEXT("BlockAll"));

    Ocean = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Ocean"));
    Ocean->SetupAttachment(Root);
    Ocean->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Ocean->SetCastShadow(false);
    Ocean->SetTranslucentSortPriority(-5);

    Runway = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Runway"));
    Runway->SetupAttachment(Root);
    Runway->SetCollisionProfileName(TEXT("BlockAll"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded())
    {
        Runway->SetStaticMesh(Cube.Object);
    }

    RunwayMarkings = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RunwayMarkings"));
    RunwayMarkings->SetupAttachment(Root);
    RunwayMarkings->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    ForestInstances = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ProceduralForest"));
    ForestInstances->SetupAttachment(Root);
    ForestInstances->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ForestInstances->SetCullDistances(220000, 1800000);
    ForestInstances->bCastDynamicShadow = true;

    RockInstances = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ProceduralRocks"));
    RockInstances->SetupAttachment(Root);
    RockInstances->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RockInstances->SetCullDistances(300000, 2400000);
    RockInstances->bCastDynamicShadow = true;

    Sun = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("Sun"));
    Sun->SetupAttachment(Root);
    Sun->SetMobility(EComponentMobility::Movable);
    Sun->bAtmosphereSunLight = true;
    Sun->SetAtmosphereSunLightIndex(0);
    Sun->CastShadows = true;
    Sun->bCastCloudShadows = true;
    Sun->CloudShadowStrength = 0.82f;
    Sun->CloudShadowOnAtmosphereStrength = 0.75f;
    Sun->CloudShadowOnSurfaceStrength = 0.9f;
    Sun->CloudShadowRaySampleCountScale = 2.0f;
    Sun->CloudShadowMapResolutionScale = 2.0f;
    Sun->CloudScatteredLuminanceScale = FLinearColor(1.0f, 0.94f, 0.88f);
    Sun->LightSourceAngle = 0.535f;
    Sun->bPerPixelAtmosphereTransmittance = true;

    SkyLight = CreateDefaultSubobject<USkyLightComponent>(TEXT("SkyLight"));
    SkyLight->SetupAttachment(Root);
    SkyLight->SetMobility(EComponentMobility::Movable);
    SkyLight->bRealTimeCapture = true;
    SkyLight->SetIntensity(0.78f);

    SkyAtmosphere = CreateDefaultSubobject<USkyAtmosphereComponent>(TEXT("SkyAtmosphere"));
    SkyAtmosphere->SetupAttachment(Root);

    HeightFog = CreateDefaultSubobject<UExponentialHeightFogComponent>(TEXT("VolumetricFog"));
    HeightFog->SetupAttachment(Root);
    HeightFog->bEnableVolumetricFog = true;
    HeightFog->VolumetricFogScatteringDistribution = 0.42f;
    HeightFog->VolumetricFogAlbedo = FColor(220, 228, 232);
    HeightFog->VolumetricFogExtinctionScale = 0.78f;
    HeightFog->FogHeightFalloff = 0.22f;

    VolumetricClouds = CreateDefaultSubobject<UVolumetricCloudComponent>(TEXT("VolumetricClouds"));
    VolumetricClouds->SetupAttachment(Root);
    VolumetricClouds->SetLayerBottomAltitude(1.15f);
    VolumetricClouds->SetLayerHeight(8.5f);
    VolumetricClouds->SetTracingStartMaxDistance(450.0f);
    VolumetricClouds->SetTracingMaxDistance(250.0f);
    VolumetricClouds->SetViewSampleCountScale(2.0f);
    VolumetricClouds->SetShadowViewSampleCountScale(1.5f);

    PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("CinematicGrade"));
    PostProcess->SetupAttachment(Root);
    PostProcess->bUnbound = true;
    PostProcess->Settings.bOverride_BloomIntensity = true;
    PostProcess->Settings.BloomIntensity = 0.16f;
    PostProcess->Settings.bOverride_VignetteIntensity = true;
    PostProcess->Settings.VignetteIntensity = 0.12f;
    PostProcess->Settings.bOverride_LensFlareIntensity = true;
    PostProcess->Settings.LensFlareIntensity = 0.08f;
    PostProcess->Settings.bOverride_AutoExposureBias = true;
    PostProcess->Settings.AutoExposureBias = -0.55f;
    PostProcess->Settings.bOverride_AmbientOcclusionIntensity = true;
    PostProcess->Settings.AmbientOcclusionIntensity = 1.15f;
    PostProcess->Settings.bOverride_AmbientOcclusionQuality = true;
    PostProcess->Settings.AmbientOcclusionQuality = 80.0f;
    PostProcess->Settings.bOverride_MotionBlurAmount = true;
    PostProcess->Settings.MotionBlurAmount = 0.32f;
    PostProcess->Settings.bOverride_ColorSaturation = true;
    PostProcess->Settings.ColorSaturation = FVector4(0.96f, 0.98f, 1.0f, 1.0f);
    PostProcess->Settings.bOverride_ColorContrast = true;
    PostProcess->Settings.ColorContrast = FVector4(1.08f, 1.08f, 1.08f, 1.0f);
    PostProcess->Settings.bOverride_FilmSlope = true;
    PostProcess->Settings.FilmSlope = 0.82f;
    PostProcess->Settings.bOverride_FilmToe = true;
    PostProcess->Settings.FilmToe = 0.48f;
    PostProcess->Settings.bOverride_FilmShoulder = true;
    PostProcess->Settings.FilmShoulder = 0.24f;
}

void AProceduralWorldDirector::BeginPlay()
{
    Super::BeginPlay();
    EnsureWorldGenerated();
}

void AProceduralWorldDirector::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    CurrentStorminess = FMath::FInterpTo(CurrentStorminess, TargetStorminess, DeltaSeconds, 0.22f);
    HeightFog->SetFogDensity(FMath::FInterpTo(HeightFog->FogDensity, TargetFogDensity, DeltaSeconds, 0.28f));
    Sun->SetIntensity(FMath::FInterpTo(Sun->Intensity, TargetSunIntensity, DeltaSeconds, 0.25f));
    Sun->SetLightColor(FMath::Lerp(Sun->GetLightColor(), TargetSunColor, FMath::Clamp(DeltaSeconds * 0.3f, 0.0f, 1.0f)));
    Sun->SetWorldRotation(FMath::RInterpTo(Sun->GetComponentRotation(), TargetSunRotation, DeltaSeconds, 0.18f));
    UpdateOceanSurface(DeltaSeconds);
}

void AProceduralWorldDirector::EnsureWorldGenerated()
{
    if (bGenerated)
    {
        return;
    }
    bGenerated = true;
    AirbaseLocation.Z = AirbaseElevationMeters * 100.0f;
    bUsingProductionLandscape = HasProductionLandscape();
    if (bUsingProductionLandscape)
    {
        Terrain->ClearAllMeshSections();
        Terrain->SetVisibility(false, true);
        Terrain->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        UE_LOG(LogTemp, Display, TEXT("[Aether] Production Landscape detected; runtime placeholder terrain is disabled."));
    }
    else
    {
        Terrain->SetVisibility(true, true);
        Terrain->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        GenerateTerrain();
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether] No Landscape actor found. Using the low-detail fallback terrain. Import the production 4033 heightmap."));
    }

    if (HasAuthoredWater())
    {
        Ocean->ClearAllMeshSections();
        Ocean->SetVisibility(false, true);
        OceanMaterialInstance = nullptr;
        UE_LOG(LogTemp, Display, TEXT("[Aether] Authored water detected; runtime ocean plane is disabled."));
    }
    else
    {
        Ocean->SetVisibility(true, true);
        GenerateOcean();
    }
    GenerateRunwayMarkings();
    GenerateEnvironmentInstances();
    ConfigureAtmosphere();

    Runway->SetRelativeLocation(AirbaseLocation + FVector(0.0f, 0.0f, 45.0f));
    Runway->SetRelativeScale3D(FVector(2200.0f, 72.0f, 1.2f));
    if (UMaterialInterface* RunwayMaterial = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Aether/Materials/M_Runway_Cinematic.M_Runway_Cinematic")))
    {
        Runway->SetMaterial(0, RunwayMaterial);
    }
    ApplyWeather(Weather, true);
}

void AProceduralWorldDirector::CycleWeather()
{
    const uint8 Next = (static_cast<uint8>(Weather) + 1) % 4;
    ApplyWeather(static_cast<EAetherWeather>(Next), false);
}

FTransform AProceduralWorldDirector::GetFlightSpawnTransform() const
{
    FVector Location = AirbaseLocation + FVector(-210000.0f, 0.0f, 0.0f);
    float GroundMeters = AirbaseElevationMeters;
    FVector GroundNormal = FVector::UpVector;
    SampleGround(Location.X, Location.Y, GroundMeters, GroundNormal);
    Location.Z = (FMath::Max(GroundMeters, AirbaseElevationMeters) + 850.0f) * 100.0f;
    return FTransform(FRotator(-2.0f, 0.0f, 0.0f), Location);
}

FVector AProceduralWorldDirector::GetTurbulenceForce(const FVector& WorldLocation, const float TimeSeconds, const float MassKg) const
{
    const float Gust = CurrentStorminess * MassKg * 1.85f;
    const float X = WorldLocation.X * 0.000017f;
    const float Y = WorldLocation.Y * 0.000021f;
    return FVector(
        FMath::Sin(Y + TimeSeconds * 0.77f),
        FMath::Sin(X * 1.7f - TimeSeconds * 1.13f),
        FMath::Sin(X + Y + TimeSeconds * 1.91f) * 1.55f) * Gust;
}

float AProceduralWorldDirector::GetCondensationHumidity() const
{
    switch (Weather)
    {
    case EAetherWeather::GoldenClear: return 0.34f;
    case EAetherWeather::BrokenClouds: return 0.76f;
    case EAetherWeather::StormFront: return 0.96f;
    case EAetherWeather::BlueHour: return 0.64f;
    default: return 0.68f;
    }
}

AProceduralWorldDirector* AProceduralWorldDirector::Find(UWorld* World)
{
    if (!World)
    {
        return nullptr;
    }
    for (TActorIterator<AProceduralWorldDirector> It(World); It; ++It)
    {
        return *It;
    }
    return nullptr;
}

void AProceduralWorldDirector::GenerateTerrain()
{
    Terrain->ClearAllMeshSections();

    const int32 Tiles = FMath::Clamp(TerrainTilesPerAxis, 2, 16);
    const int32 Resolution = FMath::Clamp(TerrainTileResolution, 17, 129);
    const float WorldSizeCm = TerrainSizeKilometers * 100000.0f;
    const float TileSizeCm = WorldSizeCm / static_cast<float>(Tiles);
    const float Step = TileSizeCm / static_cast<float>(Resolution - 1);
    const int32 VertexCount = Resolution * Resolution;

    UMaterialInterface* TerrainMaterial = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Aether/Materials/M_Terrain_Cinematic.M_Terrain_Cinematic"));
    if (!TerrainMaterial)
    {
        TerrainMaterial = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
    }

    for (int32 TileY = 0; TileY < Tiles; ++TileY)
    {
        for (int32 TileX = 0; TileX < Tiles; ++TileX)
        {
            TArray<FVector> Vertices;
            TArray<int32> Triangles;
            TArray<FVector> Normals;
            TArray<FVector2D> UVs;
            TArray<FLinearColor> Colors;
            TArray<FProcMeshTangent> Tangents;
            Vertices.Reserve(VertexCount);
            Normals.Reserve(VertexCount);
            UVs.Reserve(VertexCount);
            Colors.Reserve(VertexCount);
            Tangents.Reserve(VertexCount);
            Triangles.Reserve((Resolution - 1) * (Resolution - 1) * 6);

            const float TileMinX = -WorldSizeCm * 0.5f + TileX * TileSizeCm;
            const float TileMinY = -WorldSizeCm * 0.5f + TileY * TileSizeCm;

            for (int32 Y = 0; Y < Resolution; ++Y)
            {
                for (int32 X = 0; X < Resolution; ++X)
                {
                    const float XCm = TileMinX + X * Step;
                    const float YCm = TileMinY + Y * Step;
                    const float HeightM = TerrainHeightMeters(XCm, YCm);
                    const FVector Normal = TerrainNormal(XCm, YCm, Step * 0.65f);
                    const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);

                    Vertices.Add(FVector(XCm, YCm, HeightM * 100.0f));
                    Normals.Add(Normal);
                    UVs.Add(FVector2D(XCm / 28000.0f, YCm / 28000.0f));
                    Colors.Add(TerrainBiomeColor(HeightM, Slope, XCm, YCm));
                    Tangents.Add(FProcMeshTangent(FVector(1.0f, 0.0f, 0.0f), false));
                }
            }

            for (int32 Y = 0; Y < Resolution - 1; ++Y)
            {
                for (int32 X = 0; X < Resolution - 1; ++X)
                {
                    const int32 I = Y * Resolution + X;
                    Triangles.Append({I, I + 1, I + Resolution, I + 1, I + Resolution + 1, I + Resolution});
                }
            }

            const int32 SectionIndex = TileY * Tiles + TileX;
            Terrain->CreateMeshSection_LinearColor(
                SectionIndex, Vertices, Triangles, Normals, UVs, Colors, Tangents, true);
            if (TerrainMaterial)
            {
                Terrain->SetMaterial(SectionIndex, TerrainMaterial);
            }
        }
    }
}

void AProceduralWorldDirector::GenerateOcean()
{
    const float Extent = TerrainSizeKilometers * 65000.0f;
    // 257x257 keeps the fallback ocean inexpensive while giving vertex displacement
    // enough geometry for kilometre-scale swells. Fine ripples remain pixel-normal detail.
    constexpr int32 Resolution = 257;
    const float Step = Extent * 2.0f / static_cast<float>(Resolution - 1);

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FProcMeshTangent> Tangents;
    TArray<FLinearColor> Colors;
    Vertices.Reserve(Resolution * Resolution);
    Normals.Reserve(Resolution * Resolution);
    UVs.Reserve(Resolution * Resolution);
    Colors.Reserve(Resolution * Resolution);
    Tangents.Reserve(Resolution * Resolution);

    for (int32 Y = 0; Y < Resolution; ++Y)
    {
        for (int32 X = 0; X < Resolution; ++X)
        {
            const float XCm = -Extent + X * Step;
            const float YCm = -Extent + Y * Step;
            Vertices.Add(FVector(XCm, YCm, -28.0f));
            Normals.Add(FVector::UpVector);
            UVs.Add(FVector2D(XCm * 0.0001f, YCm * 0.0001f));
            Tangents.Add(FProcMeshTangent(FVector(1.0f, 0.0f, 0.0f), false));
            const float Variation = ValueNoise(XCm * 0.000006f + 70.0f, YCm * 0.000006f - 22.0f);
            Colors.Add(FMath::Lerp(
                FLinearColor(0.006f, 0.032f, 0.052f, 1.0f),
                FLinearColor(0.012f, 0.11f, 0.14f, 1.0f), Variation));
        }
    }

    for (int32 Y = 0; Y < Resolution - 1; ++Y)
    {
        for (int32 X = 0; X < Resolution - 1; ++X)
        {
            const int32 I = Y * Resolution + X;
            Triangles.Append({I, I + 1, I + Resolution, I + 1, I + Resolution + 1, I + Resolution});
        }
    }

    Ocean->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Aether/Materials/M_Ocean_Cinematic.M_Ocean_Cinematic"));
    if (!Material)
    {
        Material = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
    }
    if (Material)
    {
        Ocean->SetMaterial(0, Material);
        OceanMaterialInstance = Ocean->CreateDynamicMaterialInstance(0, Material);
        if (OceanMaterialInstance)
        {
            OceanMaterialInstance->SetScalarParameterValue(TEXT("SeaState"), CurrentSeaState);
            OceanMaterialInstance->SetScalarParameterValue(TEXT("OceanRoughness"), CurrentOceanRoughness);
            OceanMaterialInstance->SetScalarParameterValue(TEXT("WaveChoppiness"), CurrentWaveChoppiness);
            OceanMaterialInstance->SetScalarParameterValue(TEXT("FoamAmount"), CurrentFoamAmount);
            UE_LOG(LogTemp, Display, TEXT("[Aether Water] Dynamic Single Layer Water ocean is active."));
        }
    }
}

void AProceduralWorldDirector::UpdateOceanSurface(const float DeltaSeconds)
{
    if (DeltaSeconds > 0.0f)
    {
        CurrentSeaState = FMath::FInterpTo(CurrentSeaState, TargetSeaState, DeltaSeconds, 0.16f);
        CurrentOceanRoughness = FMath::FInterpTo(
            CurrentOceanRoughness, TargetOceanRoughness, DeltaSeconds, 0.22f);
        CurrentWaveChoppiness = FMath::FInterpTo(
            CurrentWaveChoppiness, TargetWaveChoppiness, DeltaSeconds, 0.18f);
        CurrentFoamAmount = FMath::FInterpTo(CurrentFoamAmount, TargetFoamAmount, DeltaSeconds, 0.18f);
    }

    if (OceanMaterialInstance)
    {
        OceanMaterialInstance->SetScalarParameterValue(TEXT("SeaState"), CurrentSeaState);
        OceanMaterialInstance->SetScalarParameterValue(TEXT("OceanRoughness"), CurrentOceanRoughness);
        OceanMaterialInstance->SetScalarParameterValue(TEXT("WaveChoppiness"), CurrentWaveChoppiness);
        OceanMaterialInstance->SetScalarParameterValue(TEXT("FoamAmount"), CurrentFoamAmount);
    }
}

void AProceduralWorldDirector::GenerateRunwayMarkings()
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;

    auto AddQuad = [&](const float XMin, const float XMax, const float YMin, const float YMax)
    {
        const int32 Start = Vertices.Num();
        const float Z = AirbaseLocation.Z + 112.0f;
        Vertices.Append({
            FVector(AirbaseLocation.X + XMin, AirbaseLocation.Y + YMin, Z),
            FVector(AirbaseLocation.X + XMax, AirbaseLocation.Y + YMin, Z),
            FVector(AirbaseLocation.X + XMin, AirbaseLocation.Y + YMax, Z),
            FVector(AirbaseLocation.X + XMax, AirbaseLocation.Y + YMax, Z)
        });
        Triangles.Append({Start, Start + 1, Start + 2, Start + 1, Start + 3, Start + 2});
        UVs.Append({FVector2D(0,0), FVector2D(1,0), FVector2D(0,1), FVector2D(1,1)});
        Colors.Append({FLinearColor::White, FLinearColor::White, FLinearColor::White, FLinearColor::White});
    };

    AddQuad(-105000.0f, 105000.0f, -3500.0f, -3250.0f);
    AddQuad(-105000.0f, 105000.0f, 3250.0f, 3500.0f);
    for (int32 I = -9; I <= 9; ++I)
    {
        const float X = I * 10000.0f;
        AddQuad(X - 2200.0f, X + 2200.0f, -115.0f, 115.0f);
    }

    UKismetProceduralMeshLibrary::CalculateTangentsForMesh(Vertices, Triangles, UVs, Normals, Tangents);
    RunwayMarkings->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Aether/Materials/M_RunwayMarkings_Cinematic.M_RunwayMarkings_Cinematic"));
    if (!Material)
    {
        Material = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
    }
    if (Material)
    {
        RunwayMarkings->SetMaterial(0, Material);
    }
}

void AProceduralWorldDirector::GenerateEnvironmentInstances()
{
    ForestInstances->ClearInstances();
    RockInstances->ClearInstances();

    UStaticMesh* ForestMesh = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/Aether/Environment/Foliage/SM_Conifer.SM_Conifer"));
    UStaticMesh* RockMesh = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/Aether/Environment/Rocks/SM_CliffRock.SM_CliffRock"));
    ForestInstances->SetStaticMesh(ForestMesh);
    RockInstances->SetStaticMesh(RockMesh);

    FRandomStream Random(WorldSeed * 7919 + 17);
    const float HalfWorldCm = TerrainSizeKilometers * 50000.0f;

    if (ForestMesh)
    {
        const int32 Attempts = ForestInstanceBudget * 5;
        for (int32 Attempt = 0; Attempt < Attempts && ForestInstances->GetInstanceCount() < ForestInstanceBudget; ++Attempt)
        {
            const float X = Random.FRandRange(-HalfWorldCm, HalfWorldCm);
            const float Y = Random.FRandRange(-HalfWorldCm, HalfWorldCm);
            float HeightM = 0.0f;
            FVector Normal = FVector::UpVector;
            if (!SampleGround(X, Y, HeightM, Normal))
            {
                continue;
            }
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            const float Moisture = ValueNoise(X * 0.000006f + 91.0f, Y * 0.000006f - 44.0f);
            const float RunwayX = FMath::Abs(X - AirbaseLocation.X);
            const float RunwayY = FMath::Abs(Y - AirbaseLocation.Y);
            if (HeightM < 24.0f || HeightM > 970.0f || Slope > 0.19f || Moisture < 0.38f
                || (RunwayX < 155000.0f && RunwayY < 18000.0f))
            {
                continue;
            }

            const FRotator SurfaceRotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
            const FRotator Rotation(SurfaceRotation.Pitch, Random.FRandRange(-180.0f, 180.0f), SurfaceRotation.Roll);
            const float Scale = Random.FRandRange(0.72f, 1.62f);
            ForestInstances->AddInstance(FTransform(
                Rotation, FVector(X, Y, HeightM * 100.0f - 12.0f), FVector(Scale)), false);
        }
    }

    if (RockMesh)
    {
        const int32 Attempts = RockInstanceBudget * 6;
        for (int32 Attempt = 0; Attempt < Attempts && RockInstances->GetInstanceCount() < RockInstanceBudget; ++Attempt)
        {
            const float X = Random.FRandRange(-HalfWorldCm, HalfWorldCm);
            const float Y = Random.FRandRange(-HalfWorldCm, HalfWorldCm);
            float HeightM = 0.0f;
            FVector Normal = FVector::UpVector;
            if (!SampleGround(X, Y, HeightM, Normal))
            {
                continue;
            }
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            const float Exposure = ValueNoise(X * 0.000012f - 14.0f, Y * 0.000012f + 62.0f);
            if (HeightM < 35.0f || Slope < 0.075f || Exposure < 0.47f)
            {
                continue;
            }

            const FRotator SurfaceRotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
            const FRotator Rotation(SurfaceRotation.Pitch, Random.FRandRange(-180.0f, 180.0f), SurfaceRotation.Roll);
            const FVector Scale(
                Random.FRandRange(0.7f, 2.8f), Random.FRandRange(0.7f, 2.2f), Random.FRandRange(0.6f, 2.5f));
            RockInstances->AddInstance(FTransform(
                Rotation, FVector(X, Y, HeightM * 100.0f - 35.0f), Scale), false);
        }
    }
}

bool AProceduralWorldDirector::HasProductionLandscape() const
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return false;
    }

    for (TActorIterator<ALandscapeProxy> It(World); It; ++It)
    {
        if (IsValid(*It) && !It->IsActorBeingDestroyed())
        {
            return true;
        }
    }
    return false;
}

bool AProceduralWorldDirector::HasAuthoredWater() const
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return false;
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        const AActor* Actor = *It;
        if (!IsValid(Actor) || Actor == this)
        {
            continue;
        }

        const FString ClassName = Actor->GetClass()->GetName();
        if (Actor->ActorHasTag(TEXT("AetherWater"))
            || ClassName.Contains(TEXT("WaterBodyOcean"), ESearchCase::IgnoreCase)
            || ClassName.Contains(TEXT("WaterBodyLake"), ESearchCase::IgnoreCase))
        {
            return true;
        }
    }
    return false;
}

bool AProceduralWorldDirector::SampleGround(
    const float XCentimeters, const float YCentimeters, float& OutHeightMeters, FVector& OutNormal) const
{
    if (bUsingProductionLandscape)
    {
        UWorld* World = GetWorld();
        if (World)
        {
            FHitResult Hit;
            FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(AetherLandscapeSample), false, this);
            const FVector Start(XCentimeters, YCentimeters, 1000000.0f);
            const FVector End(XCentimeters, YCentimeters, -300000.0f);
            if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, QueryParams))
            {
                OutHeightMeters = Hit.ImpactPoint.Z * 0.01f;
                OutNormal = Hit.ImpactNormal.GetSafeNormal();
                return true;
            }
            return false;
        }
    }

    OutHeightMeters = TerrainHeightMeters(XCentimeters, YCentimeters);
    OutNormal = TerrainNormal(XCentimeters, YCentimeters, 6000.0f);
    return true;
}

void AProceduralWorldDirector::ConfigureAtmosphere()
{
    if (UMaterialInterface* CloudMaterial = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst")))
    {
        VolumetricClouds->SetMaterial(CloudMaterial);
    }
}

void AProceduralWorldDirector::ApplyWeather(const EAetherWeather NewWeather, const bool bInstant)
{
    Weather = NewWeather;
    switch (Weather)
    {
    case EAetherWeather::GoldenClear:
        TargetStorminess = 0.04f;
        TargetFogDensity = 0.00055f;
        TargetSunIntensity = 7.5f;
        TargetSunColor = FLinearColor(1.0f, 0.67f, 0.43f);
        TargetSunRotation = FRotator(-12.0f, -48.0f, 0.0f);
        TargetSeaState = 0.34f;
        TargetOceanRoughness = 0.045f;
        TargetWaveChoppiness = 0.22f;
        TargetFoamAmount = 0.05f;
        break;
    case EAetherWeather::BrokenClouds:
        TargetStorminess = 0.22f;
        TargetFogDensity = 0.00115f;
        TargetSunIntensity = 5.8f;
        TargetSunColor = FLinearColor(0.93f, 0.96f, 1.0f);
        TargetSunRotation = FRotator(-28.0f, -35.0f, 0.0f);
        TargetSeaState = 0.68f;
        TargetOceanRoughness = 0.075f;
        TargetWaveChoppiness = 0.42f;
        TargetFoamAmount = 0.18f;
        break;
    case EAetherWeather::StormFront:
        TargetStorminess = 1.0f;
        TargetFogDensity = 0.0065f;
        TargetSunIntensity = 1.35f;
        TargetSunColor = FLinearColor(0.52f, 0.62f, 0.72f);
        TargetSunRotation = FRotator(-18.0f, 20.0f, 0.0f);
        TargetSeaState = 1.25f;
        TargetOceanRoughness = 0.15f;
        TargetWaveChoppiness = 0.72f;
        TargetFoamAmount = 0.60f;
        break;
    case EAetherWeather::BlueHour:
        TargetStorminess = 0.12f;
        TargetFogDensity = 0.0022f;
        TargetSunIntensity = 1.9f;
        TargetSunColor = FLinearColor(0.42f, 0.55f, 0.9f);
        TargetSunRotation = FRotator(-3.0f, -62.0f, 0.0f);
        TargetSeaState = 0.52f;
        TargetOceanRoughness = 0.06f;
        TargetWaveChoppiness = 0.34f;
        TargetFoamAmount = 0.12f;
        break;
    }

    if (bInstant)
    {
        CurrentStorminess = TargetStorminess;
        CurrentSeaState = TargetSeaState;
        CurrentOceanRoughness = TargetOceanRoughness;
        CurrentWaveChoppiness = TargetWaveChoppiness;
        CurrentFoamAmount = TargetFoamAmount;
        UpdateOceanSurface(0.0f);
        HeightFog->SetFogDensity(TargetFogDensity);
        Sun->SetIntensity(TargetSunIntensity);
        Sun->SetLightColor(TargetSunColor);
        Sun->SetWorldRotation(TargetSunRotation);
    }
}

float AProceduralWorldDirector::TerrainHeightMeters(const float XCentimeters, const float YCentimeters) const
{
    const float XMeters = XCentimeters * 0.01f;
    const float YMeters = YCentimeters * 0.01f;
    const float Raw = RawTerrainHeightMeters(XMeters, YMeters);
    const float DX = (XCentimeters - AirbaseLocation.X) / 145000.0f;
    const float DY = (YCentimeters - AirbaseLocation.Y) / 12000.0f;
    const float RunwayDistance = FMath::Sqrt(DX * DX + DY * DY);
    const float Flatten = 1.0f - FMath::SmoothStep(0.72f, 1.18f, RunwayDistance);
    return FMath::Lerp(Raw, AirbaseElevationMeters, Flatten);
}

float AProceduralWorldDirector::RawTerrainHeightMeters(const float XMeters, const float YMeters) const
{
    const float Continental = FractalNoise(XMeters * 0.000105f, YMeters * 0.000105f, 5, 0.54f);
    const float Detail = FractalNoise(XMeters * 0.00042f + 19.0f, YMeters * 0.00042f - 7.0f, 4, 0.5f);
    const float RidgeNoise = FractalNoise(XMeters * 0.00022f - 31.0f, YMeters * 0.00022f + 11.0f, 5, 0.56f);
    const float Ridge = 1.0f - FMath::Abs(RidgeNoise * 2.0f - 1.0f);
    const float Land = FMath::SmoothStep(0.44f, 0.59f, Continental + (Detail - 0.5f) * 0.16f);
    const float Mountains = FMath::Pow(FMath::Clamp(Ridge, 0.0f, 1.0f), 2.4f) * 1850.0f;
    const float Hills = Detail * 430.0f;
    return -210.0f + Land * (255.0f + Hills + Mountains);
}

float AProceduralWorldDirector::FractalNoise(float X, float Y, const int32 Octaves, const float Persistence) const
{
    float Total = 0.0f;
    float Amplitude = 1.0f;
    float Normalizer = 0.0f;
    for (int32 I = 0; I < Octaves; ++I)
    {
        Total += ValueNoise(X, Y) * Amplitude;
        Normalizer += Amplitude;
        X *= 2.03f;
        Y *= 2.03f;
        Amplitude *= Persistence;
    }
    return Total / FMath::Max(Normalizer, SMALL_NUMBER);
}

float AProceduralWorldDirector::ValueNoise(const float X, const float Y) const
{
    const int32 X0 = FMath::FloorToInt(X);
    const int32 Y0 = FMath::FloorToInt(Y);
    const float TX = FMath::SmoothStep(0.0f, 1.0f, X - X0);
    const float TY = FMath::SmoothStep(0.0f, 1.0f, Y - Y0);
    const float A = FMath::Lerp(HashNoise(X0, Y0), HashNoise(X0 + 1, Y0), TX);
    const float B = FMath::Lerp(HashNoise(X0, Y0 + 1), HashNoise(X0 + 1, Y0 + 1), TX);
    return FMath::Lerp(A, B, TY);
}

float AProceduralWorldDirector::HashNoise(const int32 X, const int32 Y) const
{
    uint32 N = static_cast<uint32>(X) * 374761393u + static_cast<uint32>(Y) * 668265263u
        + static_cast<uint32>(WorldSeed) * 1442695041u;
    N = (N ^ (N >> 13u)) * 1274126177u;
    return static_cast<float>(N ^ (N >> 16u)) / static_cast<float>(MAX_uint32);
}

FVector AProceduralWorldDirector::TerrainNormal(
    const float XCentimeters, const float YCentimeters, const float SampleDistanceCentimeters) const
{
    const float Sample = FMath::Max(SampleDistanceCentimeters, 100.0f);
    const float HeightLeft = TerrainHeightMeters(XCentimeters - Sample, YCentimeters) * 100.0f;
    const float HeightRight = TerrainHeightMeters(XCentimeters + Sample, YCentimeters) * 100.0f;
    const float HeightBack = TerrainHeightMeters(XCentimeters, YCentimeters - Sample) * 100.0f;
    const float HeightFront = TerrainHeightMeters(XCentimeters, YCentimeters + Sample) * 100.0f;
    return FVector(HeightLeft - HeightRight, HeightBack - HeightFront, Sample * 2.0f).GetSafeNormal();
}

FLinearColor AProceduralWorldDirector::TerrainBiomeColor(
    const float HeightMeters, const float Slope, const float XCentimeters, const float YCentimeters) const
{
    const float Macro = ValueNoise(XCentimeters * 0.0000055f + 18.0f, YCentimeters * 0.0000055f - 37.0f);
    const float Micro = ValueNoise(XCentimeters * 0.000029f - 73.0f, YCentimeters * 0.000029f + 29.0f);
    const float Variation = 0.86f + Macro * 0.16f + Micro * 0.07f;

    const FLinearColor WetSand(0.17f, 0.15f, 0.105f, 1.0f);
    const FLinearColor DryGrass(0.18f, 0.215f, 0.105f, 1.0f);
    const FLinearColor AlpineGreen(0.045f, 0.115f, 0.055f, 1.0f);
    const FLinearColor Granite(0.23f, 0.235f, 0.22f, 1.0f);
    const FLinearColor DarkCliff(0.105f, 0.115f, 0.11f, 1.0f);
    const FLinearColor Snow(0.72f, 0.755f, 0.76f, 1.0f);

    FLinearColor Base;
    if (HeightMeters < 8.0f)
    {
        Base = WetSand;
    }
    else if (HeightMeters < 170.0f)
    {
        Base = FMath::Lerp(DryGrass, AlpineGreen, FMath::Clamp((HeightMeters - 8.0f) / 162.0f, 0.0f, 1.0f));
    }
    else if (HeightMeters < 820.0f)
    {
        Base = AlpineGreen;
    }
    else if (HeightMeters < 1380.0f)
    {
        Base = FMath::Lerp(AlpineGreen, Granite, FMath::Clamp((HeightMeters - 820.0f) / 560.0f, 0.0f, 1.0f));
    }
    else
    {
        Base = FMath::Lerp(Granite, Snow, FMath::Clamp((HeightMeters - 1380.0f) / 520.0f, 0.0f, 1.0f));
    }

    const float CliffBlend = FMath::SmoothStep(0.055f, 0.24f, Slope);
    Base = FMath::Lerp(Base, DarkCliff, CliffBlend * (HeightMeters > 1300.0f ? 0.55f : 0.88f));
    const float SnowBlend = FMath::SmoothStep(1420.0f, 1830.0f, HeightMeters) * (1.0f - CliffBlend * 0.7f);
    Base = FMath::Lerp(Base, Snow, SnowBlend);
    Base.R *= Variation;
    Base.G *= Variation;
    Base.B *= Variation;
    Base.A = 1.0f;
    return Base;
}
