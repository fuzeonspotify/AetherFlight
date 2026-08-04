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
#include "UObject/UObjectGlobals.h"

namespace AetherVerifiedEnvironment
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr float HalfWorldCm = 2400000.0f;
    constexpr float WorldInsetCm = 12000.0f;
    constexpr int32 MaximumPrepareAttempts = 18;

    float SpatialField(
        const float X,
        const float Y,
        const float Frequency,
        const float Phase)
    {
        return FMath::Clamp(
            0.5f
                + 0.26f * FMath::Sin(X * Frequency + Phase)
                + 0.24f * FMath::Cos(Y * Frequency * 1.17f - Phase * 0.73f),
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

    PineTrees = CreateScatterComponent(TEXT("CinematicPineTrees"), 1600000);
    AspenTrees = CreateScatterComponent(TEXT("CinematicAspenTrees"), 1500000);
    OakTrees = CreateScatterComponent(TEXT("CinematicOakTrees"), 1450000);
    CoastalTrees = CreateScatterComponent(TEXT("CinematicCoastalTrees"), 1400000);
    ShrubPrimary = CreateScatterComponent(TEXT("CinematicShrubPrimary"), 450000);
    ShrubSecondary = CreateScatterComponent(TEXT("CinematicShrubSecondary"), 425000);
    GroundPlants = CreateScatterComponent(TEXT("CinematicGroundPlants"), 260000);
    Rocks = CreateScatterComponent(TEXT("CinematicRocks"), 1000000);
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

    // Keep the first high-detail rollout renderer-safe. The audited vegetation
    // retains its materials and wind, while collision, dynamic shadows, distance
    // fields, and dynamic indirect-lighting updates remain disabled.
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
    UStaticMesh* FallbackTree = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_03.PCG_Tree_03"));

    UStaticMesh* Pine = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine/SM_Pine_1.SM_Pine_1"));
    UStaticMesh* Aspen = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen/SM_Columnar_Aspen_1.SM_Columnar_Aspen_1"));
    UStaticMesh* Oak = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak/SM_Cork_Oak_1.SM_Cork_Oak_1"));
    UStaticMesh* Coconut = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Coconut_Tree/SM_Coconut_Tree_1.SM_Coconut_Tree_1"));
    if (!Coconut)
    {
        Coconut = LoadObject<UStaticMesh>(
            nullptr,
            TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Windmill_Palm/SM_Windmill_Palm_1.SM_Windmill_Palm_1"));
    }

    UStaticMesh* ShrubA = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_A/GV_Vol7_Shrub_A_full_type1.GV_Vol7_Shrub_A_full_type1"));
    UStaticMesh* ShrubB = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_B/GV_Vol7_Shrub_B_full_type1.GV_Vol7_Shrub_B_full_type1"));
    UStaticMesh* GroundPlant = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Abelia_x_grandiflora_Nanite_Free_Sample.SM_Abelia_x_grandiflora_Nanite_Free_Sample"));
    UStaticMesh* Boulder = LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Boulder_02.PCG_Boulder_02"));

    Pine = Pine ? Pine : FallbackTree;
    Aspen = Aspen ? Aspen : Pine;
    Oak = Oak ? Oak : Aspen;
    Coconut = Coconut ? Coconut : Oak;

    PineTrees->SetStaticMesh(Pine);
    AspenTrees->SetStaticMesh(Aspen);
    OakTrees->SetStaticMesh(Oak);
    CoastalTrees->SetStaticMesh(Coconut);
    ShrubPrimary->SetStaticMesh(ShrubA);
    ShrubSecondary->SetStaticMesh(ShrubB ? ShrubB : ShrubA);
    GroundPlants->SetStaticMesh(GroundPlant);
    Rocks->SetStaticMesh(Boulder);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Cinematic Environment] Exact audited meshes: pine=%s aspen=%s oak=%s coastal=%s shrubA=%s shrubB=%s plant=%s rock=%s."),
        PineTrees->GetStaticMesh() ? *PineTrees->GetStaticMesh()->GetPathName() : TEXT("None"),
        AspenTrees->GetStaticMesh() ? *AspenTrees->GetStaticMesh()->GetPathName() : TEXT("None"),
        OakTrees->GetStaticMesh() ? *OakTrees->GetStaticMesh()->GetPathName() : TEXT("None"),
        CoastalTrees->GetStaticMesh() ? *CoastalTrees->GetStaticMesh()->GetPathName() : TEXT("None"),
        ShrubPrimary->GetStaticMesh() ? *ShrubPrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
        ShrubSecondary->GetStaticMesh() ? *ShrubSecondary->GetStaticMesh()->GetPathName() : TEXT("None"),
        GroundPlants->GetStaticMesh() ? *GroundPlants->GetStaticMesh()->GetPathName() : TEXT("None"),
        Rocks->GetStaticMesh() ? *Rocks->GetStaticMesh()->GetPathName() : TEXT("None"));

    const bool bUsingFallbackTree = Pine == FallbackTree;
    if (bUsingFallbackTree)
    {
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[Aether Cinematic Environment] DZ tree assets failed to load; temporary PCG fallback is active."));
    }

    return PineTrees->GetStaticMesh() != nullptr && Rocks->GetStaticMesh() != nullptr;
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
    return FMath::Clamp(DesiredHeightCm / Height, 0.25f, 4.0f);
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
    PineTrees->ClearInstances();
    AspenTrees->ClearInstances();
    OakTrees->ClearInstances();
    CoastalTrees->ClearInstances();
    ShrubPrimary->ClearInstances();
    ShrubSecondary->ClearInstances();
    GroundPlants->ClearInstances();
    Rocks->ClearInstances();
    PendingChunks.Reset();
    GeneratedChunks.Reset();
    TotalTrees = 0;
    TotalShrubs = 0;
    TotalGroundPlants = 0;
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
        TEXT("[Aether Cinematic Environment] Local ring centered on chunk (%d,%d); %d chunks queued."),
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
    TSet<uint64> ShrubCells;
    TSet<uint64> PlantCells;
    TSet<uint64> RockCells;
    int32 ChunkTrees = 0;
    int32 ChunkShrubs = 0;
    int32 ChunkGroundPlants = 0;
    int32 ChunkRocks = 0;

    auto RandomPoint = [&]()
    {
        return FVector2D(
            Random.FRandRange(Bounds.Min.X, Bounds.Max.X),
            Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y));
    };

    for (int32 Attempt = 0;
         Attempt < TreesPerChunk * 10 && ChunkTrees < TreesPerChunk;
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
        const float Forest = AetherVerifiedEnvironment::SpatialField(
            Point.X,
            Point.Y,
            0.0000042f,
            80.83f);
        const float Moisture = AetherVerifiedEnvironment::SpatialField(
            Point.X,
            Point.Y,
            0.0000061f,
            37.11f);
        const float Coast = AetherVerifiedEnvironment::SpatialField(
            Point.X,
            Point.Y,
            0.0000084f,
            14.27f);
        const float Density = FMath::Clamp(0.28f + Forest * 0.66f, 0.28f, 0.94f);

        if (HeightMeters < 2.0f || HeightMeters > 3900.0f || Slope > 0.42f
            || Random.FRand() > Density
            || !ReserveCell(TreeCells, Point.X, Point.Y, 2200.0f))
        {
            continue;
        }

        UHierarchicalInstancedStaticMeshComponent* Target = OakTrees;
        float DesiredHeightCm = Random.FRandRange(1500.0f, 2300.0f);

        if (HeightMeters < 180.0f && Coast > 0.58f && CoastalTrees->GetStaticMesh())
        {
            Target = CoastalTrees;
            DesiredHeightCm = Random.FRandRange(1600.0f, 2450.0f);
        }
        else if (HeightMeters > 850.0f || Slope > 0.24f)
        {
            Target = PineTrees;
            DesiredHeightCm = Random.FRandRange(2100.0f, 3300.0f);
        }
        else if (Moisture > 0.54f)
        {
            Target = AspenTrees;
            DesiredHeightCm = Random.FRandRange(1850.0f, 2850.0f);
        }

        UStaticMesh* Mesh = Target->GetStaticMesh();
        if (!Mesh)
        {
            continue;
        }

        const float Scale = ScaleForHeight(Mesh, DesiredHeightCm);
        Target->AddInstance(
            FTransform(
                FRotator(
                    Random.FRandRange(-1.2f, 1.2f),
                    Random.FRandRange(-180.0f, 180.0f),
                    Random.FRandRange(-1.2f, 1.2f)),
                Location - FVector(0.0f, 0.0f, Random.FRandRange(1.0f, 7.0f)),
                FVector(
                    Scale * Random.FRandRange(0.90f, 1.10f),
                    Scale * Random.FRandRange(0.90f, 1.10f),
                    Scale * Random.FRandRange(0.94f, 1.16f))),
            true);
        ++ChunkTrees;
    }

    if (ShrubPrimary->GetStaticMesh())
    {
        for (int32 Attempt = 0;
             Attempt < ShrubsPerChunk * 9 && ChunkShrubs < ShrubsPerChunk;
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
            const float EdgeField = AetherVerifiedEnvironment::SpatialField(
                Point.X,
                Point.Y,
                0.0000097f,
                24.15f);
            if (HeightMeters < 2.0f || HeightMeters > 3000.0f || Normal.Z < 0.78f
                || Random.FRand() > FMath::Clamp(0.34f + EdgeField * 0.48f, 0.34f, 0.82f)
                || !ReserveCell(ShrubCells, Point.X, Point.Y, 1700.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Target =
                ShrubSecondary->GetStaticMesh() && Random.FRand() > 0.52f
                    ? ShrubSecondary
                    : ShrubPrimary;
            UStaticMesh* Mesh = Target->GetStaticMesh();
            const float Scale = ScaleForHeight(Mesh, Random.FRandRange(150.0f, 360.0f));
            Target->AddInstance(
                FTransform(
                    FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                    Location - FVector(0.0f, 0.0f, 2.0f),
                    FVector(
                        Scale * Random.FRandRange(0.82f, 1.18f),
                        Scale * Random.FRandRange(0.82f, 1.18f),
                        Scale * Random.FRandRange(0.90f, 1.22f))),
                true);
            ++ChunkShrubs;
        }
    }

    if (GroundPlants->GetStaticMesh())
    {
        for (int32 Attempt = 0;
             Attempt < GroundPlantsPerChunk * 8 && ChunkGroundPlants < GroundPlantsPerChunk;
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
            if (HeightMeters < 2.0f || HeightMeters > 2200.0f || Normal.Z < 0.86f
                || Random.FRand() > 0.68f
                || !ReserveCell(PlantCells, Point.X, Point.Y, 1200.0f))
            {
                continue;
            }

            const float Scale = ScaleForHeight(
                GroundPlants->GetStaticMesh(),
                Random.FRandRange(65.0f, 135.0f));
            GroundPlants->AddInstance(
                FTransform(
                    FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                    Location - FVector(0.0f, 0.0f, 1.0f),
                    FVector(Scale * Random.FRandRange(0.82f, 1.22f))),
                true);
            ++ChunkGroundPlants;
        }
    }

    for (int32 Attempt = 0;
         Attempt < RocksPerChunk * 18 && ChunkRocks < RocksPerChunk;
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
        const float Acceptance = FMath::Clamp(0.17f + Slope * 1.75f, 0.17f, 0.86f);
        if (HeightMeters < 2.0f || HeightMeters > 4300.0f || Normal.Z < 0.34f
            || Random.FRand() > Acceptance
            || !ReserveCell(RockCells, Point.X, Point.Y, 5400.0f))
        {
            continue;
        }

        const float DesiredHeight = Random.FRand() < 0.90f
            ? Random.FRandRange(220.0f, 760.0f)
            : Random.FRandRange(760.0f, 1500.0f);
        const float Scale = ScaleForHeight(Rocks->GetStaticMesh(), DesiredHeight);
        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        Rocks->AddInstance(
            FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(5.0f, 42.0f)),
                FVector(
                    Scale * Random.FRandRange(0.80f, 1.32f),
                    Scale * Random.FRandRange(0.80f, 1.28f),
                    Scale * Random.FRandRange(0.76f, 1.16f))),
            true);
        ++ChunkRocks;
    }

    GeneratedChunks.Add(Chunk);
    TotalTrees += ChunkTrees;
    TotalShrubs += ChunkShrubs;
    TotalGroundPlants += ChunkGroundPlants;
    TotalRocks += ChunkRocks;

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Cinematic Environment] Chunk (%d,%d): %d trees, %d shrubs, %d plants, %d rocks. Ring total=%d/%d/%d/%d."),
        Chunk.X,
        Chunk.Y,
        ChunkTrees,
        ChunkShrubs,
        ChunkGroundPlants,
        ChunkRocks,
        TotalTrees,
        TotalShrubs,
        TotalGroundPlants,
        TotalRocks);

    if (GEngine && GeneratedChunks.Num() == 1)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            20.0f,
            FColor(100, 255, 140),
            FString::Printf(
                TEXT("AETHER CINEMATIC ENVIRONMENT // %d TREES // %d SHRUBS // %d ROCKS"),
                TotalTrees,
                TotalShrubs,
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
                TEXT("[Aether Cinematic Environment] Required tree or rock meshes failed to load."));
            if (GEngine)
            {
                GEngine->AddOnScreenDebugMessage(
                    -1,
                    20.0f,
                    FColor::Red,
                    TEXT("AETHER ENVIRONMENT ERROR // REQUIRED MESHES FAILED TO LOAD"));
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
                TEXT("[Aether Cinematic Environment] Waiting for Mesh Terrain collision near aircraft (%d/%d)."),
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
                TEXT("[Aether Cinematic Environment] Mesh Terrain collision did not become ready; no vegetation generated."));
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
        TEXT("[Aether Cinematic Environment] CINEMATIC MAP-WIDE STREAMING READY."));
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
