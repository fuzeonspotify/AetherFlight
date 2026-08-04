#include "AetherMapWideEnvironmentActor.h"

#include "AetherBiomeScatterActor.h"
#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Modules/ModuleManager.h"

namespace AetherMapEnvironment
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr float HalfWorldCm = 2400000.0f;
    constexpr float WorldInsetCm = 12000.0f;
    constexpr int32 MaxPrepareAttempts = 12;

    float SpatialField(const float X, const float Y, const float Frequency, const float Phase)
    {
        return 0.5f + 0.25f * FMath::Sin(X * Frequency + Phase)
            + 0.25f * FMath::Cos(Y * Frequency * 1.17f - Phase * 0.73f);
    }
}

AAetherMapWideEnvironmentActor::AAetherMapWideEnvironmentActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);
}

void AAetherMapWideEnvironmentActor::BeginPlay()
{
    Super::BeginPlay();
    if (!bEnableMapWideEnvironment || !GetWorld())
    {
        return;
    }

    DisableLegacyEnvironment();
    GetWorldTimerManager().SetTimer(
        PrepareTimer,
        this,
        &AAetherMapWideEnvironmentActor::PrepareEnvironment,
        3.0f,
        false);
}

void AAetherMapWideEnvironmentActor::DisableLegacyEnvironment()
{
    for (TActorIterator<AAetherBiomeScatterActor> It(GetWorld()); It; ++It)
    {
        It->ClearEnvironment();
        It->SetActorHiddenInGame(true);
    }
}

bool AAetherMapWideEnvironmentActor::IsUnsafeAggregateMeshName(const FString& Name) const
{
    static const TCHAR* RejectedTokens[] = {
        TEXT("Cluster"), TEXT("Forest"), TEXT("Group"), TEXT("Merged"),
        TEXT("Billboard"), TEXT("Impostor"), TEXT("Imposter"), TEXT("Proxy"),
        TEXT("Collision"), TEXT("_LOD"), TEXT("LOD_")
    };
    for (const TCHAR* Token : RejectedTokens)
    {
        if (Name.Contains(Token, ESearchCase::IgnoreCase))
        {
            return true;
        }
    }
    return false;
}

TArray<UStaticMesh*> AAetherMapWideEnvironmentActor::LoadSuitableMeshes(
    const TArray<FName>& Paths,
    const TArray<FString>& RequiredKeywords,
    const int32 MaxMeshes,
    const float DesiredHeightCm,
    const float MinimumHeightCm,
    const float MaximumHeightCm,
    const float MaximumWidthToHeight) const
{
    TArray<UStaticMesh*> Result;
    if (Paths.Num() == 0 || MaxMeshes <= 0)
    {
        return Result;
    }

    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    FARFilter Filter;
    Filter.PackagePaths.Append(Paths);
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;

    TArray<FAssetData> Assets;
    AssetRegistryModule.Get().GetAssets(Filter, Assets);
    Assets.Sort([](const FAssetData& Left, const FAssetData& Right)
    {
        return Left.AssetName.ToString() < Right.AssetName.ToString();
    });

    TArray<TPair<float, UStaticMesh*>> Candidates;
    int32 LoadedAssets = 0;
    for (const FAssetData& Asset : Assets)
    {
        const FString Name = Asset.AssetName.ToString();
        if (IsUnsafeAggregateMeshName(Name))
        {
            continue;
        }

        bool bKeywordMatch = RequiredKeywords.Num() == 0;
        for (const FString& Keyword : RequiredKeywords)
        {
            if (Name.Contains(Keyword, ESearchCase::IgnoreCase))
            {
                bKeywordMatch = true;
                break;
            }
        }
        if (!bKeywordMatch || ++LoadedAssets > 128)
        {
            continue;
        }

        UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset());
        if (!Mesh)
        {
            continue;
        }

        const FBoxSphereBounds Bounds = Mesh->GetBounds();
        const float HeightCm = Bounds.BoxExtent.Z * 2.0f;
        const float WidthCm = FMath::Max(Bounds.BoxExtent.X, Bounds.BoxExtent.Y) * 2.0f;
        if (HeightCm < MinimumHeightCm || HeightCm > MaximumHeightCm
            || WidthCm / FMath::Max(HeightCm, 1.0f) > MaximumWidthToHeight)
        {
            continue;
        }

        const float HeightError = FMath::Abs(HeightCm - DesiredHeightCm)
            / FMath::Max(DesiredHeightCm, 1.0f);
        const float ShapePenalty = WidthCm / FMath::Max(HeightCm, 1.0f) * 0.08f;
        Candidates.Emplace(HeightError + ShapePenalty, Mesh);
    }

    Candidates.Sort([](const TPair<float, UStaticMesh*>& Left, const TPair<float, UStaticMesh*>& Right)
    {
        return Left.Key < Right.Key;
    });
    for (int32 Index = 0; Index < Candidates.Num() && Result.Num() < MaxMeshes; ++Index)
    {
        Result.AddUnique(Candidates[Index].Value);
    }
    return Result;
}

UStaticMesh* AAetherMapWideEnvironmentActor::LoadFirstKeywordMesh(
    const TArray<FName>& Paths,
    const TArray<FString>& Keywords,
    const float MinimumHeightCm,
    const float MaximumHeightCm) const
{
    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    FARFilter Filter;
    Filter.PackagePaths.Append(Paths);
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;

    TArray<FAssetData> Assets;
    AssetRegistryModule.Get().GetAssets(Filter, Assets);
    Assets.Sort([](const FAssetData& Left, const FAssetData& Right)
    {
        return Left.AssetName.ToString() < Right.AssetName.ToString();
    });

    int32 LoadedAssets = 0;
    for (const FAssetData& Asset : Assets)
    {
        const FString Name = Asset.AssetName.ToString();
        if (IsUnsafeAggregateMeshName(Name))
        {
            continue;
        }

        bool bKeywordMatch = false;
        for (const FString& Keyword : Keywords)
        {
            if (Name.Contains(Keyword, ESearchCase::IgnoreCase))
            {
                bKeywordMatch = true;
                break;
            }
        }
        if (!bKeywordMatch || ++LoadedAssets > 96)
        {
            continue;
        }

        UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset());
        if (!Mesh)
        {
            continue;
        }
        const float HeightCm = Mesh->GetBounds().BoxExtent.Z * 2.0f;
        if (HeightCm >= MinimumHeightCm && HeightCm <= MaximumHeightCm)
        {
            return Mesh;
        }
    }
    return nullptr;
}

bool AAetherMapWideEnvironmentActor::LoadEnvironmentAssets()
{
    TreeMeshes.Reset();
    RockMeshes.Reset();
    ShrubMesh = nullptr;

    const TArray<UStaticMesh*> LoadedTrees = LoadSuitableMeshes({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Windmill_Palm")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Coconut_Tree"))
    }, {
        TEXT("tree"), TEXT("pine"), TEXT("aspen"), TEXT("oak"),
        TEXT("conifer"), TEXT("palm"), TEXT("coconut")
    }, 3, 2300.0f, 450.0f, 12000.0f, 2.7f);
    for (UStaticMesh* Mesh : LoadedTrees)
    {
        TreeMeshes.Add(Mesh);
    }

    const TArray<UStaticMesh*> LoadedRocks = LoadSuitableMeshes({
        FName(TEXT("/Game/Aether/Environment/Rocks")),
        FName(TEXT("/Game/Rocks")),
        FName(TEXT("/Game/Rock_01")),
        FName(TEXT("/Game/Rock_02")),
        FName(TEXT("/Game/Rock_03")),
        FName(TEXT("/Game/Rock_04")),
        FName(TEXT("/Game/Rock_05")),
        FName(TEXT("/Game/Rock_06")),
        FName(TEXT("/Game/Rock_07"))
    }, {
        TEXT("rock"), TEXT("boulder"), TEXT("stone"), TEXT("cliff")
    }, 3, 450.0f, 40.0f, 8000.0f, 5.0f);
    for (UStaticMesh* Mesh : LoadedRocks)
    {
        RockMeshes.Add(Mesh);
    }

    ShrubMesh = LoadFirstKeywordMesh({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets"))
    }, {
        TEXT("shrub"), TEXT("bush"), TEXT("sapling"), TEXT("fern")
    }, 20.0f, 1400.0f);

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] Assets: trees=%d shrub=%s rocks=%d."),
        TreeMeshes.Num(),
        ShrubMesh ? *ShrubMesh->GetPathName() : TEXT("None"),
        RockMeshes.Num());

    for (int32 Index = 0; Index < TreeMeshes.Num(); ++Index)
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Map Environment] Tree %d: %s"),
            Index + 1,
            *TreeMeshes[Index]->GetPathName());
    }
    for (int32 Index = 0; Index < RockMeshes.Num(); ++Index)
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Map Environment] Rock %d: %s"),
            Index + 1,
            *RockMeshes[Index]->GetPathName());
    }

    return TreeMeshes.Num() > 0 || ShrubMesh != nullptr || RockMeshes.Num() > 0;
}

bool AAetherMapWideEnvironmentActor::LooksLikeWater(const FHitResult& Hit) const
{
    FString CombinedName;
    if (const AActor* Actor = Hit.GetActor())
    {
        CombinedName += Actor->GetName();
        CombinedName += Actor->GetClass()->GetName();
    }
    if (const UPrimitiveComponent* Component = Hit.GetComponent())
    {
        CombinedName += Component->GetName();
        CombinedName += Component->GetClass()->GetName();
    }
    return CombinedName.Contains(TEXT("Water"), ESearchCase::IgnoreCase)
        || CombinedName.Contains(TEXT("Ocean"), ESearchCase::IgnoreCase)
        || CombinedName.Contains(TEXT("Lake"), ESearchCase::IgnoreCase);
}

bool AAetherMapWideEnvironmentActor::SampleTerrain(
    const float X,
    const float Y,
    FVector& OutLocation,
    FVector& OutNormal) const
{
    if (!GetWorld())
    {
        return false;
    }

    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(AetherMapEnvironmentTrace), false, this);
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Params.AddIgnoredActor(Controller->GetPawn());
    }

    if (!GetWorld()->LineTraceSingleByChannel(
            Hit,
            FVector(X, Y, AetherMapEnvironment::TraceTopCm),
            FVector(X, Y, AetherMapEnvironment::TraceBottomCm),
            ECC_Visibility,
            Params)
        || LooksLikeWater(Hit))
    {
        return false;
    }

    const AActor* HitActor = Hit.GetActor();
    const UPrimitiveComponent* HitComponent = Hit.GetComponent();
    if (!HitActor || !HitComponent || HitActor->ActorHasTag(TEXT("AetherLegacyLandscape")))
    {
        return false;
    }

    const FString CombinedName = HitActor->GetName()
        + HitActor->GetClass()->GetName()
        + HitComponent->GetName()
        + HitComponent->GetClass()->GetName();
    const bool bProductionTerrain = HitActor->ActorHasTag(TEXT("AetherProductionTerrain"))
        || CombinedName.Contains(TEXT("MeshTerrain"), ESearchCase::IgnoreCase)
        || CombinedName.Contains(TEXT("MeshPartition"), ESearchCase::IgnoreCase)
        || CombinedName.Contains(TEXT("CompiledSection"), ESearchCase::IgnoreCase);
    if (!bProductionTerrain)
    {
        return false;
    }

    OutLocation = Hit.ImpactPoint;
    OutNormal = Hit.ImpactNormal.GetSafeNormal();
    return OutNormal.Z > 0.05f;
}

FBox2D AAetherMapWideEnvironmentActor::GetChunkBounds(const FIntPoint& Chunk) const
{
    const float SafeChunkSize = FMath::Max(80000.0f, ChunkSizeCm);
    FBox2D Bounds(
        FVector2D(Chunk.X * SafeChunkSize, Chunk.Y * SafeChunkSize),
        FVector2D((Chunk.X + 1) * SafeChunkSize, (Chunk.Y + 1) * SafeChunkSize));
    const float Minimum = -AetherMapEnvironment::HalfWorldCm + AetherMapEnvironment::WorldInsetCm;
    const float Maximum = AetherMapEnvironment::HalfWorldCm - AetherMapEnvironment::WorldInsetCm;
    Bounds.Min.X = FMath::Max(Bounds.Min.X, Minimum);
    Bounds.Min.Y = FMath::Max(Bounds.Min.Y, Minimum);
    Bounds.Max.X = FMath::Min(Bounds.Max.X, Maximum);
    Bounds.Max.Y = FMath::Min(Bounds.Max.Y, Maximum);
    return Bounds;
}

bool AAetherMapWideEnvironmentActor::IsInsideWorldBounds(const FIntPoint& Chunk) const
{
    const FBox2D Bounds = GetChunkBounds(Chunk);
    return Bounds.Min.X < Bounds.Max.X && Bounds.Min.Y < Bounds.Max.Y;
}

bool AAetherMapWideEnvironmentActor::IsChunkTerrainReady(const FBox2D& Bounds) const
{
    const FVector2D Size = Bounds.GetSize();
    const FVector2D Inset = Size * 0.22f;
    const FVector2D Probes[] = {
        Bounds.GetCenter(),
        Bounds.Min + Inset,
        FVector2D(Bounds.Max.X - Inset.X, Bounds.Min.Y + Inset.Y),
        Bounds.Max - Inset,
        FVector2D(Bounds.Min.X + Inset.X, Bounds.Max.Y - Inset.Y)
    };

    int32 Successful = 0;
    for (const FVector2D& Probe : Probes)
    {
        FVector Location;
        FVector Normal;
        Successful += SampleTerrain(Probe.X, Probe.Y, Location, Normal) ? 1 : 0;
    }
    return Successful >= 2;
}

bool AAetherMapWideEnvironmentActor::ReserveCell(
    TSet<uint64>& Cells,
    const float X,
    const float Y,
    const float CellSize) const
{
    const int32 CellX = FMath::FloorToInt(X / CellSize);
    const int32 CellY = FMath::FloorToInt(Y / CellSize);
    const uint64 Key = (static_cast<uint64>(static_cast<uint32>(CellX)) << 32u)
        | static_cast<uint32>(CellY);
    if (Cells.Contains(Key))
    {
        return false;
    }
    Cells.Add(Key);
    return true;
}

float AAetherMapWideEnvironmentActor::ScaleForDesiredHeight(
    const UStaticMesh* Mesh,
    const float DesiredHeightCm) const
{
    if (!Mesh)
    {
        return 1.0f;
    }
    const float MeshHeight = FMath::Max(50.0f, Mesh->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / MeshHeight, 0.18f, 4.0f);
}

UHierarchicalInstancedStaticMeshComponent* AAetherMapWideEnvironmentActor::CreateChunkComponent(
    const FIntPoint& Chunk,
    const TCHAR* Label,
    UStaticMesh* Mesh,
    const int32 EndCullDistanceCm)
{
    if (!Mesh)
    {
        return nullptr;
    }

    const FName ComponentName(*FString::Printf(
        TEXT("Env_%d_%d_%s"),
        Chunk.X,
        Chunk.Y,
        Label));
    UHierarchicalInstancedStaticMeshComponent* Component =
        NewObject<UHierarchicalInstancedStaticMeshComponent>(this, ComponentName);
    Component->SetupAttachment(Root);
    AddInstanceComponent(Component);
    Component->RegisterComponent();
    Component->SetStaticMesh(Mesh);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetGenerateOverlapEvents(false);
    Component->SetCanEverAffectNavigation(false);
    Component->SetCullDistances(0, EndCullDistanceCm);
    Component->SetMobility(EComponentMobility::Movable);
    Component->bEnableDensityScaling = true;

    // Keep the map-wide rollout renderer-safe. The environment stays visually
    // dense through instancing and culling while avoiding thousands of dynamic
    // shadow and distance-field updates during Mesh Terrain streaming.
    Component->SetCastShadow(false);
    Component->bCastDynamicShadow = false;
    Component->bAffectDistanceFieldLighting = false;
    Component->bAffectDynamicIndirectLighting = false;
    return Component;
}

bool AAetherMapWideEnvironmentActor::BuildChunk(const FIntPoint& Chunk)
{
    if (ActiveChunks.Contains(Chunk) || !IsInsideWorldBounds(Chunk))
    {
        return false;
    }

    const FBox2D Bounds = GetChunkBounds(Chunk);
    if (!IsChunkTerrainReady(Bounds))
    {
        return false;
    }

    FRuntimeChunk RuntimeChunk;
    TArray<UHierarchicalInstancedStaticMeshComponent*> TreeComponents;
    TArray<UHierarchicalInstancedStaticMeshComponent*> RockComponents;

    for (int32 Index = 0; Index < TreeMeshes.Num(); ++Index)
    {
        UHierarchicalInstancedStaticMeshComponent* Component = CreateChunkComponent(
            Chunk,
            *FString::Printf(TEXT("Tree%d"), Index + 1),
            TreeMeshes[Index].Get(),
            900000);
        if (Component)
        {
            TreeComponents.Add(Component);
            RuntimeChunk.Components.Add(Component);
        }
    }

    UHierarchicalInstancedStaticMeshComponent* ShrubComponent = CreateChunkComponent(
        Chunk,
        TEXT("Shrub"),
        ShrubMesh.Get(),
        250000);
    if (ShrubComponent)
    {
        RuntimeChunk.Components.Add(ShrubComponent);
    }

    for (int32 Index = 0; Index < RockMeshes.Num(); ++Index)
    {
        UHierarchicalInstancedStaticMeshComponent* Component = CreateChunkComponent(
            Chunk,
            *FString::Printf(TEXT("Rock%d"), Index + 1),
            RockMeshes[Index].Get(),
            700000);
        if (Component)
        {
            RockComponents.Add(Component);
            RuntimeChunk.Components.Add(Component);
        }
    }

    const uint32 ChunkHash = static_cast<uint32>(Chunk.X) * 73856093u
        ^ static_cast<uint32>(Chunk.Y) * 19349663u
        ^ static_cast<uint32>(EnvironmentSeed) * 83492791u;
    FRandomStream Random(static_cast<int32>(ChunkHash));
    TSet<uint64> TreeCells;
    TSet<uint64> ShrubCells;
    TSet<uint64> RockCells;

    auto RandomPoint = [&]()
    {
        return FVector2D(
            Random.FRandRange(Bounds.Min.X, Bounds.Max.X),
            Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y));
    };

    if (TreeComponents.Num() > 0 && TreesPerChunk > 0)
    {
        const int32 MaximumAttempts = TreesPerChunk * 11;
        for (int32 Attempt = 0;
             Attempt < MaximumAttempts && RuntimeChunk.TreeCount < TreesPerChunk;
             ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }

            const float HeightMeters = Location.Z * 0.01f;
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            const float ForestField = FMath::Clamp(AetherMapEnvironment::SpatialField(
                Point.X,
                Point.Y,
                0.0000041f,
                EnvironmentSeed * 0.00031f), 0.0f, 1.0f);
            const float Density = FMath::Clamp(0.18f + ForestField * 0.63f, 0.18f, 0.80f);
            if (HeightMeters < 8.0f || HeightMeters > 2250.0f || Slope > 0.27f
                || Random.FRand() > Density
                || !ReserveCell(TreeCells, Point.X, Point.Y, 3300.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Component =
                TreeComponents[Random.RandRange(0, TreeComponents.Num() - 1)];
            UStaticMesh* Mesh = Component->GetStaticMesh();
            const float Scale = ScaleForDesiredHeight(Mesh, Random.FRandRange(1250.0f, 2550.0f));
            Component->AddInstance(FTransform(
                FRotator(
                    Random.FRandRange(-1.0f, 1.0f),
                    Random.FRandRange(-180.0f, 180.0f),
                    Random.FRandRange(-1.0f, 1.0f)),
                Location - FVector(0.0f, 0.0f, Random.FRandRange(2.0f, 9.0f)),
                FVector(
                    Scale * Random.FRandRange(0.86f, 1.12f),
                    Scale * Random.FRandRange(0.86f, 1.12f),
                    Scale * Random.FRandRange(0.92f, 1.24f))),
                true);
            ++RuntimeChunk.TreeCount;
        }
    }

    if (ShrubComponent && ShrubsPerChunk > 0)
    {
        const int32 MaximumAttempts = ShrubsPerChunk * 12;
        for (int32 Attempt = 0;
             Attempt < MaximumAttempts && RuntimeChunk.ShrubCount < ShrubsPerChunk;
             ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }

            const float HeightMeters = Location.Z * 0.01f;
            if (HeightMeters < 5.0f || HeightMeters > 2200.0f || Normal.Z < 0.84f
                || Random.FRand() > 0.58f
                || !ReserveCell(ShrubCells, Point.X, Point.Y, 2500.0f))
            {
                continue;
            }

            const float Scale = ScaleForDesiredHeight(
                ShrubMesh.Get(),
                Random.FRandRange(80.0f, 230.0f));
            ShrubComponent->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                Location - FVector(0.0f, 0.0f, 2.0f),
                FVector(Scale)),
                true);
            ++RuntimeChunk.ShrubCount;
        }
    }

    if (RockComponents.Num() > 0 && RocksPerChunk > 0)
    {
        const int32 MaximumAttempts = RocksPerChunk * 22;
        for (int32 Attempt = 0;
             Attempt < MaximumAttempts && RuntimeChunk.RockCount < RocksPerChunk;
             ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }

            const float HeightMeters = Location.Z * 0.01f;
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            const float OutcropField = FMath::Clamp(AetherMapEnvironment::SpatialField(
                Point.X,
                Point.Y,
                0.0000068f,
                EnvironmentSeed * 0.00047f), 0.0f, 1.0f);
            const float Acceptance = FMath::Clamp(
                0.08f + Slope * 1.75f + OutcropField * 0.22f,
                0.10f,
                0.76f);
            if (HeightMeters < 5.0f || HeightMeters > 2900.0f || Normal.Z < 0.45f
                || Random.FRand() > Acceptance
                || !ReserveCell(RockCells, Point.X, Point.Y, 6200.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Component =
                RockComponents[Random.RandRange(0, RockComponents.Num() - 1)];
            UStaticMesh* Mesh = Component->GetStaticMesh();
            const float DesiredHeight = Random.FRand() < 0.92f
                ? Random.FRandRange(100.0f, 520.0f)
                : Random.FRandRange(520.0f, 1100.0f);
            const float Scale = ScaleForDesiredHeight(Mesh, DesiredHeight);
            FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
            Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
            Component->AddInstance(FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(8.0f, 60.0f)),
                FVector(
                    Scale * Random.FRandRange(0.78f, 1.28f),
                    Scale * Random.FRandRange(0.78f, 1.24f),
                    Scale * Random.FRandRange(0.70f, 1.14f))),
                true);
            ++RuntimeChunk.RockCount;
        }
    }

    ActiveChunks.Add(Chunk, MoveTemp(RuntimeChunk));
    const FRuntimeChunk& AddedChunk = ActiveChunks.FindChecked(Chunk);
    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] Chunk (%d,%d) ready: %d trees, %d shrubs, %d rocks. Active chunks=%d."),
        Chunk.X,
        Chunk.Y,
        AddedChunk.TreeCount,
        AddedChunk.ShrubCount,
        AddedChunk.RockCount,
        ActiveChunks.Num());
    return true;
}

void AAetherMapWideEnvironmentActor::RemoveChunk(const FIntPoint& Chunk)
{
    FRuntimeChunk* RuntimeChunk = ActiveChunks.Find(Chunk);
    if (!RuntimeChunk)
    {
        return;
    }

    for (UHierarchicalInstancedStaticMeshComponent* Component : RuntimeChunk->Components)
    {
        if (IsValid(Component))
        {
            Component->ClearInstances();
            Component->DestroyComponent();
        }
    }
    ActiveChunks.Remove(Chunk);
}

void AAetherMapWideEnvironmentActor::RemoveAllChunks()
{
    TArray<FIntPoint> Chunks;
    ActiveChunks.GetKeys(Chunks);
    for (const FIntPoint& Chunk : Chunks)
    {
        RemoveChunk(Chunk);
    }
}

FVector AAetherMapWideEnvironmentActor::GetFocusLocation() const
{
    if (const APlayerController* Controller = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr)
    {
        if (const APawn* Pawn = Controller->GetPawn())
        {
            return Pawn->GetActorLocation();
        }
    }
    return GetActorLocation();
}

void AAetherMapWideEnvironmentActor::PrepareEnvironment()
{
    ++PrepareAttempts;
    if (!bAssetsReady)
    {
        if (!LoadEnvironmentAssets())
        {
            UE_LOG(LogTemp, Warning,
                TEXT("[Aether Map Environment] No safe individual environment meshes were found; map-wide placement is disabled."));
            return;
        }
        bAssetsReady = true;
    }

    const FVector Focus = GetFocusLocation();
    const float SafeChunkSize = FMath::Max(80000.0f, ChunkSizeCm);
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / SafeChunkSize),
        FMath::FloorToInt(Focus.Y / SafeChunkSize));
    if (!IsInsideWorldBounds(FocusChunk) || !IsChunkTerrainReady(GetChunkBounds(FocusChunk)))
    {
        if (PrepareAttempts < AetherMapEnvironment::MaxPrepareAttempts)
        {
            UE_LOG(LogTemp, Display,
                TEXT("[Aether Map Environment] Mesh Terrain collision is still streaming near the aircraft; retrying (%d/%d)."),
                PrepareAttempts,
                AetherMapEnvironment::MaxPrepareAttempts);
            GetWorldTimerManager().SetTimer(
                PrepareTimer,
                this,
                &AAetherMapWideEnvironmentActor::PrepareEnvironment,
                1.5f,
                false);
        }
        else
        {
            UE_LOG(LogTemp, Warning,
                TEXT("[Aether Map Environment] Mesh Terrain collision never became ready near the aircraft; no environment chunks were generated."));
        }
        return;
    }

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] MAP-WIDE STREAMING READY: %.1f km chunks, radius=%d, max %d new chunk(s) per %.2f seconds."),
        SafeChunkSize * 0.00001f,
        ActiveRadiusInChunks,
        MaxNewChunksPerUpdate,
        StreamingUpdateSeconds);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            12.0f,
            FColor(110, 255, 150),
            TEXT("AETHER // MAP-WIDE FORESTS AND ROCKS STREAMING"));
    }

    UpdateStreaming();
    GetWorldTimerManager().SetTimer(
        StreamingTimer,
        this,
        &AAetherMapWideEnvironmentActor::UpdateStreaming,
        FMath::Max(0.25f, StreamingUpdateSeconds),
        true);
}

void AAetherMapWideEnvironmentActor::UpdateStreaming()
{
    if (!bAssetsReady || !GetWorld())
    {
        return;
    }

    const FVector Focus = GetFocusLocation();
    const float SafeChunkSize = FMath::Max(80000.0f, ChunkSizeCm);
    const FIntPoint CenterChunk(
        FMath::FloorToInt(Focus.X / SafeChunkSize),
        FMath::FloorToInt(Focus.Y / SafeChunkSize));
    const int32 Radius = FMath::Clamp(ActiveRadiusInChunks, 1, 4);

    TSet<FIntPoint> DesiredChunks;
    TArray<FIntPoint> PendingChunks;
    for (int32 OffsetY = -Radius; OffsetY <= Radius; ++OffsetY)
    {
        for (int32 OffsetX = -Radius; OffsetX <= Radius; ++OffsetX)
        {
            if (OffsetX * OffsetX + OffsetY * OffsetY > Radius * Radius)
            {
                continue;
            }

            const FIntPoint Chunk(CenterChunk.X + OffsetX, CenterChunk.Y + OffsetY);
            if (!IsInsideWorldBounds(Chunk))
            {
                continue;
            }
            DesiredChunks.Add(Chunk);
            if (!ActiveChunks.Contains(Chunk))
            {
                PendingChunks.Add(Chunk);
            }
        }
    }

    TArray<FIntPoint> RemoveList;
    for (const TPair<FIntPoint, FRuntimeChunk>& Pair : ActiveChunks)
    {
        if (!DesiredChunks.Contains(Pair.Key))
        {
            RemoveList.Add(Pair.Key);
        }
    }
    for (const FIntPoint& Chunk : RemoveList)
    {
        RemoveChunk(Chunk);
    }

    PendingChunks.Sort([CenterChunk](const FIntPoint& Left, const FIntPoint& Right)
    {
        const int32 LeftX = Left.X - CenterChunk.X;
        const int32 LeftY = Left.Y - CenterChunk.Y;
        const int32 RightX = Right.X - CenterChunk.X;
        const int32 RightY = Right.Y - CenterChunk.Y;
        return LeftX * LeftX + LeftY * LeftY < RightX * RightX + RightY * RightY;
    });

    int32 Added = 0;
    const int32 MaximumNewChunks = FMath::Clamp(MaxNewChunksPerUpdate, 1, 3);
    for (const FIntPoint& Chunk : PendingChunks)
    {
        if (BuildChunk(Chunk) && ++Added >= MaximumNewChunks)
        {
            break;
        }
    }
}
