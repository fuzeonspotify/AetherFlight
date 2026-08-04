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
    constexpr int32 MaxPositionAttempts = 20;
    constexpr int32 MaxBuildAttempts = 8;

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
}

AAetherEnvironmentTestActor::AAetherEnvironmentTestActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    TreePrimary = CreateScatterComponent(TEXT("TestTreePrimary"), 250000, 1600000);
    TreeSecondary = CreateScatterComponent(TEXT("TestTreeSecondary"), 250000, 1500000);
    Shrubs = CreateScatterComponent(TEXT("TestShrubs"), 60000, 320000);
    RockPrimary = CreateScatterComponent(TEXT("TestRockPrimary"), 180000, 1000000);
    RockSecondary = CreateScatterComponent(TEXT("TestRockSecondary"), 180000, 900000);
}

void AAetherEnvironmentTestActor::BeginPlay()
{
    Super::BeginPlay();
    if (!bEnableEnvironmentTest || !GetWorld())
    {
        return;
    }

    // Prevent the older full-world runtime scatter from building at the same
    // time as this deliberately small approval zone.
    for (TActorIterator<AAetherBiomeScatterActor> It(GetWorld()); It; ++It)
    {
        It->ClearEnvironment();
        It->SetActorHiddenInGame(true);
    }

    GetWorldTimerManager().SetTimer(
        PositionTimer,
        this,
        &AAetherEnvironmentTestActor::PositionPlayerAboveTestArea,
        0.65f,
        false);
    GetWorldTimerManager().SetTimer(
        BuildTimer,
        this,
        &AAetherEnvironmentTestActor::BuildTestArea,
        3.0f,
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
    Component->bCastDynamicShadow = true;
    Component->bAffectDistanceFieldLighting = true;
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

    const float SpawnZ = FMath::Max(5000.0f, SpawnAltitudeFeet) * 30.48f;
    const FVector SpawnLocation(TestAreaCenter.X - 120000.0f, TestAreaCenter.Y, SpawnZ);
    const FRotator SpawnRotation(-3.0f, 0.0f, 0.0f);

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
        TEXT("[Aether Environment Test] Player positioned above test zone at X=%.0f Y=%.0f Z=%.0f."),
        SpawnLocation.X,
        SpawnLocation.Y,
        SpawnLocation.Z);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            10.0f,
            FColor(110, 255, 150),
            TEXT("AETHER // ENVIRONMENT TEST ZONE AHEAD"));
    }
}

TArray<UStaticMesh*> AAetherEnvironmentTestActor::LoadLargestMeshes(
    const TArray<FName>& Paths, const int32 MaxMeshes) const
{
    TArray<UStaticMesh*> Meshes;
    if (Paths.Num() == 0 || MaxMeshes <= 0)
    {
        return Meshes;
    }

    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    FARFilter Filter;
    Filter.PackagePaths.Append(Paths);
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;

    TArray<FAssetData> Assets;
    AssetRegistryModule.Get().GetAssets(Filter, Assets);
    for (const FAssetData& Asset : Assets)
    {
        if (UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset()))
        {
            Meshes.AddUnique(Mesh);
        }
    }

    Meshes.Sort([](const UStaticMesh& Left, const UStaticMesh& Right)
    {
        return Left.GetBounds().BoxExtent.SizeSquared() > Right.GetBounds().BoxExtent.SizeSquared();
    });
    if (Meshes.Num() > MaxMeshes)
    {
        Meshes.SetNum(MaxMeshes);
    }
    return Meshes;
}

UStaticMesh* AAetherEnvironmentTestActor::LoadFirstKeywordMesh(
    const TArray<FName>& Paths, const TArray<FString>& Keywords) const
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
        for (const FString& Keyword : Keywords)
        {
            if (Name.Contains(Keyword, ESearchCase::IgnoreCase))
            {
                return Cast<UStaticMesh>(Asset.GetAsset());
            }
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
        || CombinedName.Contains(TEXT("CompiledSection"), ESearchCase::IgnoreCase)
        || HitComponent->GetCollisionObjectType() == ECC_WorldStatic;
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
    const float MeshHeight = FMath::Max(100.0f, Mesh->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / MeshHeight, 0.18f, 5.0f);
}

void AAetherEnvironmentTestActor::BuildTestArea()
{
    ++BuildAttempts;
    TreePrimary->ClearInstances();
    TreeSecondary->ClearInstances();
    Shrubs->ClearInstances();
    RockPrimary->ClearInstances();
    RockSecondary->ClearInstances();

    TArray<UStaticMesh*> Trees = LoadLargestMeshes({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen")),
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak"))
    }, 2);
    TArray<UStaticMesh*> Rocks = LoadLargestMeshes({
        FName(TEXT("/Game/Aether/Environment/Rocks")),
        FName(TEXT("/Game/Rocks")),
        FName(TEXT("/Game/Rock_01")),
        FName(TEXT("/Game/Rock_02")),
        FName(TEXT("/Game/Rock_03")),
        FName(TEXT("/Game/Rock_04")),
        FName(TEXT("/Game/Rock_05")),
        FName(TEXT("/Game/Rock_06")),
        FName(TEXT("/Game/Rock_07"))
    }, 2);
    UStaticMesh* ShrubMesh = LoadFirstKeywordMesh({
        FName(TEXT("/Game/Aether/Environment/Foliage")),
        FName(TEXT("/Game/DZ_Assets"))
    }, { TEXT("shrub"), TEXT("bush"), TEXT("sapling"), TEXT("fern") });

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

    if (Trees.Num() == 0 && Rocks.Num() == 0 && !ShrubMesh)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Environment Test] No usable tree, shrub or rock meshes were found."));
        return;
    }

    FRandomStream Random(EnvironmentSeed);
    TSet<uint64> TreeCells;
    TSet<uint64> ShrubCells;
    TSet<uint64> RockCells;
    int32 SuccessfulTerrainTraces = 0;
    int32 TreesPlaced = 0;
    int32 ShrubsPlaced = 0;
    int32 RocksPlaced = 0;

    auto RandomPoint = [&]()
    {
        const float Angle = Random.FRandRange(0.0f, 2.0f * PI);
        const float Distance = FMath::Sqrt(Random.FRand()) * TestAreaRadiusCm;
        return FVector2D(
            TestAreaCenter.X + FMath::Cos(Angle) * Distance,
            TestAreaCenter.Y + FMath::Sin(Angle) * Distance);
    };

    if (Trees.Num() > 0)
    {
        const int32 Attempts = TreeBudget * 16;
        for (int32 Attempt = 0; Attempt < Attempts && TreesPlaced < TreeBudget; ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }
            ++SuccessfulTerrainTraces;
            const float HeightMeters = Location.Z * 0.01f;
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            if (HeightMeters < 8.0f || HeightMeters > 2450.0f || Slope > 0.25f
                || !ReserveCell(TreeCells, Point.X, Point.Y, 2300.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Target =
                Random.FRand() < 0.58f ? TreePrimary : TreeSecondary;
            UStaticMesh* Mesh = Target->GetStaticMesh();
            const float Scale = ScaleForDesiredHeight(Mesh, Random.FRandRange(1350.0f, 2700.0f));
            const FVector InstanceScale(
                Scale * Random.FRandRange(0.86f, 1.12f),
                Scale * Random.FRandRange(0.86f, 1.12f),
                Scale * Random.FRandRange(0.92f, 1.22f));
            Target->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                Location - FVector(0.0f, 0.0f, Random.FRandRange(2.0f, 10.0f)),
                InstanceScale), true);
            ++TreesPlaced;
        }
    }

    if (ShrubMesh)
    {
        const int32 Attempts = ShrubBudget * 14;
        for (int32 Attempt = 0; Attempt < Attempts && ShrubsPlaced < ShrubBudget; ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }
            ++SuccessfulTerrainTraces;
            const float HeightMeters = Location.Z * 0.01f;
            if (HeightMeters < 5.0f || HeightMeters > 2300.0f || Normal.Z < 0.84f
                || !ReserveCell(ShrubCells, Point.X, Point.Y, 1000.0f))
            {
                continue;
            }
            const float Scale = ScaleForDesiredHeight(ShrubMesh, Random.FRandRange(90.0f, 260.0f));
            Shrubs->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                Location - FVector(0.0f, 0.0f, 2.0f),
                FVector(Scale)), true);
            ++ShrubsPlaced;
        }
    }

    if (Rocks.Num() > 0)
    {
        const int32 Attempts = RockBudget * 22;
        for (int32 Attempt = 0; Attempt < Attempts && RocksPlaced < RockBudget; ++Attempt)
        {
            const FVector2D Point = RandomPoint();
            FVector Location;
            FVector Normal;
            if (!SampleTerrain(Point.X, Point.Y, Location, Normal))
            {
                continue;
            }
            ++SuccessfulTerrainTraces;
            const float HeightMeters = Location.Z * 0.01f;
            const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
            const float Acceptance = FMath::Clamp(0.10f + Slope * 1.8f, 0.10f, 0.78f);
            if (HeightMeters < 5.0f || HeightMeters > 3000.0f || Normal.Z < 0.42f
                || Random.FRand() > Acceptance
                || !ReserveCell(RockCells, Point.X, Point.Y, 5200.0f))
            {
                continue;
            }

            UHierarchicalInstancedStaticMeshComponent* Target =
                Random.FRand() < 0.62f ? RockPrimary : RockSecondary;
            UStaticMesh* Mesh = Target->GetStaticMesh();
            const float DesiredHeight = Random.FRand() < 0.92f
                ? Random.FRandRange(120.0f, 650.0f)
                : Random.FRandRange(650.0f, 1500.0f);
            const float Scale = ScaleForDesiredHeight(Mesh, DesiredHeight);
            FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
            Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
            Target->AddInstance(FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(10.0f, 80.0f)),
                FVector(
                    Scale * Random.FRandRange(0.76f, 1.30f),
                    Scale * Random.FRandRange(0.76f, 1.26f),
                    Scale * Random.FRandRange(0.68f, 1.15f))), true);
            ++RocksPlaced;
        }
    }

    if (SuccessfulTerrainTraces < 30 && BuildAttempts < AetherEnvironmentTest::MaxBuildAttempts)
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Environment Test] Mesh Terrain collision is still streaming; retrying test-zone build (%d/%d)."),
            BuildAttempts,
            AetherEnvironmentTest::MaxBuildAttempts);
        GetWorldTimerManager().SetTimer(
            BuildTimer,
            this,
            &AAetherEnvironmentTestActor::BuildTestArea,
            2.0f,
            false);
        return;
    }

    ReportResult(TreesPlaced, ShrubsPlaced, RocksPlaced);
}

void AAetherEnvironmentTestActor::ReportResult(
    const int32 TreesPlaced, const int32 ShrubsPlaced, const int32 RocksPlaced) const
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
            15.0f,
            FColor(110, 255, 150),
            FString::Printf(
                TEXT("AETHER TEST READY // %d TREES // %d SHRUBS // %d ROCKS"),
                TreesPlaced,
                ShrubsPlaced,
                RocksPlaced));
    }
}
