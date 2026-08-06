#include "ProceduralBiomeDirector.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "LandscapeProxy.h"
#include "Math/RotationMatrix.h"
#include "TimerManager.h"

AProceduralBiomeDirector::AProceduralBiomeDirector()
{
    PrimaryActorTick.bCanEverTick = false;

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    ResetDefaultBiomes();
}

void AProceduralBiomeDirector::BeginPlay()
{
    Super::BeginPlay();

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimerForNextTick(
            FTimerDelegate::CreateUObject(this, &AProceduralBiomeDirector::BuildRuntimeBiomes));
    }
}

void AProceduralBiomeDirector::BuildRuntimeBiomes()
{
    if (bDisableLegacyForestAndRocks)
    {
        DisableLegacyEnvironment();
    }

    if (bBuildOnBeginPlay)
    {
        BuildBiomes();
    }
}

void AProceduralBiomeDirector::BuildBiomes()
{
#if WITH_EDITOR
    Modify();
#endif

    ClearBiomes();

    if (bDisableLegacyForestAndRocks)
    {
        DisableLegacyEnvironment();
    }

    bool bHasAnyMesh = false;
    for (const FProceduralBiomeDefinition& Biome : Biomes)
    {
        if (!Biome.bEnabled)
        {
            continue;
        }

        for (const FProceduralBiomeMesh& MeshEntry : Biome.Meshes)
        {
            if (IsValid(MeshEntry.Mesh) && MeshEntry.Weight > 0.0f)
            {
                bHasAnyMesh = true;
                break;
            }
        }

        if (bHasAnyMesh)
        {
            break;
        }
    }

    if (!bHasAnyMesh || SampleCount <= 0)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Biomes] No valid biome meshes are assigned, or SampleCount is zero."));
        return;
    }

    const bool bLandscapeExists = HasLandscape();
    FRandomStream Random(Seed * 7919 + 313);
    TMap<UStaticMesh*, UHierarchicalInstancedStaticMeshComponent*> ComponentsByMesh;

    int32 GeneratedCount = 0;
    for (int32 SampleIndex = 0; SampleIndex < SampleCount; ++SampleIndex)
    {
        const float X = WorldCenterCentimeters.X
            + Random.FRandRange(-WorldHalfExtentCentimeters.X, WorldHalfExtentCentimeters.X);
        const float Y = WorldCenterCentimeters.Y
            + Random.FRandRange(-WorldHalfExtentCentimeters.Y, WorldHalfExtentCentimeters.Y);

        if (bProtectAirbase
            && FMath::Abs(X - AirbaseCenterCentimeters.X) <= AirbaseExclusionHalfExtentCentimeters.X
            && FMath::Abs(Y - AirbaseCenterCentimeters.Y) <= AirbaseExclusionHalfExtentCentimeters.Y)
        {
            continue;
        }

        FVector GroundLocation;
        FVector GroundNormal;
        if (!TraceGround(X, Y, bLandscapeExists, GroundLocation, GroundNormal))
        {
            continue;
        }

        const float ElevationMeters = GroundLocation.Z * 0.01f;
        const float Moisture = FractalNoise(
            X * MoistureNoiseScale + 91.0f,
            Y * MoistureNoiseScale - 44.0f,
            4,
            0.52f,
            17);
        const float TemperatureNoise = FractalNoise(
            X * TemperatureNoiseScale - 31.0f,
            Y * TemperatureNoiseScale + 73.0f,
            4,
            0.50f,
            41);
        const float Temperature = FMath::Clamp(
            TemperatureNoise
                - FMath::Max(0.0f, ElevationMeters) * 0.001f * ElevationCoolingPerKilometer,
            0.0f,
            1.0f);
        const float PatchValue = FractalNoise(
            X * PatchNoiseScale + 151.0f,
            Y * PatchNoiseScale - 207.0f,
            3,
            0.58f,
            79);

        const FProceduralBiomeDefinition* BestBiome = nullptr;
        float BestScore = 0.0f;
        for (const FProceduralBiomeDefinition& Biome : Biomes)
        {
            const float Score = BiomeScore(
                Biome,
                ElevationMeters,
                Moisture,
                Temperature,
                GroundNormal.Z);
            if (Score > BestScore)
            {
                BestScore = Score;
                BestBiome = &Biome;
            }
        }

        if (!BestBiome)
        {
            continue;
        }

        const float SpawnChance = FMath::Clamp(
            BestBiome->Density * FMath::Lerp(1.0f, PatchValue, BestBiome->Patchiness),
            0.0f,
            1.0f);
        if (Random.FRand() > SpawnChance)
        {
            continue;
        }

        const FProceduralBiomeMesh* MeshEntry = ChooseMesh(*BestBiome, Random);
        if (!MeshEntry || !IsValid(MeshEntry->Mesh))
        {
            continue;
        }

        UHierarchicalInstancedStaticMeshComponent* MeshComponent =
            GetOrCreateMeshComponent(MeshEntry->Mesh, ComponentsByMesh);
        if (!MeshComponent)
        {
            continue;
        }

        const float MinScale = FMath::Min(
            MeshEntry->UniformScaleRange.X,
            MeshEntry->UniformScaleRange.Y);
        const float MaxScale = FMath::Max(
            MeshEntry->UniformScaleRange.X,
            MeshEntry->UniformScaleRange.Y);
        const float Scale = Random.FRandRange(
            FMath::Max(0.01f, MinScale),
            FMath::Max(0.01f, MaxScale));

        FQuat Rotation = MeshEntry->bAlignToSurface
            ? FRotationMatrix::MakeFromZ(GroundNormal).ToQuat()
            : FQuat::Identity;
        if (MeshEntry->bRandomYaw)
        {
            const FQuat YawRotation(
                GroundNormal,
                FMath::DegreesToRadians(Random.FRandRange(-180.0f, 180.0f)));
            Rotation = YawRotation * Rotation;
        }

        const FVector InstanceLocation =
            GroundLocation + GroundNormal * MeshEntry->ZOffsetCentimeters;
        MeshComponent->AddInstance(
            FTransform(Rotation, InstanceLocation, FVector(Scale)),
            true);
        ++GeneratedCount;
    }

    for (const TPair<UStaticMesh*, UHierarchicalInstancedStaticMeshComponent*>& Pair : ComponentsByMesh)
    {
        if (IsValid(Pair.Value))
        {
            Pair.Value->MarkRenderStateDirty();
        }
    }

    LastGeneratedInstanceCount = GeneratedCount;
    UE_LOG(LogTemp, Display,
        TEXT("[Aether Biomes] Generated %d instances from %d samples across %d biome profiles."),
        GeneratedCount,
        SampleCount,
        Biomes.Num());
}

void AProceduralBiomeDirector::ClearBiomes()
{
#if WITH_EDITOR
    Modify();
#endif

    TArray<UHierarchicalInstancedStaticMeshComponent*> GeneratedComponents;
    GetComponents(GeneratedComponents);

    const FName Tag = GeneratedComponentTag();
    for (UHierarchicalInstancedStaticMeshComponent* Component : GeneratedComponents)
    {
        if (!IsValid(Component) || !Component->ComponentHasTag(Tag))
        {
            continue;
        }

        Component->ClearInstances();
        RemoveInstanceComponent(Component);
        Component->DestroyComponent();
    }

    LastGeneratedInstanceCount = 0;
}

void AProceduralBiomeDirector::ResetDefaultBiomes()
{
    Biomes.Reset();

    FProceduralBiomeDefinition Meadow;
    Meadow.BiomeName = TEXT("Meadow");
    Meadow.MinElevationMeters = -100.0f;
    Meadow.MaxElevationMeters = 700.0f;
    Meadow.MinMoisture = 0.20f;
    Meadow.MaxMoisture = 0.82f;
    Meadow.MinTemperature = 0.36f;
    Meadow.MaxTemperature = 1.0f;
    Meadow.MinGroundNormalZ = 0.94f;
    Meadow.Density = 0.30f;
    Meadow.Patchiness = 0.42f;
    Meadow.Priority = 1.0f;
    Biomes.Add(Meadow);

    FProceduralBiomeDefinition EvergreenForest;
    EvergreenForest.BiomeName = TEXT("EvergreenForest");
    EvergreenForest.MinElevationMeters = 30.0f;
    EvergreenForest.MaxElevationMeters = 1150.0f;
    EvergreenForest.MinMoisture = 0.46f;
    EvergreenForest.MaxMoisture = 1.0f;
    EvergreenForest.MinTemperature = 0.24f;
    EvergreenForest.MaxTemperature = 0.88f;
    EvergreenForest.MinGroundNormalZ = 0.82f;
    EvergreenForest.Density = 0.72f;
    EvergreenForest.Patchiness = 0.55f;
    EvergreenForest.Priority = 1.25f;
    Biomes.Add(EvergreenForest);

    FProceduralBiomeDefinition RockyHighlands;
    RockyHighlands.BiomeName = TEXT("RockyHighlands");
    RockyHighlands.MinElevationMeters = 420.0f;
    RockyHighlands.MaxElevationMeters = 1900.0f;
    RockyHighlands.MinMoisture = 0.0f;
    RockyHighlands.MaxMoisture = 1.0f;
    RockyHighlands.MinTemperature = 0.08f;
    RockyHighlands.MaxTemperature = 0.78f;
    RockyHighlands.MinGroundNormalZ = 0.48f;
    RockyHighlands.Density = 0.44f;
    RockyHighlands.Patchiness = 0.48f;
    RockyHighlands.Priority = 1.10f;
    Biomes.Add(RockyHighlands);

    FProceduralBiomeDefinition AlpineSnow;
    AlpineSnow.BiomeName = TEXT("AlpineSnow");
    AlpineSnow.MinElevationMeters = 1050.0f;
    AlpineSnow.MaxElevationMeters = 5000.0f;
    AlpineSnow.MinMoisture = 0.0f;
    AlpineSnow.MaxMoisture = 1.0f;
    AlpineSnow.MinTemperature = 0.0f;
    AlpineSnow.MaxTemperature = 0.48f;
    AlpineSnow.MinGroundNormalZ = 0.52f;
    AlpineSnow.Density = 0.22f;
    AlpineSnow.Patchiness = 0.32f;
    AlpineSnow.Priority = 1.45f;
    Biomes.Add(AlpineSnow);
}

void AProceduralBiomeDirector::DisableLegacyEnvironment()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!IsValid(Actor) || Actor == this)
        {
            continue;
        }

        TArray<UHierarchicalInstancedStaticMeshComponent*> Components;
        Actor->GetComponents(Components);
        for (UHierarchicalInstancedStaticMeshComponent* Component : Components)
        {
            if (!IsValid(Component))
            {
                continue;
            }

            const FName ComponentName = Component->GetFName();
            if (ComponentName == TEXT("ProceduralForest")
                || ComponentName == TEXT("ProceduralRocks"))
            {
                Component->ClearInstances();
                Component->SetVisibility(false, true);
            }
        }
    }
}

bool AProceduralBiomeDirector::HasLandscape() const
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

bool AProceduralBiomeDirector::TraceGround(
    const float X,
    const float Y,
    const bool bLandscapeExists,
    FVector& OutLocation,
    FVector& OutNormal) const
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return false;
    }

    FHitResult Hit;
    FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(AetherBiomeGroundTrace), false, this);
    const FVector Start(X, Y, TraceTopZ);
    const FVector End(X, Y, TraceBottomZ);
    if (!World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, QueryParams))
    {
        return false;
    }

    if (bLandscapeExists
        && bRequireLandscapeHitWhenLandscapeExists
        && (!Hit.GetActor() || !Hit.GetActor()->IsA<ALandscapeProxy>()))
    {
        return false;
    }

    OutLocation = Hit.ImpactPoint;
    OutNormal = Hit.ImpactNormal.GetSafeNormal();
    return true;
}

float AProceduralBiomeDirector::BiomeScore(
    const FProceduralBiomeDefinition& Biome,
    const float ElevationMeters,
    const float Moisture,
    const float Temperature,
    const float GroundNormalZ) const
{
    if (!Biome.bEnabled
        || Biome.Meshes.IsEmpty()
        || ElevationMeters < Biome.MinElevationMeters
        || ElevationMeters > Biome.MaxElevationMeters
        || Moisture < Biome.MinMoisture
        || Moisture > Biome.MaxMoisture
        || Temperature < Biome.MinTemperature
        || Temperature > Biome.MaxTemperature
        || GroundNormalZ < Biome.MinGroundNormalZ)
    {
        return 0.0f;
    }

    auto RangePreference = [](const float Value, const float Minimum, const float Maximum)
    {
        const float Width = Maximum - Minimum;
        if (Width <= KINDA_SMALL_NUMBER)
        {
            return 1.0f;
        }

        const float Normalized = FMath::Clamp((Value - Minimum) / Width, 0.0f, 1.0f);
        const float CenterPreference = 1.0f - FMath::Abs(Normalized * 2.0f - 1.0f);
        return 0.55f + CenterPreference * 0.45f;
    };

    const float ElevationPreference = RangePreference(
        ElevationMeters,
        Biome.MinElevationMeters,
        Biome.MaxElevationMeters);
    const float MoisturePreference = RangePreference(
        Moisture,
        Biome.MinMoisture,
        Biome.MaxMoisture);
    const float TemperaturePreference = RangePreference(
        Temperature,
        Biome.MinTemperature,
        Biome.MaxTemperature);
    const float SlopePreference = FMath::GetMappedRangeValueClamped(
        FVector2D(Biome.MinGroundNormalZ, 1.0f),
        FVector2D(0.65f, 1.0f),
        GroundNormalZ);

    return Biome.Priority
        * ElevationPreference
        * MoisturePreference
        * TemperaturePreference
        * SlopePreference;
}

const FProceduralBiomeMesh* AProceduralBiomeDirector::ChooseMesh(
    const FProceduralBiomeDefinition& Biome,
    FRandomStream& Random) const
{
    float TotalWeight = 0.0f;
    for (const FProceduralBiomeMesh& MeshEntry : Biome.Meshes)
    {
        if (IsValid(MeshEntry.Mesh) && MeshEntry.Weight > 0.0f)
        {
            TotalWeight += MeshEntry.Weight;
        }
    }

    if (TotalWeight <= SMALL_NUMBER)
    {
        return nullptr;
    }

    float Selection = Random.FRandRange(0.0f, TotalWeight);
    for (const FProceduralBiomeMesh& MeshEntry : Biome.Meshes)
    {
        if (!IsValid(MeshEntry.Mesh) || MeshEntry.Weight <= 0.0f)
        {
            continue;
        }

        Selection -= MeshEntry.Weight;
        if (Selection <= 0.0f)
        {
            return &MeshEntry;
        }
    }

    return nullptr;
}

UHierarchicalInstancedStaticMeshComponent* AProceduralBiomeDirector::GetOrCreateMeshComponent(
    UStaticMesh* Mesh,
    TMap<UStaticMesh*, UHierarchicalInstancedStaticMeshComponent*>& ComponentsByMesh)
{
    if (!IsValid(Mesh))
    {
        return nullptr;
    }

    if (UHierarchicalInstancedStaticMeshComponent** Existing = ComponentsByMesh.Find(Mesh))
    {
        return *Existing;
    }

    const FName ComponentName = MakeUniqueObjectName(
        this,
        UHierarchicalInstancedStaticMeshComponent::StaticClass(),
        *FString::Printf(TEXT("Biome_%s"), *Mesh->GetName()));

    UHierarchicalInstancedStaticMeshComponent* Component =
        NewObject<UHierarchicalInstancedStaticMeshComponent>(
            this,
            ComponentName,
            RF_Transactional);
    if (!Component)
    {
        return nullptr;
    }

    Component->SetupAttachment(Root);
    Component->SetStaticMesh(Mesh);
    Component->SetMobility(EComponentMobility::Static);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetCullDistances(StartCullDistance, EndCullDistance);
    Component->bCastDynamicShadow = true;
    Component->ComponentTags.Add(GeneratedComponentTag());

    AddInstanceComponent(Component);
    Component->RegisterComponent();

    ComponentsByMesh.Add(Mesh, Component);
    return Component;
}

float AProceduralBiomeDirector::FractalNoise(
    const float X,
    const float Y,
    const int32 Octaves,
    const float Persistence,
    const int32 SeedOffset) const
{
    float Total = 0.0f;
    float Frequency = 1.0f;
    float Amplitude = 1.0f;
    float Normalization = 0.0f;

    for (int32 Octave = 0; Octave < Octaves; ++Octave)
    {
        Total += ValueNoise(X * Frequency, Y * Frequency, SeedOffset + Octave * 1013) * Amplitude;
        Normalization += Amplitude;
        Frequency *= 2.0f;
        Amplitude *= Persistence;
    }

    return Normalization > SMALL_NUMBER ? Total / Normalization : 0.5f;
}

float AProceduralBiomeDirector::ValueNoise(
    const float X,
    const float Y,
    const int32 SeedOffset) const
{
    const int32 X0 = FMath::FloorToInt(X);
    const int32 Y0 = FMath::FloorToInt(Y);
    const int32 X1 = X0 + 1;
    const int32 Y1 = Y0 + 1;

    const float TX = X - static_cast<float>(X0);
    const float TY = Y - static_cast<float>(Y0);
    const float SmoothX = TX * TX * (3.0f - 2.0f * TX);
    const float SmoothY = TY * TY * (3.0f - 2.0f * TY);

    const float A = FMath::Lerp(HashNoise(X0, Y0, SeedOffset), HashNoise(X1, Y0, SeedOffset), SmoothX);
    const float B = FMath::Lerp(HashNoise(X0, Y1, SeedOffset), HashNoise(X1, Y1, SeedOffset), SmoothX);
    return FMath::Lerp(A, B, SmoothY);
}

float AProceduralBiomeDirector::HashNoise(
    const int32 X,
    const int32 Y,
    const int32 SeedOffset) const
{
    uint32 Hash = static_cast<uint32>(X) * 0x8da6b343u;
    Hash ^= static_cast<uint32>(Y) * 0xd8163841u;
    Hash ^= static_cast<uint32>(Seed + SeedOffset) * 0xcb1ab31fu;
    Hash ^= Hash >> 13;
    Hash *= 0x85ebca6bu;
    Hash ^= Hash >> 16;
    return static_cast<float>(Hash & 0x00ffffffu) / static_cast<float>(0x00ffffffu);
}

FName AProceduralBiomeDirector::GeneratedComponentTag()
{
    static const FName Tag(TEXT("AetherBiomeGenerated"));
    return Tag;
}
