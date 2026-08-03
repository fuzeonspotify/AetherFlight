#include "AetherBiomeScatterActor.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "LandscapeProxy.h"
#include "Modules/ModuleManager.h"
#include "TimerManager.h"

namespace AetherEnvironment
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr float DefaultHalfWorldCm = 2400000.0f;
    constexpr float LandscapeBorderCm = 12000.0f;
    constexpr float TreeCellSizeCm = 850.0f;
    constexpr float RockCellSizeCm = 1800.0f;
    constexpr float InitialBuildDelaySeconds = 2.0f;
    constexpr float RetryBuildDelaySeconds = 2.0f;
    constexpr int32 MaxBuildAttempts = 6;
}

AAetherBiomeScatterActor::AAetherBiomeScatterActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    ConiferPrimary = CreateScatterComponent(TEXT("ConiferPrimary"), 2400000, 6000000);
    ConiferSecondary = CreateScatterComponent(TEXT("ConiferSecondary"), 2400000, 6000000);
    BroadleafTrees = CreateScatterComponent(TEXT("BroadleafTrees"), 1900000, 4800000);
    Shrubs = CreateScatterComponent(TEXT("Shrubs"), 260000, 850000);
    GroundCover = CreateScatterComponent(TEXT("GroundCover"), 90000, 350000);
    BoulderPrimary = CreateScatterComponent(TEXT("BoulderPrimary"), 1200000, 4200000);
    BoulderSecondary = CreateScatterComponent(TEXT("BoulderSecondary"), 1400000, 4800000);
    BoulderVariant3 = CreateScatterComponent(TEXT("BoulderVariant3"), 1200000, 4200000);
    BoulderVariant4 = CreateScatterComponent(TEXT("BoulderVariant4"), 1200000, 4200000);
    BoulderVariant5 = CreateScatterComponent(TEXT("BoulderVariant5"), 1200000, 4200000);
    BoulderVariant6 = CreateScatterComponent(TEXT("BoulderVariant6"), 1200000, 4200000);
    BoulderVariant7 = CreateScatterComponent(TEXT("BoulderVariant7"), 1200000, 4200000);
}

void AAetherBiomeScatterActor::BeginPlay()
{
    Super::BeginPlay();
    if (bEnableRuntimeScatter)
    {
        // World Partition needs more than one frame to stream Landscape collision.
        BuildAttempt = 0;
        GetWorldTimerManager().SetTimer(
            ScatterBuildTimer,
            this,
            &AAetherBiomeScatterActor::BuildEnvironment,
            AetherEnvironment::InitialBuildDelaySeconds,
            false);
    }
}

UHierarchicalInstancedStaticMeshComponent* AAetherBiomeScatterActor::CreateScatterComponent(
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
    Component->bCastDynamicShadow = true;
    Component->bAffectDistanceFieldLighting = true;
    return Component;
}

TArray<UHierarchicalInstancedStaticMeshComponent*> AAetherBiomeScatterActor::GetRockComponents() const
{
    return {
        BoulderPrimary,
        BoulderSecondary,
        BoulderVariant3,
        BoulderVariant4,
        BoulderVariant5,
        BoulderVariant6,
        BoulderVariant7
    };
}

int32 AAetherBiomeScatterActor::GetRockInstanceCount() const
{
    int32 Count = 0;
    for (const UHierarchicalInstancedStaticMeshComponent* RockComponent : GetRockComponents())
    {
        Count += RockComponent->GetInstanceCount();
    }
    return Count;
}

void AAetherBiomeScatterActor::ClearEnvironment()
{
    GetWorldTimerManager().ClearTimer(ScatterBuildTimer);
    ConiferPrimary->ClearInstances();
    ConiferSecondary->ClearInstances();
    BroadleafTrees->ClearInstances();
    Shrubs->ClearInstances();
    GroundCover->ClearInstances();
    for (UHierarchicalInstancedStaticMeshComponent* RockComponent : GetRockComponents())
    {
        RockComponent->ClearInstances();
    }
    BuildAttempt = 0;
    bBuilt = false;
}

UStaticMesh* AAetherBiomeScatterActor::LoadFirstAvailable(
    const TArray<FSoftObjectPath>& CandidatePaths) const
{
    for (const FSoftObjectPath& Path : CandidatePaths)
    {
        if (UStaticMesh* Mesh = Cast<UStaticMesh>(Path.TryLoad()))
        {
            return Mesh;
        }
    }
    return nullptr;
}

TArray<UStaticMesh*> AAetherBiomeScatterActor::LoadLargestMeshesInPaths(
    const TArray<FName>& PackagePaths, const int32 MaxMeshes) const
{
    TArray<UStaticMesh*> Meshes;
    if (PackagePaths.Num() == 0 || MaxMeshes <= 0)
    {
        return Meshes;
    }

    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    FARFilter Filter;
    Filter.PackagePaths.Append(PackagePaths);
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

void AAetherBiomeScatterActor::BuildEnvironment()
{
    if (bBuilt || !GetWorld())
    {
        return;
    }
    ++BuildAttempt;

    UStaticMesh* ConiferA = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Conifer_A.SM_Conifer_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Conifer.SM_Conifer"))
    });
    UStaticMesh* ConiferB = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Conifer_B.SM_Conifer_B")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Conifer_02.SM_Conifer_02"))
    });
    UStaticMesh* Broadleaf = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Broadleaf_A.SM_Broadleaf_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Broadleaf.SM_Broadleaf"))
    });
    UStaticMesh* Shrub = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Shrub_A.SM_Shrub_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Shrub.SM_Shrub"))
    });
    UStaticMesh* Cover = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_GroundCover_A.SM_GroundCover_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_Fern.SM_Fern"))
    });
    UStaticMesh* BoulderA = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Rocks/SM_Boulder_A.SM_Boulder_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Rocks/SM_CliffRock.SM_CliffRock"))
    });
    UStaticMesh* BoulderB = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Rocks/SM_Boulder_B.SM_Boulder_B")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Rocks/SM_CliffRock_B.SM_CliffRock_B"))
    });

    // Keep third-party pack names intact. The largest complete meshes in the
    // known source folders are selected automatically when Aether aliases do
    // not exist.
    const TArray<UStaticMesh*> PineMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Pine"))
    }, 2);
    const TArray<UStaticMesh*> AspenMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen"))
    }, 1);
    const TArray<UStaticMesh*> RockMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/Aether/Environment/Rocks")),
        FName(TEXT("/Game/Rocks")),
        FName(TEXT("/Game/Rock_01")),
        FName(TEXT("/Game/Rock_02")),
        FName(TEXT("/Game/Rock_03")),
        FName(TEXT("/Game/Rock_04")),
        FName(TEXT("/Game/Rock_05")),
        FName(TEXT("/Game/Rock_06")),
        FName(TEXT("/Game/Rock_07"))
    }, 7);

    ConiferA = ConiferA ? ConiferA : (PineMeshes.Num() > 0 ? PineMeshes[0] : nullptr);
    ConiferB = ConiferB ? ConiferB : (PineMeshes.Num() > 1 ? PineMeshes[1] : nullptr);
    Broadleaf = Broadleaf ? Broadleaf : (AspenMeshes.Num() > 0 ? AspenMeshes[0] : nullptr);
    TArray<UStaticMesh*> SelectedRockMeshes;
    if (BoulderA)
    {
        SelectedRockMeshes.AddUnique(BoulderA);
    }
    if (BoulderB)
    {
        SelectedRockMeshes.AddUnique(BoulderB);
    }
    for (UStaticMesh* RockMesh : RockMeshes)
    {
        SelectedRockMeshes.AddUnique(RockMesh);
    }

    if (!ConiferA && !ConiferB && !Broadleaf && !Shrub && !Cover && SelectedRockMeshes.Num() == 0)
    {
        bBuilt = true;
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether] High-quality environment meshes are not installed. Run AuditEnvironmentAssets_UE58.py and follow HIGH_QUALITY_ENVIRONMENT_SETUP.md."));
        return;
    }

    ConiferB = ConiferB ? ConiferB : ConiferA;
    ConiferPrimary->SetStaticMesh(ConiferA);
    ConiferSecondary->SetStaticMesh(ConiferB);
    BroadleafTrees->SetStaticMesh(Broadleaf);
    Shrubs->SetStaticMesh(Shrub);
    GroundCover->SetStaticMesh(Cover);
    const TArray<UHierarchicalInstancedStaticMeshComponent*> RockComponents = GetRockComponents();
    for (int32 Index = 0; Index < RockComponents.Num(); ++Index)
    {
        RockComponents[Index]->SetStaticMesh(
            SelectedRockMeshes.IsValidIndex(Index) ? SelectedRockMeshes[Index] : nullptr);
    }

    FBox2D Bounds;
    if (!FindLandscapeBounds(Bounds))
    {
        Bounds = FBox2D(
            FVector2D(-AetherEnvironment::DefaultHalfWorldCm),
            FVector2D(AetherEnvironment::DefaultHalfWorldCm));
    }

    Bounds.Min += FVector2D(AetherEnvironment::LandscapeBorderCm);
    Bounds.Max -= FVector2D(AetherEnvironment::LandscapeBorderCm);
    FRandomStream Random(EnvironmentSeed * 104729 + 37);
    GenerateForest(Bounds, Random);
    GenerateRocks(Bounds, Random);
    DisableLegacyScatterIfReplaced();

    const int32 TreeCount = ConiferPrimary->GetInstanceCount()
        + ConiferSecondary->GetInstanceCount() + BroadleafTrees->GetInstanceCount();
    const int32 UnderstoryCount = Shrubs->GetInstanceCount() + GroundCover->GetInstanceCount();
    const int32 RockCount = GetRockInstanceCount();
    if (TreeCount == 0 && RockCount == 0 && BuildAttempt < AetherEnvironment::MaxBuildAttempts)
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether] Landscape streaming is not ready; retrying ecosystem build (%d/%d)."),
            BuildAttempt, AetherEnvironment::MaxBuildAttempts);
        GetWorldTimerManager().SetTimer(
            ScatterBuildTimer,
            this,
            &AAetherBiomeScatterActor::BuildEnvironment,
            AetherEnvironment::RetryBuildDelaySeconds,
            false);
        return;
    }

    bBuilt = true;
    UE_LOG(LogTemp, Display,
        TEXT("[Aether] Production ecosystem built: %d trees, %d understory plants, %d rocks."),
        TreeCount, UnderstoryCount, RockCount);
}

bool AAetherBiomeScatterActor::FindLandscapeBounds(FBox2D& OutBounds) const
{
    double LargestArea = 0.0;
    bool bFound = false;
    for (TActorIterator<ALandscapeProxy> It(GetWorld()); It; ++It)
    {
        if (!IsValid(*It) || It->IsActorBeingDestroyed() || It->IsHidden())
        {
            continue;
        }

        const FBox Box = It->GetComponentsBoundingBox(true);
        if (!Box.IsValid)
        {
            continue;
        }
        const double Area = static_cast<double>(Box.GetSize().X) * static_cast<double>(Box.GetSize().Y);
        if (Area > LargestArea)
        {
            LargestArea = Area;
            OutBounds = FBox2D(
                FVector2D(Box.Min.X, Box.Min.Y), FVector2D(Box.Max.X, Box.Max.Y));
            bFound = true;
        }
    }
    return bFound;
}

bool AAetherBiomeScatterActor::SampleLandscape(
    const float X, const float Y, float& OutHeightMeters, FVector& OutNormal) const
{
    FHitResult Hit;
    FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(AetherBiomeLandscapeSample), false, this);
    const FVector Start(X, Y, AetherEnvironment::TraceTopCm);
    const FVector End(X, Y, AetherEnvironment::TraceBottomCm);
    if (!GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, QueryParams))
    {
        return false;
    }

    if (!Hit.GetActor() || !Hit.GetActor()->IsA<ALandscapeProxy>())
    {
        return false;
    }

    OutHeightMeters = Hit.ImpactPoint.Z * 0.01f;
    OutNormal = Hit.ImpactNormal.GetSafeNormal();
    return true;
}

bool AAetherBiomeScatterActor::IsInsideRunwayClearance(const float X, const float Y) const
{
    constexpr float AirbaseX = -650000.0f;
    constexpr float AirbaseY = -900000.0f;
    return FMath::Abs(X - AirbaseX) < 175000.0f && FMath::Abs(Y - AirbaseY) < 30000.0f;
}

bool AAetherBiomeScatterActor::ReserveCell(
    TSet<uint64>& OccupiedCells, const float X, const float Y, const float CellSize) const
{
    const int32 CellX = FMath::FloorToInt(X / CellSize);
    const int32 CellY = FMath::FloorToInt(Y / CellSize);
    const uint64 Key = (static_cast<uint64>(static_cast<uint32>(CellX)) << 32u)
        | static_cast<uint32>(CellY);
    if (OccupiedCells.Contains(Key))
    {
        return false;
    }
    OccupiedCells.Add(Key);
    return true;
}

void AAetherBiomeScatterActor::GenerateForest(const FBox2D& Bounds, FRandomStream& Random)
{
    if (!ConiferPrimary->GetStaticMesh() && !ConiferSecondary->GetStaticMesh()
        && !BroadleafTrees->GetStaticMesh())
    {
        return;
    }

    TSet<uint64> OccupiedTreeCells;
    const int32 ClusterAttempts = ForestClusterBudget * 4;
    int32 AcceptedClusters = 0;
    for (int32 Attempt = 0; Attempt < ClusterAttempts && AcceptedClusters < ForestClusterBudget; ++Attempt)
    {
        const float CenterX = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float CenterY = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (IsInsideRunwayClearance(CenterX, CenterY))
        {
            continue;
        }

        const float ForestSignal = ValueNoise(CenterX * 0.0000043f + 17.0f, CenterY * 0.0000043f - 53.0f);
        const float MoistureSignal = ValueNoise(CenterX * 0.0000021f - 81.0f, CenterY * 0.0000021f + 29.0f);
        if (ForestSignal < 0.36f || MoistureSignal < 0.27f)
        {
            continue;
        }

        ++AcceptedClusters;
        const float Radius = Random.FRandRange(28000.0f, 72000.0f);
        const int32 ClusterTrees = FMath::Max(4, FMath::RoundToInt(
            TreesPerCluster * Random.FRandRange(0.65f, 1.35f)));
        for (int32 TreeIndex = 0; TreeIndex < ClusterTrees; ++TreeIndex)
        {
            const float Angle = Random.FRandRange(0.0f, 2.0f * PI);
            const float Distance = FMath::Sqrt(Random.FRand()) * Radius;
            const float X = CenterX + FMath::Cos(Angle) * Distance;
            const float Y = CenterY + FMath::Sin(Angle) * Distance;
            if (X <= Bounds.Min.X || X >= Bounds.Max.X || Y <= Bounds.Min.Y || Y >= Bounds.Max.Y)
            {
                continue;
            }
            TryAddTree(X, Y, Random, OccupiedTreeCells);
        }
    }
}

bool AAetherBiomeScatterActor::TryAddTree(
    const float X, const float Y, FRandomStream& Random, TSet<uint64>& OccupiedCells)
{
    if (IsInsideRunwayClearance(X, Y)
        || !ReserveCell(OccupiedCells, X, Y, AetherEnvironment::TreeCellSizeCm))
    {
        return false;
    }

    float HeightMeters = 0.0f;
    FVector Normal = FVector::UpVector;
    if (!SampleLandscape(X, Y, HeightMeters, Normal))
    {
        return false;
    }

    const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
    const float Moisture = ValueNoise(X * 0.0000061f + 91.0f, Y * 0.0000061f - 44.0f);
    const float Exposure = ValueNoise(X * 0.0000117f - 15.0f, Y * 0.0000117f + 63.0f);
    if (HeightMeters < 16.0f || HeightMeters > 1850.0f || Slope > 0.31f
        || Moisture < 0.24f || Exposure < 0.19f)
    {
        return false;
    }

    UHierarchicalInstancedStaticMeshComponent* Target = nullptr;
    const float SpeciesRoll = Random.FRand();
    if (HeightMeters < 720.0f && Moisture > 0.56f && BroadleafTrees->GetStaticMesh() && SpeciesRoll < 0.34f)
    {
        Target = BroadleafTrees;
    }
    else if (ConiferSecondary->GetStaticMesh() && SpeciesRoll > 0.57f)
    {
        Target = ConiferSecondary;
    }
    else if (ConiferPrimary->GetStaticMesh())
    {
        Target = ConiferPrimary;
    }
    else
    {
        Target = BroadleafTrees;
    }

    if (!Target || !Target->GetStaticMesh())
    {
        return false;
    }

    const float UniformScale = Random.FRandRange(0.72f, 1.36f);
    const float WidthScale = UniformScale * Random.FRandRange(0.88f, 1.12f);
    const float HeightScale = UniformScale * Random.FRandRange(0.92f, 1.20f);
    const FRotator Rotation(
        Random.FRandRange(-1.3f, 1.3f), Random.FRandRange(-180.0f, 180.0f), Random.FRandRange(-1.3f, 1.3f));
    Target->AddInstance(FTransform(
        Rotation,
        FVector(X, Y, HeightMeters * 100.0f - 4.0f),
        FVector(WidthScale, WidthScale, HeightScale)), false);

    TryAddUnderstory(X, Y, Random);
    return true;
}

void AAetherBiomeScatterActor::TryAddUnderstory(
    const float X, const float Y, FRandomStream& Random)
{
    if (Shrubs->GetStaticMesh() && Shrubs->GetInstanceCount() < ShrubInstanceBudget && Random.FRand() < 0.52f)
    {
        const float OffsetAngle = Random.FRandRange(0.0f, 2.0f * PI);
        const float OffsetDistance = Random.FRandRange(350.0f, 2100.0f);
        const float ShrubX = X + FMath::Cos(OffsetAngle) * OffsetDistance;
        const float ShrubY = Y + FMath::Sin(OffsetAngle) * OffsetDistance;
        float ShrubHeightMeters = 0.0f;
        FVector ShrubNormal = FVector::UpVector;
        if (SampleLandscape(ShrubX, ShrubY, ShrubHeightMeters, ShrubNormal) && ShrubNormal.Z > 0.82f)
        {
            const float Scale = Random.FRandRange(0.68f, 1.48f);
            Shrubs->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                FVector(ShrubX, ShrubY, ShrubHeightMeters * 100.0f - 2.0f), FVector(Scale)), false);
        }
    }

    if (GroundCover->GetStaticMesh() && GroundCover->GetInstanceCount() < GroundCoverInstanceBudget
        && Random.FRand() < 0.72f)
    {
        const float OffsetAngle = Random.FRandRange(0.0f, 2.0f * PI);
        const float OffsetDistance = Random.FRandRange(180.0f, 1250.0f);
        const float CoverX = X + FMath::Cos(OffsetAngle) * OffsetDistance;
        const float CoverY = Y + FMath::Sin(OffsetAngle) * OffsetDistance;
        float CoverHeightMeters = 0.0f;
        FVector CoverNormal = FVector::UpVector;
        if (SampleLandscape(CoverX, CoverY, CoverHeightMeters, CoverNormal) && CoverNormal.Z > 0.86f)
        {
            const float Scale = Random.FRandRange(0.55f, 1.32f);
            GroundCover->AddInstance(FTransform(
                FRotator(0.0f, Random.FRandRange(-180.0f, 180.0f), 0.0f),
                FVector(CoverX, CoverY, CoverHeightMeters * 100.0f), FVector(Scale)), false);
        }
    }
}

void AAetherBiomeScatterActor::GenerateRocks(const FBox2D& Bounds, FRandomStream& Random)
{
    TArray<UHierarchicalInstancedStaticMeshComponent*> AvailableRockComponents;
    for (UHierarchicalInstancedStaticMeshComponent* RockComponent : GetRockComponents())
    {
        if (RockComponent->GetStaticMesh())
        {
            AvailableRockComponents.Add(RockComponent);
        }
    }
    if (AvailableRockComponents.Num() == 0)
    {
        return;
    }

    TSet<uint64> OccupiedRockCells;
    const int32 Attempts = RockInstanceBudget * 12;
    int32 RockCount = 0;
    for (int32 Attempt = 0; Attempt < Attempts && RockCount < RockInstanceBudget; ++Attempt)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (IsInsideRunwayClearance(X, Y)
            || !ReserveCell(OccupiedRockCells, X, Y, AetherEnvironment::RockCellSizeCm))
        {
            continue;
        }

        float HeightMeters = 0.0f;
        FVector Normal = FVector::UpVector;
        if (!SampleLandscape(X, Y, HeightMeters, Normal))
        {
            continue;
        }

        const float Slope = 1.0f - FMath::Clamp(Normal.Z, 0.0f, 1.0f);
        const float Exposure = ValueNoise(X * 0.0000103f - 14.0f, Y * 0.0000103f + 62.0f);
        const float Outcrop = ValueNoise(X * 0.000027f + 39.0f, Y * 0.000027f - 77.0f);
        if (HeightMeters < 18.0f || HeightMeters > 2350.0f
            || (Slope < 0.055f && Outcrop < 0.73f) || Exposure < 0.42f)
        {
            continue;
        }

        UHierarchicalInstancedStaticMeshComponent* Target = AvailableRockComponents[
            Random.RandRange(0, AvailableRockComponents.Num() - 1)];

        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        const FVector Scale(
            Random.FRandRange(0.65f, 2.8f),
            Random.FRandRange(0.65f, 2.35f),
            Random.FRandRange(0.55f, 2.45f));
        Target->AddInstance(FTransform(
            Rotation, FVector(X, Y, HeightMeters * 100.0f - Random.FRandRange(8.0f, 55.0f)), Scale), false);
        ++RockCount;
    }
}

void AAetherBiomeScatterActor::DisableLegacyScatterIfReplaced()
{
    const bool bHasTrees = ConiferPrimary->GetInstanceCount() + ConiferSecondary->GetInstanceCount()
        + BroadleafTrees->GetInstanceCount() > 0;
    const bool bHasRocks = GetRockInstanceCount() > 0;
    if (!bHasTrees && !bHasRocks)
    {
        return;
    }

    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        if (*It == this)
        {
            continue;
        }
        TInlineComponentArray<UHierarchicalInstancedStaticMeshComponent*> Components;
        It->GetComponents(Components);
        for (UHierarchicalInstancedStaticMeshComponent* Component : Components)
        {
            const FName Name = Component->GetFName();
            if ((bHasTrees && Name == FName(TEXT("ProceduralForest")))
                || (bHasRocks && Name == FName(TEXT("ProceduralRocks"))))
            {
                Component->ClearInstances();
                Component->SetVisibility(false, true);
            }
        }
    }
}

float AAetherBiomeScatterActor::ValueNoise(const float X, const float Y) const
{
    const int32 X0 = FMath::FloorToInt(X);
    const int32 Y0 = FMath::FloorToInt(Y);
    const float TX = FMath::SmoothStep(0.0f, 1.0f, X - X0);
    const float TY = FMath::SmoothStep(0.0f, 1.0f, Y - Y0);
    const float A = FMath::Lerp(HashNoise(X0, Y0), HashNoise(X0 + 1, Y0), TX);
    const float B = FMath::Lerp(HashNoise(X0, Y0 + 1), HashNoise(X0 + 1, Y0 + 1), TX);
    return FMath::Lerp(A, B, TY);
}

float AAetherBiomeScatterActor::HashNoise(const int32 X, const int32 Y) const
{
    uint32 N = static_cast<uint32>(X) * 374761393u + static_cast<uint32>(Y) * 668265263u
        + static_cast<uint32>(EnvironmentSeed) * 1442695041u;
    N = (N ^ (N >> 13u)) * 1274126177u;
    return static_cast<float>(N ^ (N >> 16u)) / static_cast<float>(MAX_uint32);
}
