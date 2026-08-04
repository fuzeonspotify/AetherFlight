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
    constexpr int32 MaxPrepareAttempts = 14;

    float SpatialField(const float X, const float Y, const float Frequency, const float Phase)
    {
        return FMath::Clamp(
            0.5f + 0.25f * FMath::Sin(X * Frequency + Phase)
                + 0.25f * FMath::Cos(Y * Frequency * 1.17f - Phase * 0.73f),
            0.0f,
            1.0f);
    }
}

AAetherMapWideEnvironmentActor::AAetherMapWideEnvironmentActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    TreePrimary = CreatePersistentScatterComponent(TEXT("MapTreePrimary"), 1200000);
    TreeSecondary = CreatePersistentScatterComponent(TEXT("MapTreeSecondary"), 1100000);
    Shrubs = CreatePersistentScatterComponent(TEXT("MapShrubs"), 300000);
    RockPrimary = CreatePersistentScatterComponent(TEXT("MapRockPrimary"), 850000);
    RockSecondary = CreatePersistentScatterComponent(TEXT("MapRockSecondary"), 800000);
}

UHierarchicalInstancedStaticMeshComponent* AAetherMapWideEnvironmentActor::CreatePersistentScatterComponent(
    const FName Name,
    const int32 EndCullDistanceCm)
{
    UHierarchicalInstancedStaticMeshComponent* Component =
        CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(Name);
    Component->SetupAttachment(Root);
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetGenerateOverlapEvents(false);
    Component->SetCanEverAffectNavigation(false);
    Component->SetCullDistances(0, EndCullDistanceCm);
    Component->bEnableDensityScaling = false;
    Component->SetCastShadow(false);
    Component->bCastDynamicShadow = false;
    Component->bAffectDistanceFieldLighting = false;
    Component->bAffectDynamicIndirectLighting = false;
    return Component;
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
        4.0f,
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
        if (!bKeywordMatch || ++LoadedAssets > 64)
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
        if (!bKeywordMatch || ++LoadedAssets > 48)
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
    const TArray<UStaticMesh*> Trees = LoadSuitableMeshes({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Windmill_Palm")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Coconut_Tree"))
    }, {
        TEXT("tree"), TEXT("pine"), TEXT("aspen"), TEXT("oak"),
        TEXT("conifer"), TEXT("palm"), TEXT("coconut")
    }, 2, 2300.0f, 450.0f, 12000.0f, 2.7f);

    const TArray<UStaticMesh*> Rocks = LoadSuitableMeshes({
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
    }, 2, 450.0f, 40.0f, 8000.0f, 5.0f);

    UStaticMesh* ShrubMesh = LoadFirstKeywordMesh({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets"))
    }, {
        TEXT("shrub"), TEXT("bush"), TEXT("sapling"), TEXT("fern")
    }, 20.0f, 1400.0f);

    TreePrimary->SetStaticMesh(Trees.Num() > 0 ? Trees[0] : nullptr);
    TreeSecondary->SetStaticMesh(Trees.Num() > 1 ? Trees[1] : (Trees.Num() > 0 ? Trees[0] : nullptr));
    Shrubs->SetStaticMesh(ShrubMesh);
    RockPrimary->SetStaticMesh(Rocks.Num() > 0 ? Rocks[0] : nullptr);
    RockSecondary->SetStaticMesh(Rocks.Num() > 1 ? Rocks[1] : (Rocks.Num() > 0 ? Rocks[0] : nullptr));

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] Selected persistent meshes: treeA=%s treeB=%s shrub=%s rockA=%s rockB=%s."),
        TreePrimary->GetStaticMesh() ? *TreePrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
        TreeSecondary->GetStaticMesh() ? *TreeSecondary->GetStaticMesh()->GetPathName() : TEXT("None"),
        Shrubs->GetStaticMesh() ? *Shrubs->GetStaticMesh()->GetPathName() : TEXT("None"),
        RockPrimary->GetStaticMesh() ? *RockPrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
        RockSecondary->GetStaticMesh() ? *RockSecondary->GetStaticMesh()->GetPathName() : TEXT("None"));

    return TreePrimary->GetStaticMesh() || Shrubs->GetStaticMesh() || RockPrimary->GetStaticMesh();
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
    const float SafeChunkSize = FMath::Max(100000.0f, ChunkSizeCm);
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
    const FVector2D Inset = Size * 0.24f;
    const FVector2D Probes[] = {
        Bounds.GetCenter(),
        Bounds.Min + Inset,
        Bounds.Max - Inset
    };

    int32 Successful = 0;
    for (const FVector2D& Probe : Probes)
    {
        FVector Location;
        FVector Normal;
        Successful += SampleTerrain(Probe.X, Probe.Y, Location, Normal) ? 1 : 0;
    }
    return Successful >= 1;
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

void AAetherMapWideEnvironmentActor::ClearLocalRing()
{
    TreePrimary->ClearInstances();
    TreeSecondary->ClearInstances();
    Shrubs->ClearInstances();
    RockPrimary->ClearInstances();
    RockSecondary->ClearInstances();
    PendingChunks.Reset();
    GeneratedChunks.Reset();
    TotalTrees = 0;
    TotalShrubs = 0;
    TotalRocks = 0;
}

void AAetherMapWideEnvironmentActor::StartLocalRing(const FIntPoint& CenterChunk)
{
    ClearLocalRing();
    CurrentCenterChunk = CenterChunk;
    bHasCenterChunk = true;

    const int32 Radius = FMath::Clamp(ActiveRadiusInChunks, 1, 3);
    for (int32 OffsetY = -Radius; OffsetY <= Radius; ++OffsetY)
    {
        for (int32 OffsetX = -Radius; OffsetX <= Radius; ++OffsetX)
        {
            if (OffsetX * OffsetX + OffsetY * OffsetY > Radius * Radius)
            {
                continue;
            }
            const FIntPoint Chunk(CenterChunk.X + OffsetX, CenterChunk.Y + OffsetY);
            if (IsInsideWorldBounds(Chunk))
            {
                PendingChunks.Add(Chunk);
            }
        }
    }

    PendingChunks.Sort([CenterChunk](const FIntPoint& Left, const FIntPoint& Right)
    {
        const int32 LeftX = Left.X - CenterChunk.X;
        const int32 LeftY = Left.Y - CenterChunk.Y;
        const int32 RightX = Right.X - CenterChunk.X;
        const int32 RightY = Right.Y - CenterChunk.Y;
        return LeftX * LeftX + LeftY * LeftY < RightX * RightX + RightY * RightY;
    });

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] Starting persistent local ring around chunk (%d,%d): %d chunks queued."),
        CenterChunk.X,
        CenterChunk.Y,
        PendingChunks.Num());
}

bool AAetherMapWideEnvironmentActor::BuildChunk(const FIntPoint& Chunk)
{
    if (GeneratedChunks.Contains(Chunk) || !IsInsideWorldBounds(Chunk))
    {
        return true;
    }

    const FBox2D Bounds = GetChunkBounds(Chunk);
    if (!IsChunkTerrainReady(Bounds))
    {
        return false;
    }

    const uint32 ChunkHash = static_cast<uint32>(Chunk.X) * 73856093u
        ^ static_cast<uint32>(Chunk.Y) * 19349663u
        ^ static_cast<uint32>(EnvironmentSeed) * 83492791u;
    FRandomStream Random(static_cast<int32>(ChunkHash));
    TSet<uint64> TreeCells;
    TSet<uint64> ShrubCells;
    TSet<uint64> RockCells;
    int32 ChunkTrees = 0;
    int32 ChunkShrubs = 0;
    int32 ChunkRocks = 0;

    auto RandomPoint = [&]()
    {
        return FVector2D(
            Random.FRandRange(Bounds.Min.X, Bounds.Max.X),
            Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y));
    };

    if (TreePrimary->GetStaticMesh() && TreesPerChunk > 0)
    {
        const int32 MaximumAttempts = TreesPerChunk * 12;
        for (int32 Attempt = 0; Attempt < MaximumAttempts && ChunkTrees < TreesPerChunk; ++Attempt)
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
            const float ForestField = AetherMapEnvironment::SpatialField(
                Point.X,
                Point.Y,
                0.0000041f,
                EnvironmentSeed * 0.00031f);
            const float Density = FMath::Clamp(0.42f + ForestField * 0.46f, 0.42f, 0.88f);
            if (HeightMeters < 5.0f || HeightMeters > 3500.0f || Slope > 0.38f
                || Random.FRand() > Density
                || !ReserveCell(TreeCells, Point.X, Point.Y, 3400.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Target =
                TreeSecondary->GetStaticMesh() && Random.FRand() > 0.58f
                    ? TreeSecondary
                    : TreePrimary;
            UStaticMesh* Mesh = Target->GetStaticMesh();
            const float Scale = ScaleForDesiredHeight(Mesh, Random.FRandRange(1500.0f, 3000.0f));
            Target->AddInstance(FTransform(
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
            ++ChunkTrees;
        }
    }

    if (Shrubs->GetStaticMesh() && ShrubsPerChunk > 0)
    {
        const int32 MaximumAttempts = ShrubsPerChunk * 14;
        for (int32 Attempt = 0; Attempt < MaximumAttempts && ChunkShrubs < ShrubsPerChunk; ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }

            const float HeightMeters = Location.Z * 0.01f;
            if (HeightMeters < 3.0f || HeightMeters > 3300.0f || Normal.Z < 0.80f
                || Random.FRand() > 0.68f
                || !ReserveCell(ShrubCells, Point.X, Point.Y, 2600.0f))
            {
                continue;
            }

            const float Scale = ScaleForDesiredHeight(
                Shrubs->GetStaticMesh(),
                Random.FRandRange(90.0f, 260.0f));
            Shrubs->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                Location - FVector(0.0f, 0.0f, 2.0f),
                FVector(Scale)),
                true);
            ++ChunkShrubs;
        }
    }

    if (RockPrimary->GetStaticMesh() && RocksPerChunk > 0)
    {
        const int32 MaximumAttempts = RocksPerChunk * 24;
        for (int32 Attempt = 0; Attempt < MaximumAttempts && ChunkRocks < RocksPerChunk; ++Attempt)
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
            const float OutcropField = AetherMapEnvironment::SpatialField(
                Point.X,
                Point.Y,
                0.0000068f,
                EnvironmentSeed * 0.00047f);
            const float Acceptance = FMath::Clamp(
                0.18f + Slope * 1.55f + OutcropField * 0.25f,
                0.18f,
                0.82f);
            if (HeightMeters < 3.0f || HeightMeters > 3900.0f || Normal.Z < 0.38f
                || Random.FRand() > Acceptance
                || !ReserveCell(RockCells, Point.X, Point.Y, 6200.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Target =
                RockSecondary->GetStaticMesh() && Random.FRand() > 0.62f
                    ? RockSecondary
                    : RockPrimary;
            UStaticMesh* Mesh = Target->GetStaticMesh();
            const float DesiredHeight = Random.FRand() < 0.90f
                ? Random.FRandRange(120.0f, 620.0f)
                : Random.FRandRange(620.0f, 1400.0f);
            const float Scale = ScaleForDesiredHeight(Mesh, DesiredHeight);
            FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
            Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
            Target->AddInstance(FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(8.0f, 70.0f)),
                FVector(
                    Scale * Random.FRandRange(0.78f, 1.28f),
                    Scale * Random.FRandRange(0.78f, 1.24f),
                    Scale * Random.FRandRange(0.70f, 1.14f))),
                true);
            ++ChunkRocks;
        }
    }

    GeneratedChunks.Add(Chunk);
    TotalTrees += ChunkTrees;
    TotalShrubs += ChunkShrubs;
    TotalRocks += ChunkRocks;

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] Persistent chunk (%d,%d): %d trees, %d shrubs, %d rocks. Ring totals=%d/%d/%d."),
        Chunk.X,
        Chunk.Y,
        ChunkTrees,
        ChunkShrubs,
        ChunkRocks,
        TotalTrees,
        TotalShrubs,
        TotalRocks);

    if (GEngine && GeneratedChunks.Num() == 1)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            15.0f,
            FColor(110, 255, 150),
            FString::Printf(
                TEXT("AETHER ENVIRONMENT VISIBLE // %d TREES // %d ROCKS"),
                TotalTrees,
                TotalRocks));
    }
    return true;
}

void AAetherMapWideEnvironmentActor::PrepareEnvironment()
{
    ++PrepareAttempts;
    if (!bAssetsReady)
    {
        if (!LoadEnvironmentAssets())
        {
            UE_LOG(LogTemp, Warning,
                TEXT("[Aether Map Environment] No safe individual tree, shrub, or rock meshes were found; map-wide placement stopped."));
            return;
        }
        bAssetsReady = true;
    }

    const FVector Focus = GetFocusLocation();
    const float SafeChunkSize = FMath::Max(100000.0f, ChunkSizeCm);
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / SafeChunkSize),
        FMath::FloorToInt(Focus.Y / SafeChunkSize));
    if (!IsInsideWorldBounds(FocusChunk) || !IsChunkTerrainReady(GetChunkBounds(FocusChunk)))
    {
        if (PrepareAttempts < AetherMapEnvironment::MaxPrepareAttempts)
        {
            UE_LOG(LogTemp, Display,
                TEXT("[Aether Map Environment] Mesh Terrain collision still streaming near aircraft; retrying (%d/%d)."),
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
                TEXT("[Aether Map Environment] Mesh Terrain collision never became ready near aircraft; no instances generated."));
        }
        return;
    }

    StartLocalRing(FocusChunk);
    UpdateStreaming();
    GetWorldTimerManager().SetTimer(
        StreamingTimer,
        this,
        &AAetherMapWideEnvironmentActor::UpdateStreaming,
        FMath::Max(0.5f, StreamingUpdateSeconds),
        true);

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Map Environment] PERSISTENT MAP-WIDE STREAMING READY: %.1f km chunks, radius=%d."),
        SafeChunkSize * 0.00001f,
        ActiveRadiusInChunks);
}

void AAetherMapWideEnvironmentActor::UpdateStreaming()
{
    if (!bAssetsReady || !GetWorld())
    {
        return;
    }

    const FVector Focus = GetFocusLocation();
    const float SafeChunkSize = FMath::Max(100000.0f, ChunkSizeCm);
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / SafeChunkSize),
        FMath::FloorToInt(Focus.Y / SafeChunkSize));

    if (!bHasCenterChunk || FocusChunk != CurrentCenterChunk)
    {
        StartLocalRing(FocusChunk);
    }

    // Build at most one ready chunk per update. Unready chunks are moved to the
    // back of the queue so Mesh Terrain can finish streaming without a busy loop.
    const int32 ChecksThisUpdate = FMath::Min(PendingChunks.Num(), 3);
    for (int32 Check = 0; Check < ChecksThisUpdate && PendingChunks.Num() > 0; ++Check)
    {
        const FIntPoint Chunk = PendingChunks[0];
        PendingChunks.RemoveAt(0);
        if (BuildChunk(Chunk))
        {
            break;
        }
        PendingChunks.Add(Chunk);
    }
}
