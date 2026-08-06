#include "AetherEnvironmentTestActor.h"

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

namespace AetherEnvironmentTest
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr int32 MaxPositionAttempts = 24;
    constexpr int32 MaxPrepareAttempts = 10;
    constexpr int32 CandidatesPerBatch = 48;
    constexpr int32 PlacementsPerBatch = 8;

    bool LooksLikeWater(const FHitResult& Hit)
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

    bool IsUnsafeAggregateMeshName(const FString& Name)
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
}

AAetherEnvironmentTestActor::AAetherEnvironmentTestActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    TreePrimary = CreateScatterComponent(TEXT("TestTreePrimary"), 0, 900000);
    TreeSecondary = CreateScatterComponent(TEXT("TestTreeSecondary"), 0, 850000);
    Shrubs = CreateScatterComponent(TEXT("TestShrubs"), 0, 260000);
    RockPrimary = CreateScatterComponent(TEXT("TestRockPrimary"), 0, 700000);
    RockSecondary = CreateScatterComponent(TEXT("TestRockSecondary"), 0, 650000);
}

void AAetherEnvironmentTestActor::BeginPlay()
{
    Super::BeginPlay();
    if (!bEnableEnvironmentTest || !GetWorld())
    {
        return;
    }

    // The approval zone is the only environment generator allowed during this
    // run. Cancel the older full-world scatter before its delayed build begins.
    for (TActorIterator<AAetherBiomeScatterActor> It(GetWorld()); It; ++It)
    {
        It->ClearEnvironment();
        It->SetActorHiddenInGame(true);
    }

    GetWorldTimerManager().SetTimer(
        PositionTimer,
        this,
        &AAetherEnvironmentTestActor::PositionPlayerAboveTestArea,
        0.75f,
        false);
    GetWorldTimerManager().SetTimer(
        PrepareTimer,
        this,
        &AAetherEnvironmentTestActor::PrepareTestArea,
        4.0f,
        false);
}

UHierarchicalInstancedStaticMeshComponent* AAetherEnvironmentTestActor::CreateScatterComponent(
    const FName Name, const int32 StartCullDistance, const int32 EndCullDistance)
{
    UHierarchicalInstancedStaticMeshComponent* Component =
        CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(Name);
    Component->SetupAttachment(Root);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetGenerateOverlapEvents(false);
    Component->SetCanEverAffectNavigation(false);
    Component->SetCullDistances(StartCullDistance, EndCullDistance);
    Component->SetMobility(EComponentMobility::Movable);
    Component->bEnableDensityScaling = true;

    // The first test is about asset scale and placement, not final lighting.
    // Third-party foliage with thousands of instances, VSM shadows, and
    // distance-field updates caused the renderer to hitch and eventually crash.
    Component->SetCastShadow(false);
    Component->bCastDynamicShadow = false;
    Component->bAffectDistanceFieldLighting = false;
    Component->bAffectDynamicIndirectLighting = false;
    return Component;
}

void AAetherEnvironmentTestActor::PositionPlayerAboveTestArea()
{
    ++PositionAttempts;
    APlayerController* Controller = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
    if (!Pawn)
    {
        if (PositionAttempts < AetherEnvironmentTest::MaxPositionAttempts)
        {
            GetWorldTimerManager().SetTimer(
                PositionTimer,
                this,
                &AAetherEnvironmentTestActor::PositionPlayerAboveTestArea,
                0.25f,
                false);
        }
        return;
    }

    const float SpawnZ = FMath::Max(8000.0f, SpawnAltitudeFeet) * 30.48f;
    const FVector SpawnLocation(TestAreaCenter.X - 180000.0f, TestAreaCenter.Y, SpawnZ);
    const FRotator SpawnRotation(-4.0f, 0.0f, 0.0f);

    if (UPrimitiveComponent* RootPrimitive = Cast<UPrimitiveComponent>(Pawn->GetRootComponent()))
    {
        RootPrimitive->SetPhysicsLinearVelocity(FVector::ZeroVector);
        RootPrimitive->SetPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    }
    Pawn->SetActorLocationAndRotation(
        SpawnLocation,
        SpawnRotation,
        false,
        nullptr,
        ETeleportType::TeleportPhysics);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Environment Test] Player positioned west of the safe test zone at X=%.0f Y=%.0f Z=%.0f."),
        SpawnLocation.X,
        SpawnLocation.Y,
        SpawnLocation.Z);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            12.0f,
            FColor(110, 255, 150),
            TEXT("AETHER // SAFE ENVIRONMENT TEST ZONE AHEAD"));
    }
}

TArray<UStaticMesh*> AAetherEnvironmentTestActor::LoadSuitableMeshes(
    const TArray<FName>& Paths,
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
        if (AetherEnvironmentTest::IsUnsafeAggregateMeshName(Name))
        {
            continue;
        }
        if (++LoadedAssets > 96)
        {
            break;
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

UStaticMesh* AAetherEnvironmentTestActor::LoadFirstKeywordMesh(
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

    for (const FAssetData& Asset : Assets)
    {
        const FString Name = Asset.AssetName.ToString();
        if (AetherEnvironmentTest::IsUnsafeAggregateMeshName(Name))
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
        if (!bKeywordMatch)
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

bool AAetherEnvironmentTestActor::SampleTerrain(
    const float X, const float Y, FVector& OutLocation, FVector& OutNormal) const
{
    if (!GetWorld())
    {
        return false;
    }

    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(AetherEnvironmentTestTrace), false, this);
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Params.AddIgnoredActor(Controller->GetPawn());
    }

    const FVector Start(X, Y, AetherEnvironmentTest::TraceTopCm);
    const FVector End(X, Y, AetherEnvironmentTest::TraceBottomCm);
    if (!GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params)
        || AetherEnvironmentTest::LooksLikeWater(Hit))
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

bool AAetherEnvironmentTestActor::ReserveCell(
    TSet<uint64>& Cells, const float X, const float Y, const float CellSize) const
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

float AAetherEnvironmentTestActor::ScaleForDesiredHeight(
    const UStaticMesh* Mesh, const float DesiredHeightCm) const
{
    if (!Mesh)
    {
        return 1.0f;
    }
    const float MeshHeight = FMath::Max(50.0f, Mesh->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / MeshHeight, 0.18f, 4.0f);
}

void AAetherEnvironmentTestActor::PrepareTestArea()
{
    ++PrepareAttempts;

    if (!bAssetsPrepared)
    {
        TreePrimary->ClearInstances();
        TreeSecondary->ClearInstances();
        Shrubs->ClearInstances();
        RockPrimary->ClearInstances();
        RockSecondary->ClearInstances();

        const TArray<UStaticMesh*> Trees = LoadSuitableMeshes({
            FName(TEXT("/Game/Aether/Environment/Foliage")),
            FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine")),
            FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen")),
            FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak"))
        }, 2, 2400.0f, 450.0f, 12000.0f, 2.5f);
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
        }, 2, 450.0f, 40.0f, 8000.0f, 5.0f);
        UStaticMesh* ShrubMesh = LoadFirstKeywordMesh({
            FName(TEXT("/Game/Aether/Environment/Foliage")),
            FName(TEXT("/Game/DZ_Assets"))
        }, { TEXT("shrub"), TEXT("bush"), TEXT("sapling"), TEXT("fern") }, 20.0f, 1200.0f);

        if (Trees.Num() > 0)
        {
            TreePrimary->SetStaticMesh(Trees[0]);
            TreeSecondary->SetStaticMesh(Trees.IsValidIndex(1) ? Trees[1] : Trees[0]);
        }
        if (Rocks.Num() > 0)
        {
            RockPrimary->SetStaticMesh(Rocks[0]);
            RockSecondary->SetStaticMesh(Rocks.IsValidIndex(1) ? Rocks[1] : Rocks[0]);
        }
        Shrubs->SetStaticMesh(ShrubMesh);
        bAssetsPrepared = true;

        UE_LOG(LogTemp, Display,
            TEXT("[Aether Environment Test] Selected assets: treeA=%s treeB=%s shrub=%s rockA=%s rockB=%s."),
            TreePrimary->GetStaticMesh() ? *TreePrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
            TreeSecondary->GetStaticMesh() ? *TreeSecondary->GetStaticMesh()->GetPathName() : TEXT("None"),
            Shrubs->GetStaticMesh() ? *Shrubs->GetStaticMesh()->GetPathName() : TEXT("None"),
            RockPrimary->GetStaticMesh() ? *RockPrimary->GetStaticMesh()->GetPathName() : TEXT("None"),
            RockSecondary->GetStaticMesh() ? *RockSecondary->GetStaticMesh()->GetPathName() : TEXT("None"));
    }

    int32 SuccessfulProbes = 0;
    const float ProbeOffset = TestAreaRadiusCm * 0.45f;
    const FVector2D ProbePoints[] = {
        TestAreaCenter,
        TestAreaCenter + FVector2D(ProbeOffset, 0.0f),
        TestAreaCenter + FVector2D(-ProbeOffset, 0.0f),
        TestAreaCenter + FVector2D(0.0f, ProbeOffset),
        TestAreaCenter + FVector2D(0.0f, -ProbeOffset)
    };
    for (const FVector2D& Point : ProbePoints)
    {
        FVector Location;
        FVector Normal;
        SuccessfulProbes += SampleTerrain(Point.X, Point.Y, Location, Normal) ? 1 : 0;
    }

    if (SuccessfulProbes < 2)
    {
        if (PrepareAttempts < AetherEnvironmentTest::MaxPrepareAttempts)
        {
            UE_LOG(LogTemp, Display,
                TEXT("[Aether Environment Test] Mesh Terrain still streaming (%d/5 probes); retrying without generating instances."),
                SuccessfulProbes);
            GetWorldTimerManager().SetTimer(
                PrepareTimer,
                this,
                &AAetherEnvironmentTestActor::PrepareTestArea,
                1.5f,
                false);
            return;
        }

        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Environment Test] Test zone never received enough Mesh Terrain collision; no instances were generated."));
        ReportResult();
        return;
    }

    if (!TreePrimary->GetStaticMesh() && !RockPrimary->GetStaticMesh() && !Shrubs->GetStaticMesh())
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Environment Test] No safe individual tree, shrub, or rock meshes were found. Aggregate meshes were intentionally rejected."));
        ReportResult();
        return;
    }

    Random.Initialize(EnvironmentSeed);
    TreeCells.Reset();
    ShrubCells.Reset();
    RockCells.Reset();
    TreesPlaced = 0;
    ShrubsPlaced = 0;
    RocksPlaced = 0;
    AttemptsInPhase = 0;
    BuildPhase = EBuildPhase::Trees;
    bBuildStarted = true;

    while (CurrentPhaseFinished() && BuildPhase != EBuildPhase::Complete)
    {
        AdvanceBuildPhase();
    }

    UE_LOG(LogTemp, Display,
        TEXT("[Aether Environment Test] Terrain ready. Building in batches of at most %d placements every %.2f seconds."),
        AetherEnvironmentTest::PlacementsPerBatch,
        BuildBatchIntervalSeconds);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            10.0f,
            FColor(110, 255, 150),
            TEXT("AETHER // SAFE TEST ASSETS LOADING IN SMALL BATCHES"));
    }

    GetWorldTimerManager().SetTimer(
        BuildBatchTimer,
        this,
        &AAetherEnvironmentTestActor::ProcessBuildBatch,
        FMath::Max(0.05f, BuildBatchIntervalSeconds),
        true);
}

FVector2D AAetherEnvironmentTestActor::RandomPointInTestArea()
{
    const float Angle = Random.FRandRange(0.0f, 2.0f * PI);
    const float Distance = FMath::Sqrt(Random.FRand()) * TestAreaRadiusCm;
    return FVector2D(
        TestAreaCenter.X + FMath::Cos(Angle) * Distance,
        TestAreaCenter.Y + FMath::Sin(Angle) * Distance);
}

bool AAetherEnvironmentTestActor::TryPlaceTree()
{
    if (!TreePrimary->GetStaticMesh())
    {
        return false;
    }

    const FVector2D Point = RandomPointInTestArea();
    FVector Location;
    FVector Normal;
    if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
    {
        return false;
    }

    const float HeightMeters = Location.Z * 0.01f;
    const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
    if (HeightMeters < 8.0f || HeightMeters > 2350.0f || Slope > 0.23f
        || Random.FRand() > 0.62f
        || !ReserveCell(TreeCells, Point.X, Point.Y, 4200.0f))
    {
        return false;
    }

    UHierarchicalInstancedStaticMeshComponent* Target =
        TreeSecondary->GetStaticMesh() && Random.FRand() > 0.58f ? TreeSecondary : TreePrimary;
    UStaticMesh* Mesh = Target->GetStaticMesh();
    const float Scale = ScaleForDesiredHeight(Mesh, Random.FRandRange(1300.0f, 2500.0f));
    Target->AddInstance(FTransform(
        FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
        Location - FVector(0.0f, 0.0f, Random.FRandRange(2.0f, 8.0f)),
        FVector(
            Scale * Random.FRandRange(0.88f, 1.10f),
            Scale * Random.FRandRange(0.88f, 1.10f),
            Scale * Random.FRandRange(0.94f, 1.18f))), true);
    return true;
}

bool AAetherEnvironmentTestActor::TryPlaceShrub()
{
    UStaticMesh* Mesh = Shrubs->GetStaticMesh();
    if (!Mesh)
    {
        return false;
    }

    const FVector2D Point = RandomPointInTestArea();
    FVector Location;
    FVector Normal;
    if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
    {
        return false;
    }

    const float HeightMeters = Location.Z * 0.01f;
    if (HeightMeters < 5.0f || HeightMeters > 2250.0f || Normal.Z < 0.86f
        || Random.FRand() > 0.58f
        || !ReserveCell(ShrubCells, Point.X, Point.Y, 2600.0f))
    {
        return false;
    }

    const float Scale = ScaleForDesiredHeight(Mesh, Random.FRandRange(80.0f, 220.0f));
    Shrubs->AddInstance(FTransform(
        FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
        Location - FVector(0.0f, 0.0f, 2.0f),
        FVector(Scale)), true);
    return true;
}

bool AAetherEnvironmentTestActor::TryPlaceRock()
{
    if (!RockPrimary->GetStaticMesh())
    {
        return false;
    }

    const FVector2D Point = RandomPointInTestArea();
    FVector Location;
    FVector Normal;
    if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
    {
        return false;
    }

    const float HeightMeters = Location.Z * 0.01f;
    const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
    const float Acceptance = FMath::Clamp(0.14f + Slope * 1.55f, 0.14f, 0.72f);
    if (HeightMeters < 5.0f || HeightMeters > 2800.0f || Normal.Z < 0.48f
        || Random.FRand() > Acceptance
        || !ReserveCell(RockCells, Point.X, Point.Y, 6500.0f))
    {
        return false;
    }

    UHierarchicalInstancedStaticMeshComponent* Target =
        RockSecondary->GetStaticMesh() && Random.FRand() > 0.62f ? RockSecondary : RockPrimary;
    UStaticMesh* Mesh = Target->GetStaticMesh();
    const float DesiredHeight = Random.FRand() < 0.92f
        ? Random.FRandRange(100.0f, 520.0f)
        : Random.FRandRange(520.0f, 1100.0f);
    const float Scale = ScaleForDesiredHeight(Mesh, DesiredHeight);
    FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
    Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
    Target->AddInstance(FTransform(
        Rotation,
        Location - FVector(0.0f, 0.0f, Random.FRandRange(8.0f, 55.0f)),
        FVector(
            Scale * Random.FRandRange(0.78f, 1.24f),
            Scale * Random.FRandRange(0.78f, 1.22f),
            Scale * Random.FRandRange(0.72f, 1.12f))), true);
    return true;
}

int32 AAetherEnvironmentTestActor::CurrentPhaseMaximumAttempts() const
{
    switch (BuildPhase)
    {
    case EBuildPhase::Trees: return FMath::Max(TreeBudget * 14, 400);
    case EBuildPhase::Shrubs: return FMath::Max(ShrubBudget * 16, 240);
    case EBuildPhase::Rocks: return FMath::Max(RockBudget * 24, 300);
    default: return 0;
    }
}

bool AAetherEnvironmentTestActor::CurrentPhaseFinished() const
{
    switch (BuildPhase)
    {
    case EBuildPhase::Trees:
        return !TreePrimary->GetStaticMesh() || TreeBudget <= 0
            || TreesPlaced >= TreeBudget || AttemptsInPhase >= CurrentPhaseMaximumAttempts();
    case EBuildPhase::Shrubs:
        return !Shrubs->GetStaticMesh() || ShrubBudget <= 0
            || ShrubsPlaced >= ShrubBudget || AttemptsInPhase >= CurrentPhaseMaximumAttempts();
    case EBuildPhase::Rocks:
        return !RockPrimary->GetStaticMesh() || RockBudget <= 0
            || RocksPlaced >= RockBudget || AttemptsInPhase >= CurrentPhaseMaximumAttempts();
    default:
        return true;
    }
}

void AAetherEnvironmentTestActor::AdvanceBuildPhase()
{
    AttemptsInPhase = 0;
    switch (BuildPhase)
    {
    case EBuildPhase::Trees: BuildPhase = EBuildPhase::Shrubs; break;
    case EBuildPhase::Shrubs: BuildPhase = EBuildPhase::Rocks; break;
    case EBuildPhase::Rocks: BuildPhase = EBuildPhase::Complete; break;
    default: BuildPhase = EBuildPhase::Complete; break;
    }
}

void AAetherEnvironmentTestActor::ProcessBuildBatch()
{
    if (!bBuildStarted || BuildPhase == EBuildPhase::Complete)
    {
        GetWorldTimerManager().ClearTimer(BuildBatchTimer);
        ReportResult();
        return;
    }

    int32 PlacementsThisBatch = 0;
    for (int32 Candidate = 0;
         Candidate < AetherEnvironmentTest::CandidatesPerBatch
             && PlacementsThisBatch < AetherEnvironmentTest::PlacementsPerBatch
             && BuildPhase != EBuildPhase::Complete;
         ++Candidate)
    {
        if (CurrentPhaseFinished())
        {
            AdvanceBuildPhase();
            --Candidate;
            continue;
        }

        ++AttemptsInPhase;
        bool bPlaced = false;
        switch (BuildPhase)
        {
        case EBuildPhase::Trees: bPlaced = TryPlaceTree(); break;
        case EBuildPhase::Shrubs: bPlaced = TryPlaceShrub(); break;
        case EBuildPhase::Rocks: bPlaced = TryPlaceRock(); break;
        default: break;
        }

        if (bPlaced)
        {
            ++PlacementsThisBatch;
            switch (BuildPhase)
            {
            case EBuildPhase::Trees: ++TreesPlaced; break;
            case EBuildPhase::Shrubs: ++ShrubsPlaced; break;
            case EBuildPhase::Rocks: ++RocksPlaced; break;
            default: break;
            }
        }
    }

    while (CurrentPhaseFinished() && BuildPhase != EBuildPhase::Complete)
    {
        AdvanceBuildPhase();
    }

    if (BuildPhase == EBuildPhase::Complete)
    {
        GetWorldTimerManager().ClearTimer(BuildBatchTimer);
        ReportResult();
    }
}

void AAetherEnvironmentTestActor::ReportResult() const
{
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Environment Test] READY center=(%.0f, %.0f) radius=%.1f km trees=%d shrubs=%d rocks=%d."),
        TestAreaCenter.X,
        TestAreaCenter.Y,
        TestAreaRadiusCm * 0.00001f,
        TreesPlaced,
        ShrubsPlaced,
        RocksPlaced);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            20.0f,
            FColor(110, 255, 150),
            FString::Printf(
                TEXT("AETHER SAFE TEST READY // %d TREES // %d SHRUBS // %d ROCKS"),
                TreesPlaced,
                ShrubsPlaced,
                RocksPlaced));
    }
}
