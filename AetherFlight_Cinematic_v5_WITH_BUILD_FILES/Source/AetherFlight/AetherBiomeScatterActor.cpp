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
    constexpr float TreeCellSizeCm = 1900.0f;
    constexpr float RockCellSizeCm = 2600.0f;
    constexpr float InitialBuildDelaySeconds = 2.0f;
    constexpr float RetryBuildDelaySeconds = 2.0f;
    constexpr int32 MaxBuildAttempts = 6;

    enum class EBiomeType : uint8
    {
        Alpine,
        Boreal,
        AspenValley,
        DryWoodland,
        Coastal
    };
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
    CorkOakTrees = CreateScatterComponent(TEXT("CorkOakTrees"), 1900000, 4800000);
    WindmillPalms = CreateScatterComponent(TEXT("WindmillPalms"), 1900000, 4800000);
    CoconutPalms = CreateScatterComponent(TEXT("CoconutPalms"), 1900000, 4800000);
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

TArray<UHierarchicalInstancedStaticMeshComponent*> AAetherBiomeScatterActor::GetTreeComponents() const
{
    return {
        ConiferPrimary,
        ConiferSecondary,
        BroadleafTrees,
        CorkOakTrees,
        WindmillPalms,
        CoconutPalms
    };
}

int32 AAetherBiomeScatterActor::GetTreeInstanceCount() const
{
    int32 Count = 0;
    for (const UHierarchicalInstancedStaticMeshComponent* TreeComponent : GetTreeComponents())
    {
        Count += TreeComponent->GetInstanceCount();
    }
    return Count;
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
    for (UHierarchicalInstancedStaticMeshComponent* TreeComponent : GetTreeComponents())
    {
        TreeComponent->ClearInstances();
    }
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
    UStaticMesh* CorkOak = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_CorkOak_A.SM_CorkOak_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_CorkOak.SM_CorkOak"))
    });
    UStaticMesh* WindmillPalm = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_WindmillPalm_A.SM_WindmillPalm_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_WindmillPalm.SM_WindmillPalm"))
    });
    UStaticMesh* CoconutPalm = LoadFirstAvailable({
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_CoconutPalm_A.SM_CoconutPalm_A")),
        FSoftObjectPath(TEXT("/Game/Aether/Environment/Foliage/SM_CoconutPalm.SM_CoconutPalm"))
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
    const TArray<UStaticMesh*> CorkOakMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Cork_Oak"))
    }, 1);
    const TArray<UStaticMesh*> WindmillPalmMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Windmill_Palm"))
    }, 1);
    const TArray<UStaticMesh*> CoconutPalmMeshes = LoadLargestMeshesInPaths({
        FName(TEXT("/Game/DZ_Assets/DZ_Trees/Meshes/Coconut_Tree"))
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
    ConiferA = ConiferA ? ConiferA : ConiferB;
    ConiferB = ConiferB ? ConiferB : ConiferA;
    Broadleaf = Broadleaf ? Broadleaf : (AspenMeshes.Num() > 0 ? AspenMeshes[0] : nullptr);
    CorkOak = CorkOak ? CorkOak : (CorkOakMeshes.Num() > 0 ? CorkOakMeshes[0] : nullptr);
    WindmillPalm = WindmillPalm ? WindmillPalm
        : (WindmillPalmMeshes.Num() > 0 ? WindmillPalmMeshes[0] : nullptr);
    CoconutPalm = CoconutPalm ? CoconutPalm
        : (CoconutPalmMeshes.Num() > 0 ? CoconutPalmMeshes[0] : nullptr);
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

    if (!ConiferA && !ConiferB && !Broadleaf && !CorkOak && !WindmillPalm && !CoconutPalm
        && !Shrub && !Cover && SelectedRockMeshes.Num() == 0)
    {
        bBuilt = true;
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether] High-quality environment meshes are not installed. Run AuditEnvironmentAssets_UE58.py and follow HIGH_QUALITY_ENVIRONMENT_SETUP.md."));
        return;
    }

    ConiferPrimary->SetStaticMesh(ConiferA);
    ConiferSecondary->SetStaticMesh(ConiferB);
    BroadleafTrees->SetStaticMesh(Broadleaf);
    CorkOakTrees->SetStaticMesh(CorkOak);
    WindmillPalms->SetStaticMesh(WindmillPalm);
    CoconutPalms->SetStaticMesh(CoconutPalm);
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

    const int32 TreeCount = GetTreeInstanceCount();
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
        TEXT("[Aether] Ecosystem built: %d trees (%d pine A, %d pine B, %d aspen, %d cork oak, %d windmill palm, %d coconut), %d understory plants, %d rocks."),
        TreeCount,
        ConiferPrimary->GetInstanceCount(),
        ConiferSecondary->GetInstanceCount(),
        BroadleafTrees->GetInstanceCount(),
        CorkOakTrees->GetInstanceCount(),
        WindmillPalms->GetInstanceCount(),
        CoconutPalms->GetInstanceCount(),
        UnderstoryCount,
        RockCount);
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
    bool bHasAnyTreeMesh = false;
    for (const UHierarchicalInstancedStaticMeshComponent* TreeComponent : GetTreeComponents())
    {
        bHasAnyTreeMesh |= TreeComponent->GetStaticMesh() != nullptr;
    }
    if (!bHasAnyTreeMesh || TreeInstanceBudget <= 0)
    {
        return;
    }

    // Uniform candidates plus minimum spacing prevent the circular megaclusters
    // produced by the old algorithm. Low-frequency noise only changes density,
    // leaving gradual biome transitions and natural open clearings.
    TSet<uint64> OccupiedTreeCells;
    const int32 Attempts = TreeInstanceBudget * 8;
    int32 AcceptedTrees = GetTreeInstanceCount();
    for (int32 Attempt = 0; Attempt < Attempts && AcceptedTrees < TreeInstanceBudget; ++Attempt)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (IsInsideRunwayClearance(X, Y))
        {
            continue;
        }

        const float MacroBiome = ValueNoise(X * 0.00000125f + 17.0f, Y * 0.00000125f - 53.0f);
        const float ForestDetail = ValueNoise(X * 0.0000058f - 81.0f, Y * 0.0000058f + 29.0f);
        const float MoistureField = ValueNoise(X * 0.0000031f + 91.0f, Y * 0.0000031f - 44.0f);
        const float ClearingField = ValueNoise(X * 0.0000024f - 31.0f, Y * 0.0000024f + 72.0f);

        float Density = FMath::Clamp(
            0.12f + MacroBiome * 0.26f + ForestDetail * 0.24f + MoistureField * 0.20f,
            0.10f, 0.78f);
        if (ClearingField < 0.18f)
        {
            Density *= 0.18f;
        }
        else if (ClearingField < 0.29f)
        {
            Density *= 0.58f;
        }

        if (Random.FRand() <= Density && TryAddTree(X, Y, Random, OccupiedTreeCells))
        {
            ++AcceptedTrees;
        }
    }
}

bool AAetherBiomeScatterActor::TryAddTree(
    const float X, const float Y, FRandomStream& Random, TSet<uint64>& OccupiedCells)
{
    if (IsInsideRunwayClearance(X, Y))
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
    const float Moisture = ValueNoise(X * 0.0000046f + 91.0f, Y * 0.0000046f - 44.0f);
    const float Exposure = ValueNoise(X * 0.0000097f - 15.0f, Y * 0.0000097f + 63.0f);
    const float MacroBiome = ValueNoise(X * 0.00000125f + 17.0f, Y * 0.00000125f - 53.0f);
    const float Warmth = FMath::Clamp(
        1.0f - HeightMeters / 2200.0f + (MacroBiome - 0.5f) * 0.45f,
        0.0f, 1.0f);
    if (HeightMeters < 12.0f || HeightMeters > 2100.0f || Slope > 0.38f || Exposure < 0.12f)
    {
        return false;
    }

    AetherEnvironment::EBiomeType Biome = AetherEnvironment::EBiomeType::Boreal;
    if (HeightMeters > 1250.0f || Warmth < 0.34f)
    {
        Biome = AetherEnvironment::EBiomeType::Alpine;
    }
    else if (HeightMeters < 560.0f && Warmth > 0.61f && MacroBiome > 0.46f)
    {
        Biome = AetherEnvironment::EBiomeType::Coastal;
    }
    else if (Moisture > 0.61f && MacroBiome < 0.67f)
    {
        Biome = AetherEnvironment::EBiomeType::AspenValley;
    }
    else if (Warmth > 0.54f && Moisture < 0.56f)
    {
        Biome = AetherEnvironment::EBiomeType::DryWoodland;
    }

    UHierarchicalInstancedStaticMeshComponent* Target = nullptr;
    const float SpeciesRoll = Random.FRand();
    switch (Biome)
    {
    case AetherEnvironment::EBiomeType::Alpine:
        Target = SpeciesRoll < 0.72f ? ConiferPrimary : ConiferSecondary;
        break;
    case AetherEnvironment::EBiomeType::AspenValley:
        Target = SpeciesRoll < 0.58f
            ? BroadleafTrees
            : (SpeciesRoll < 0.83f ? ConiferSecondary : CorkOakTrees);
        break;
    case AetherEnvironment::EBiomeType::DryWoodland:
        Target = SpeciesRoll < 0.58f
            ? CorkOakTrees
            : (SpeciesRoll < 0.78f ? BroadleafTrees : ConiferPrimary);
        break;
    case AetherEnvironment::EBiomeType::Coastal:
        Target = SpeciesRoll < 0.44f
            ? CoconutPalms
            : (SpeciesRoll < 0.78f ? WindmillPalms
                : (SpeciesRoll < 0.91f ? CorkOakTrees : BroadleafTrees));
        break;
    default:
        Target = SpeciesRoll < 0.34f
            ? ConiferPrimary
            : (SpeciesRoll < 0.61f ? ConiferSecondary
                : (SpeciesRoll < 0.82f ? BroadleafTrees : CorkOakTrees));
        break;
    }

    if (!Target || !Target->GetStaticMesh())
    {
        TArray<UHierarchicalInstancedStaticMeshComponent*> AvailableTrees;
        for (UHierarchicalInstancedStaticMeshComponent* TreeComponent : GetTreeComponents())
        {
            if (TreeComponent->GetStaticMesh())
            {
                AvailableTrees.Add(TreeComponent);
            }
        }
        if (AvailableTrees.Num() == 0)
        {
            return false;
        }
        Target = AvailableTrees[Random.RandRange(0, AvailableTrees.Num() - 1)];
    }

    if (!ReserveCell(OccupiedCells, X, Y, AetherEnvironment::TreeCellSizeCm))
    {
        return false;
    }

    float MinScale = 0.72f;
    float MaxScale = 1.42f;
    if (Biome == AetherEnvironment::EBiomeType::Alpine)
    {
        MinScale = 0.54f;
        MaxScale = 1.08f;
    }
    else if (Biome == AetherEnvironment::EBiomeType::DryWoodland)
    {
        MinScale = 0.68f;
        MaxScale = 1.22f;
    }

    const float UniformScale = Random.FRandRange(MinScale, MaxScale);
    float WidthScale = UniformScale * Random.FRandRange(0.84f, 1.14f);
    float HeightScale = UniformScale * Random.FRandRange(0.91f, 1.24f);
    if (Target == WindmillPalms || Target == CoconutPalms)
    {
        WidthScale *= Random.FRandRange(0.76f, 0.96f);
        HeightScale *= Random.FRandRange(1.08f, 1.34f);
    }

    const FRotator Rotation(
        Random.FRandRange(-1.5f, 1.5f),
        Random.FRandRange(-180.0f, 180.0f),
        Random.FRandRange(-1.5f, 1.5f));
    Target->AddInstance(FTransform(
        Rotation,
        FVector(X, Y, HeightMeters * 100.0f - Random.FRandRange(2.0f, 10.0f)),
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
    if (AvailableRockComponents.Num() == 0 || RockInstanceBudget <= 0)
    {
        return;
    }

    TSet<uint64> OccupiedSoloCells;
    TSet<uint64> OccupiedFormationCells;
    TSet<uint64> FormationCenterCells;
    int32 RockCount = GetRockInstanceCount();

    auto TryPlaceRock = [&](const float X, const float Y, const float MinScale,
                            const float MaxScale, const bool bFormationRock) -> bool
    {
        if (RockCount >= RockInstanceBudget || IsInsideRunwayClearance(X, Y))
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
        const float Exposure = ValueNoise(X * 0.0000063f - 14.0f, Y * 0.0000063f + 62.0f);
        const float Outcrop = ValueNoise(X * 0.0000027f + 39.0f, Y * 0.0000027f - 77.0f);
        if (HeightMeters < 10.0f || HeightMeters > 2450.0f)
        {
            return false;
        }

        if (!bFormationRock)
        {
            const float Density = FMath::Clamp(
                0.09f + Slope * 1.55f + Exposure * 0.22f + Outcrop * 0.28f,
                0.10f, 0.88f);
            if (Random.FRand() > Density)
            {
                return false;
            }
        }

        TSet<uint64>& OccupiedCells = bFormationRock ? OccupiedFormationCells : OccupiedSoloCells;
        const float CellSize = bFormationRock
            ? AetherEnvironment::RockCellSizeCm * 0.30f
            : AetherEnvironment::RockCellSizeCm;
        if (!ReserveCell(OccupiedCells, X, Y, CellSize))
        {
            return false;
        }

        UHierarchicalInstancedStaticMeshComponent* Target = AvailableRockComponents[
            Random.RandRange(0, AvailableRockComponents.Num() - 1)];
        const float BaseScale = Random.FRandRange(MinScale, MaxScale);
        FVector Scale(
            BaseScale * Random.FRandRange(0.72f, 1.36f),
            BaseScale * Random.FRandRange(0.72f, 1.32f),
            BaseScale * Random.FRandRange(0.62f, 1.24f));

        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        Rotation.Pitch += Random.FRandRange(-6.0f, 6.0f);
        Rotation.Roll += Random.FRandRange(-6.0f, 6.0f);
        const float BuryDepth = FMath::Lerp(8.0f, 150.0f, FMath::Clamp(BaseScale / 7.0f, 0.0f, 1.0f));
        Target->AddInstance(FTransform(
            Rotation,
            FVector(X, Y, HeightMeters * 100.0f - Random.FRandRange(BuryDepth * 0.45f, BuryDepth)),
            Scale), false);
        ++RockCount;
        return true;
    };

    // Most rocks are evenly dispersed singles. The size distribution strongly
    // favors small stones but still produces boulders and rare landmarks.
    const int32 SoloTarget = FMath::RoundToInt(RockInstanceBudget * 0.82f);
    const int32 SoloAttempts = RockInstanceBudget * 12;
    for (int32 Attempt = 0; Attempt < SoloAttempts && RockCount < SoloTarget; ++Attempt)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        const float SizeRoll = Random.FRand();
        if (SizeRoll < 0.52f)
        {
            TryPlaceRock(X, Y, 0.20f, 0.72f, false);
        }
        else if (SizeRoll < 0.86f)
        {
            TryPlaceRock(X, Y, 0.70f, 1.75f, false);
        }
        else if (SizeRoll < 0.975f)
        {
            TryPlaceRock(X, Y, 1.70f, 4.20f, false);
        }
        else
        {
            TryPlaceRock(X, Y, 4.50f, 8.50f, false);
        }
    }

    // Widely separated formations have one dominant boulder surrounded by
    // irregular satellites. They read as geological features, not asset patches.
    const int32 FormationTarget = FMath::Clamp(RockInstanceBudget / 70, 18, 140);
    int32 FormationsPlaced = 0;
    for (int32 Attempt = 0; Attempt < FormationTarget * 12
        && FormationsPlaced < FormationTarget && RockCount < RockInstanceBudget; ++Attempt)
    {
        const float CenterX = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float CenterY = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (!ReserveCell(FormationCenterCells, CenterX, CenterY, 32000.0f)
            || !TryPlaceRock(CenterX, CenterY, 2.40f, 6.80f, true))
        {
            continue;
        }

        ++FormationsPlaced;
        const int32 SatelliteCount = Random.RandRange(3, 9);
        const float FormationRadius = Random.FRandRange(1400.0f, 9200.0f);
        for (int32 Satellite = 0; Satellite < SatelliteCount && RockCount < RockInstanceBudget; ++Satellite)
        {
            const float Angle = Random.FRandRange(0.0f, 2.0f * PI);
            const float Distance = FMath::Sqrt(Random.FRand()) * FormationRadius;
            const float RockX = CenterX + FMath::Cos(Angle) * Distance;
            const float RockY = CenterY + FMath::Sin(Angle) * Distance;
            if (RockX <= Bounds.Min.X || RockX >= Bounds.Max.X
                || RockY <= Bounds.Min.Y || RockY >= Bounds.Max.Y)
            {
                continue;
            }

            if (Random.FRand() < 0.70f)
            {
                TryPlaceRock(RockX, RockY, 0.24f, 1.35f, true);
            }
            else
            {
                TryPlaceRock(RockX, RockY, 1.20f, 3.20f, true);
            }
        }
    }
}

void AAetherBiomeScatterActor::DisableLegacyScatterIfReplaced()
{
    const bool bHasTrees = GetTreeInstanceCount() > 0;
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
