#include "AetherVerifiedEnvironmentActor.h"

#include "AetherBiomeScatterActor.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"

namespace AetherVerifiedEnvironment
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr float HalfWorldCm = 2400000.0f;
    constexpr float WorldInsetCm = 12000.0f;
    constexpr int32 MaximumPrepareAttempts = 18;

    float ForestField(const float X, const float Y, const int32 Seed)
    {
        return FMath::Clamp(
            0.5f
                + 0.26f * FMath::Sin(X * 0.0000042f + Seed * 0.00031f)
                + 0.24f * FMath::Cos(Y * 0.0000049f - Seed * 0.00019f),
            0.0f,
            1.0f);
    }
}

AAetherVerifiedEnvironmentActor::AAetherVerifiedEnvironmentActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    TreePrimary = CreateScatterComponent(TEXT("VerifiedTreePrimary"), 1400000);
    TreeSecondary = CreateScatterComponent(TEXT("VerifiedTreeSecondary"), 1300000);
    Rocks = CreateScatterComponent(TEXT("VerifiedRocks"), 950000);
}

UHierarchicalInstancedStaticMeshComponent* AAetherVerifiedEnvironmentActor::CreateScatterComponent(
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

void AAetherVerifiedEnvironmentActor::BeginPlay()
{
    Super::BeginPlay();
    if (!GetWorld())
    {
        return;
    }

    // Disable the older generated scatter actor before it can compete for traces
    // or renderer resources during the verified rollout.
    for (TActorIterator<AAetherBiomeScatterActor> It(GetWorld()); It; ++It)
    {
        It->ClearEnvironment();
        It->SetActorHiddenInGame(true);
    }

    GetWorldTimerManager().SetTimer(
        PrepareTimer,
        this,
        &AAetherVerifiedEnvironmentActor::PrepareEnvironment,
        5.0f,
        false);
}

bool AAetherVerifiedEnvironmentActor::LoadVerifiedMeshes()
{
    UStaticMesh* TreeA = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_03.PCG_Tree_03"));
    UStaticMesh* TreeB = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_01.PCG_Tree_01"));
    if (!TreeB)
    {
        TreeB = LoadObject<UStaticMesh>(
            nullptr,
            TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_02.PCG_Tree_02"));
    }

    UStaticMesh* Boulder = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Boulder_02.PCG_Boulder_02"));

    TreePrimary->SetStaticMesh(TreeA);
    TreeSecondary->SetStaticMesh(TreeB ? TreeB : TreeA);
    Rocks->SetStaticMesh(Boulder);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Verified Environment] Exact audited meshes: treeA=%s treeB=%s rock=%s."),
        TreePrimary->GetStaticMesh() ? *TreePrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
        TreeSecondary->GetStaticMesh() ? *TreeSecondary->GetStaticMesh()->GetPathName() : TEXT("None"),
        Rocks->GetStaticMesh() ? *Rocks->GetStaticMesh()->GetPathName() : TEXT("None"));

    return TreePrimary->GetStaticMesh() != nullptr && Rocks->GetStaticMesh() != nullptr;
}

bool AAetherVerifiedEnvironmentActor::LooksLikeWater(const FHitResult& Hit) const
{
    FString Name;
    if (const AActor* Actor = Hit.GetActor())
    {
        Name += Actor->GetName();
        Name += Actor->GetClass()->GetName();
    }
    if (const UPrimitiveComponent* Component = Hit.GetComponent())
    {
        Name += Component->GetName();
        Name += Component->GetClass()->GetName();
    }
    return Name.Contains(TEXT("Water"), ESearchCase::IgnoreCase)
        || Name.Contains(TEXT("Ocean"), ESearchCase::IgnoreCase)
        || Name.Contains(TEXT("Lake"), ESearchCase::IgnoreCase);
}

bool AAetherVerifiedEnvironmentActor::TraceTerrain(
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
    FCollisionQueryParams Parameters(SCENE_QUERY_STAT(AetherVerifiedEnvironmentTrace), false, this);
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Parameters.AddIgnoredActor(Controller->GetPawn());
    }

    if (!GetWorld()->LineTraceSingleByChannel(
            Hit,
            FVector(X, Y, AetherVerifiedEnvironment::TraceTopCm),
            FVector(X, Y, AetherVerifiedEnvironment::TraceBottomCm),
            ECC_Visibility,
            Parameters)
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

    const FString Name = HitActor->GetName()
        + HitActor->GetClass()->GetName()
        + HitComponent->GetName()
        + HitComponent->GetClass()->GetName();
    const bool bProductionTerrain = HitActor->ActorHasTag(TEXT("AetherProductionTerrain"))
        || Name.Contains(TEXT("MeshTerrain"), ESearchCase::IgnoreCase)
        || Name.Contains(TEXT("MeshPartition"), ESearchCase::IgnoreCase)
        || Name.Contains(TEXT("CompiledSection"), ESearchCase::IgnoreCase);
    if (!bProductionTerrain)
    {
        return false;
    }

    OutLocation = Hit.ImpactPoint;
    OutNormal = Hit.ImpactNormal.GetSafeNormal();
    return OutNormal.Z > 0.05f;
}

FBox2D AAetherVerifiedEnvironmentActor::ChunkBounds(const FIntPoint& Chunk) const
{
    FBox2D Bounds(
        FVector2D(Chunk.X * ChunkSizeCm, Chunk.Y * ChunkSizeCm),
        FVector2D((Chunk.X + 1) * ChunkSizeCm, (Chunk.Y + 1) * ChunkSizeCm));

    const float Minimum = -AetherVerifiedEnvironment::HalfWorldCm
        + AetherVerifiedEnvironment::WorldInsetCm;
    const float Maximum = AetherVerifiedEnvironment::HalfWorldCm
        - AetherVerifiedEnvironment::WorldInsetCm;
    Bounds.Min.X = FMath::Max(Bounds.Min.X, Minimum);
    Bounds.Min.Y = FMath::Max(Bounds.Min.Y, Minimum);
    Bounds.Max.X = FMath::Min(Bounds.Max.X, Maximum);
    Bounds.Max.Y = FMath::Min(Bounds.Max.Y, Maximum);
    return Bounds;
}

bool AAetherVerifiedEnvironmentActor::IsInsideWorld(const FIntPoint& Chunk) const
{
    const FBox2D Bounds = ChunkBounds(Chunk);
    return Bounds.Min.X < Bounds.Max.X && Bounds.Min.Y < Bounds.Max.Y;
}

bool AAetherVerifiedEnvironmentActor::IsTerrainReady(const FBox2D& Bounds) const
{
    const FVector2D Size = Bounds.GetSize();
    const FVector2D Inset = Size * 0.24f;
    const FVector2D Points[] = {
        Bounds.GetCenter(),
        Bounds.Min + Inset,
        Bounds.Max - Inset,
    };

    for (const FVector2D& Point : Points)
    {
        FVector Location;
        FVector Normal;
        if (TraceTerrain(Point.X, Point.Y, Location, Normal))
        {
            return true;
        }
    }
    return false;
}

FVector AAetherVerifiedEnvironmentActor::FocusLocation() const
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

float AAetherVerifiedEnvironmentActor::ScaleForHeight(
    const UStaticMesh* Mesh,
    const float DesiredHeightCm) const
{
    if (!Mesh)
    {
        return 1.0f;
    }
    const float Height = FMath::Max(50.0f, Mesh->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / Height, 0.25f, 5.0f);
}

bool AAetherVerifiedEnvironmentActor::ReserveCell(
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

void AAetherVerifiedEnvironmentActor::ClearInstances()
{
    TreePrimary->ClearInstances();
    TreeSecondary->ClearInstances();
    Rocks->ClearInstances();
    PendingChunks.Reset();
    GeneratedChunks.Reset();
    TotalTrees = 0;
    TotalRocks = 0;
}

void AAetherVerifiedEnvironmentActor::BeginLocalRing(const FIntPoint& CenterChunk)
{
    ClearInstances();
    CurrentCenterChunk = CenterChunk;
    bHasCenterChunk = true;

    for (int32 OffsetY = -ActiveRadiusChunks; OffsetY <= ActiveRadiusChunks; ++OffsetY)
    {
        for (int32 OffsetX = -ActiveRadiusChunks; OffsetX <= ActiveRadiusChunks; ++OffsetX)
        {
            if (OffsetX * OffsetX + OffsetY * OffsetY > ActiveRadiusChunks * ActiveRadiusChunks)
            {
                continue;
            }
            const FIntPoint Chunk(CenterChunk.X + OffsetX, CenterChunk.Y + OffsetY);
            if (IsInsideWorld(Chunk))
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

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Verified Environment] Local map-wide ring centered on chunk (%d,%d); %d chunks queued."),
        CenterChunk.X,
        CenterChunk.Y,
        PendingChunks.Num());
}

bool AAetherVerifiedEnvironmentActor::GenerateChunk(const FIntPoint& Chunk)
{
    if (GeneratedChunks.Contains(Chunk))
    {
        return true;
    }

    const FBox2D Bounds = ChunkBounds(Chunk);
    if (!IsTerrainReady(Bounds))
    {
        return false;
    }

    const uint32 Hash = static_cast<uint32>(Chunk.X) * 73856093u
        ^ static_cast<uint32>(Chunk.Y) * 19349663u
        ^ 260804u * 83492791u;
    FRandomStream Random(static_cast<int32>(Hash));
    TSet<uint64> TreeCells;
    TSet<uint64> RockCells;
    int32 ChunkTrees = 0;
    int32 ChunkRocks = 0;

    auto RandomPoint = [&]()
    {
        return FVector2D(
            Random.FRandRange(Bounds.Min.X, Bounds.Max.X),
            Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y));
    };

    for (int32 Attempt = 0;
         Attempt < TreesPerChunk * 15 && ChunkTrees < TreesPerChunk;
         ++Attempt)
    {
        const FVector2D Point = RandomPoint();
        FVector Location;
        FVector Normal;
        if (!TraceTerrain(Point.X, Point.Y, Location, Normal))
        {
            continue;
        }

        const float HeightMeters = Location.Z * 0.01f;
        const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
        const float Density = FMath::Clamp(
            0.48f + AetherVerifiedEnvironment::ForestField(Point.X, Point.Y, 260804) * 0.45f,
            0.48f,
            0.93f);
        if (HeightMeters < 2.0f || HeightMeters > 3900.0f || Slope > 0.42f
            || Random.FRand() > Density
            || !ReserveCell(TreeCells, Point.X, Point.Y, 3000.0f))
        {
            continue;
        }

        UHierarchicalInstancedStaticMeshComponent* Target =
            TreeSecondary->GetStaticMesh() && Random.FRand() > 0.55f
                ? TreeSecondary
                : TreePrimary;
        UStaticMesh* Mesh = Target->GetStaticMesh();
        const float Scale = ScaleForHeight(Mesh, Random.FRandRange(2200.0f, 4200.0f));
        Target->AddInstance(
            FTransform(
                FRotator(
                    Random.FRandRange(-1.5f, 1.5f),
                    Random.FRandRange(-180.0f, 180.0f),
                    Random.FRandRange(-1.5f, 1.5f)),
                Location - FVector(0.0f, 0.0f, Random.FRandRange(1.0f, 7.0f)),
                FVector(
                    Scale * Random.FRandRange(0.86f, 1.14f),
                    Scale * Random.FRandRange(0.86f, 1.14f),
                    Scale * Random.FRandRange(0.92f, 1.24f))),
            true);
        ++ChunkTrees;
    }

    for (int32 Attempt = 0;
         Attempt < RocksPerChunk * 26 && ChunkRocks < RocksPerChunk;
         ++Attempt)
    {
        const FVector2D Point = RandomPoint();
        FVector Location;
        FVector Normal;
        if (!TraceTerrain(Point.X, Point.Y, Location, Normal))
        {
            continue;
        }

        const float HeightMeters = Location.Z * 0.01f;
        const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
        const float Acceptance = FMath::Clamp(0.20f + Slope * 1.7f, 0.20f, 0.88f);
        if (HeightMeters < 2.0f || HeightMeters > 4300.0f || Normal.Z < 0.34f
            || Random.FRand() > Acceptance
            || !ReserveCell(RockCells, Point.X, Point.Y, 5200.0f))
        {
            continue;
        }

        const float DesiredHeight = Random.FRand() < 0.88f
            ? Random.FRandRange(250.0f, 900.0f)
            : Random.FRandRange(900.0f, 1800.0f);
        const float Scale = ScaleForHeight(Rocks->GetStaticMesh(), DesiredHeight);
        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        Rocks->AddInstance(
            FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(5.0f, 45.0f)),
                FVector(
                    Scale * Random.FRandRange(0.80f, 1.35f),
                    Scale * Random.FRandRange(0.80f, 1.30f),
                    Scale * Random.FRandRange(0.75f, 1.18f))),
            true);
        ++ChunkRocks;
    }

    GeneratedChunks.Add(Chunk);
    TotalTrees += ChunkTrees;
    TotalRocks += ChunkRocks;

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Verified Environment] Chunk (%d,%d): %d trees, %d rocks. Ring total=%d trees/%d rocks."),
        Chunk.X,
        Chunk.Y,
        ChunkTrees,
        ChunkRocks,
        TotalTrees,
        TotalRocks);

    if (GEngine && GeneratedChunks.Num() == 1)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            20.0f,
            FColor(100, 255, 140),
            FString::Printf(
                TEXT("AETHER VERIFIED FOLIAGE VISIBLE // %d TREES // %d ROCKS"),
                TotalTrees,
                TotalRocks));
    }

    return true;
}

void AAetherVerifiedEnvironmentActor::PrepareEnvironment()
{
    ++PrepareAttempts;
    if (!bMeshesReady)
    {
        if (!LoadVerifiedMeshes())
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("[Aether Verified Environment] Audited PCG tree/boulder meshes failed to load."));
            if (GEngine)
            {
                GEngine->AddOnScreenDebugMessage(
                    -1,
                    20.0f,
                    FColor::Red,
                    TEXT("AETHER FOLIAGE ERROR // VERIFIED PCG MESHES FAILED TO LOAD"));
            }
            return;
        }
        bMeshesReady = true;
    }

    const FVector Focus = FocusLocation();
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / ChunkSizeCm),
        FMath::FloorToInt(Focus.Y / ChunkSizeCm));

    if (!IsInsideWorld(FocusChunk) || !IsTerrainReady(ChunkBounds(FocusChunk)))
    {
        if (PrepareAttempts < AetherVerifiedEnvironment::MaximumPrepareAttempts)
        {
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[Aether Verified Environment] Waiting for Mesh Terrain collision near aircraft (%d/%d)."),
                PrepareAttempts,
                AetherVerifiedEnvironment::MaximumPrepareAttempts);
            GetWorldTimerManager().SetTimer(
                PrepareTimer,
                this,
                &AAetherVerifiedEnvironmentActor::PrepareEnvironment,
                1.5f,
                false);
        }
        else
        {
            UE_LOG(
                LogTemp,
                Warning,
                TEXT("[Aether Verified Environment] Mesh Terrain collision did not become ready; no foliage generated."));
        }
        return;
    }

    BeginLocalRing(FocusChunk);
    UpdateEnvironment();
    GetWorldTimerManager().SetTimer(
        UpdateTimer,
        this,
        &AAetherVerifiedEnvironmentActor::UpdateEnvironment,
        1.0f,
        true);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Verified Environment] VERIFIED MAP-WIDE STREAMING READY."));
}

void AAetherVerifiedEnvironmentActor::UpdateEnvironment()
{
    if (!bMeshesReady || !GetWorld())
    {
        return;
    }

    const FVector Focus = FocusLocation();
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / ChunkSizeCm),
        FMath::FloorToInt(Focus.Y / ChunkSizeCm));

    if (!bHasCenterChunk || FocusChunk != CurrentCenterChunk)
    {
        BeginLocalRing(FocusChunk);
    }

    const int32 Checks = FMath::Min(PendingChunks.Num(), 3);
    for (int32 Check = 0; Check < Checks && PendingChunks.Num() > 0; ++Check)
    {
        const FIntPoint Chunk = PendingChunks[0];
        PendingChunks.RemoveAt(0);
        if (GenerateChunk(Chunk))
        {
            break;
        }
        PendingChunks.Add(Chunk);
    }
}
