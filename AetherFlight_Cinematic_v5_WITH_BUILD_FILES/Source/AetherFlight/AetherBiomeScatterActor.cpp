#include "AetherBiomeScatterActor.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
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
    constexpr float RockCellSizeCm = 6500.0f;
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

    ConiferPrimary = CreateScatterComponent(TEXT("ConiferPrimary"), 450000, 1600000);
    ConiferSecondary = CreateScatterComponent(TEXT("ConiferSecondary"), 450000, 1600000);
    BroadleafTrees = CreateScatterComponent(TEXT("BroadleafTrees"), 400000, 1450000);
    CorkOakTrees = CreateScatterComponent(TEXT("CorkOakTrees"), 400000, 1450000);
    WindmillPalms = CreateScatterComponent(TEXT("WindmillPalms"), 350000, 1300000);
    CoconutPalms = CreateScatterComponent(TEXT("CoconutPalms"), 350000, 1300000);
    Shrubs = CreateScatterComponent(TEXT("Shrubs"), 70000, 320000);
    GroundCover = CreateScatterComponent(TEXT("GroundCover"), 35000, 160000);
    GroundCover->SetCastShadow(false);
    BoulderPrimary = CreateScatterComponent(TEXT("BoulderPrimary"), 260000, 950000);
    BoulderSecondary = CreateScatterComponent(TEXT("BoulderSecondary"), 300000, 1100000);
    BoulderVariant3 = CreateScatterComponent(TEXT("BoulderVariant3"), 240000, 900000);
    BoulderVariant4 = CreateScatterComponent(TEXT("BoulderVariant4"), 240000, 900000);
    BoulderVariant5 = CreateScatterComponent(TEXT("BoulderVariant5"), 240000, 900000);
    BoulderVariant6 = CreateScatterComponent(TEXT("BoulderVariant6"), 240000, 900000);
    BoulderVariant7 = CreateScatterComponent(TEXT("BoulderVariant7"), 240000, 900000);
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
    Component->bEnableDensityScaling = true;
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
    GetWorldTimerManager().ClearTimer(ScatterStreamTimer);
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
    GeneratedChunks.Reset();
    OccupiedTreeCells.Reset();
    OccupiedSoloRockCells.Reset();
    OccupiedFormationRockCells.Reset();
    CachedLandscapeBounds = FBox2D();
    BuildAttempt = 0;
    StreamUpdateCount = 0;
    bLandscapeBoundsReady = false;
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

UStaticMesh* AAetherBiomeScatterActor::LoadFirstMeshMatchingKeywords(
    const TArray<FName>& PackagePaths, const TArray<FString>& Keywords) const
{
    if (PackagePaths.Num() == 0 || Keywords.Num() == 0)
    {
        return nullptr;
    }

    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    FARFilter Filter;
    Filter.PackagePaths.Append(PackagePaths);
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
        const FString AssetName = Asset.AssetName.ToString();
        bool bMatches = false;
        for (const FString& Keyword : Keywords)
        {
            if (AssetName.Contains(Keyword, ESearchCase::IgnoreCase))
            {
                bMatches = true;
                break;
            }
        }

        if (bMatches)
        {
            if (UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset()))
            {
                return Mesh;
            }
        }
    }
    return nullptr;
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

    // Automatically use installed high-quality plant meshes when explicit
    // Aether aliases have not been created.
    if (!Shrub)
    {
        Shrub = LoadFirstMeshMatchingKeywords({
            FName(TEXT("/Game/Aether/Environment/Foliage")),
            FName(TEXT("/Game/DZ_Assets"))
        }, { TEXT("shrub"), TEXT("bush"), TEXT("sapling") });
    }
    if (!Cover)
    {
        Cover = LoadFirstMeshMatchingKeywords({
            FName(TEXT("/Game/Aether/Environment/Foliage")),
            FName(TEXT("/Game/DZ_Assets"))
        }, { TEXT("fern"), TEXT("groundcover"), TEXT("ground_cover"), TEXT("grass"), TEXT("flower") });
    }

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

    // A partially streamed Landscape can report only one proxy at startup.
    // Preserve the known production-world extent so chunks across the entire
    // 4033 landscape become eligible as the aircraft approaches them.
    const float MinimumExpectedSize = AetherEnvironment::DefaultHalfWorldCm * 1.5f;
    if (Bounds.GetSize().X < MinimumExpectedSize || Bounds.GetSize().Y < MinimumExpectedSize)
    {
        Bounds.Min.X = FMath::Min(Bounds.Min.X, -AetherEnvironment::DefaultHalfWorldCm);
        Bounds.Min.Y = FMath::Min(Bounds.Min.Y, -AetherEnvironment::DefaultHalfWorldCm);
        Bounds.Max.X = FMath::Max(Bounds.Max.X, AetherEnvironment::DefaultHalfWorldCm);
        Bounds.Max.Y = FMath::Max(Bounds.Max.Y, AetherEnvironment::DefaultHalfWorldCm);
    }

    Bounds.Min += FVector2D(AetherEnvironment::LandscapeBorderCm);
    Bounds.Max -= FVector2D(AetherEnvironment::LandscapeBorderCm);
    if (Bounds.Min.X >= Bounds.Max.X || Bounds.Min.Y >= Bounds.Max.Y)
    {
        UE_LOG(LogTemp, Warning, TEXT("[Aether] Invalid production Landscape bounds; ecosystem streaming was not started."));
        return;
    }

    CachedLandscapeBounds = Bounds;
    bLandscapeBoundsReady = true;
    bBuilt = true;

    StreamEnvironmentAroundPlayer();
    GetWorldTimerManager().SetTimer(
        ScatterStreamTimer,
        this,
        &AAetherBiomeScatterActor::StreamEnvironmentAroundPlayer,
        StreamingUpdateSeconds,
        true);

    UE_LOG(LogTemp, Display,
        TEXT("[Aether] Ecosystem streaming initialized across %.1f x %.1f km; %d tree and %d rock maximum."),
        Bounds.GetSize().X * 0.00001f,
        Bounds.GetSize().Y * 0.00001f,
        TreeInstanceBudget,
        RockInstanceBudget);
}

bool AAetherBiomeScatterActor::FindLandscapeBounds(FBox2D& OutBounds) const
{
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

        const FBox2D ProxyBounds(
            FVector2D(Box.Min.X, Box.Min.Y),
            FVector2D(Box.Max.X, Box.Max.Y));
        if (!bFound)
        {
            OutBounds = ProxyBounds;
            bFound = true;
        }
        else
        {
            OutBounds.Min.X = FMath::Min(OutBounds.Min.X, ProxyBounds.Min.X);
            OutBounds.Min.Y = FMath::Min(OutBounds.Min.Y, ProxyBounds.Min.Y);
            OutBounds.Max.X = FMath::Max(OutBounds.Max.X, ProxyBounds.Max.X);
            OutBounds.Max.Y = FMath::Max(OutBounds.Max.Y, ProxyBounds.Max.Y);
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
    const FVector2D FullSize = CachedLandscapeBounds.GetSize();
    const FVector2D LocalSize = Bounds.GetSize();
    const double FullArea = FMath::Max(
        1.0, static_cast<double>(FullSize.X) * static_cast<double>(FullSize.Y));
    const double LocalArea = FMath::Max(
        1.0, static_cast<double>(LocalSize.X) * static_cast<double>(LocalSize.Y));
    const int32 LocalBudget = FMath::Clamp(
        FMath::RoundToInt(TreeInstanceBudget * LocalArea / FullArea),
        12, 1200);
    const int32 StartCount = GetTreeInstanceCount();
    const int32 TargetCount = FMath::Min(TreeInstanceBudget, StartCount + LocalBudget);
    const int32 Attempts = LocalBudget * 14;
    int32 AcceptedTrees = StartCount;
    for (int32 Attempt = 0; Attempt < Attempts && AcceptedTrees < TargetCount; ++Attempt)
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
    if (Shrubs->GetStaticMesh() && Shrubs->GetInstanceCount() < ShrubInstanceBudget && Random.FRand() < 0.18f)
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
        && Random.FRand() < 0.28f)
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

    const FVector2D FullSize = CachedLandscapeBounds.GetSize();
    const FVector2D LocalSize = Bounds.GetSize();
    const double FullArea = FMath::Max(
        1.0, static_cast<double>(FullSize.X) * static_cast<double>(FullSize.Y));
    const double LocalArea = FMath::Max(
        1.0, static_cast<double>(LocalSize.X) * static_cast<double>(LocalSize.Y));
    const int32 LocalBudget = FMath::Clamp(
        FMath::RoundToInt(RockInstanceBudget * LocalArea / FullArea),
        2, 32);
    int32 RockCount = GetRockInstanceCount();
    const int32 LocalTargetCount = FMath::Min(RockInstanceBudget, RockCount + LocalBudget);
    if (RockCount >= LocalTargetCount)
    {
        return;
    }

    auto TryPlaceRock = [&](const float X, const float Y, const float MinScale,
                            const float MaxScale, const bool bFormationRock) -> bool
    {
        if (RockCount >= LocalTargetCount || IsInsideRunwayClearance(X, Y))
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
                0.04f + Slope * 1.05f + Exposure * 0.14f + Outcrop * 0.16f,
                0.06f, 0.58f);
            if (Random.FRand() > Density)
            {
                return false;
            }
        }

        TSet<uint64>& OccupiedCells =
            bFormationRock ? OccupiedFormationRockCells : OccupiedSoloRockCells;
        const float CellSize = bFormationRock
            ? AetherEnvironment::RockCellSizeCm * 0.28f
            : AetherEnvironment::RockCellSizeCm;
        if (!ReserveCell(OccupiedCells, X, Y, CellSize))
        {
            return false;
        }

        UHierarchicalInstancedStaticMeshComponent* Target = AvailableRockComponents[
            Random.RandRange(0, AvailableRockComponents.Num() - 1)];
        const float BaseScale = Random.FRandRange(MinScale, MaxScale);
        const FVector Scale(
            BaseScale * Random.FRandRange(0.78f, 1.28f),
            BaseScale * Random.FRandRange(0.78f, 1.25f),
            BaseScale * Random.FRandRange(0.68f, 1.18f));

        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        Rotation.Pitch += Random.FRandRange(-5.0f, 5.0f);
        Rotation.Roll += Random.FRandRange(-5.0f, 5.0f);
        const float BuryDepth = FMath::Lerp(
            8.0f, 130.0f, FMath::Clamp(BaseScale / 6.5f, 0.0f, 1.0f));
        Target->AddInstance(FTransform(
            Rotation,
            FVector(X, Y, HeightMeters * 100.0f - Random.FRandRange(BuryDepth * 0.45f, BuryDepth)),
            Scale), false);
        ++RockCount;
        return true;
    };

    // Only a minority of chunks contain a formation. Each formation has one
    // dominant rock and a few satellites, preventing wall-to-wall boulders.
    if (LocalBudget >= 4 && Random.FRand() < 0.16f)
    {
        for (int32 FormationAttempt = 0; FormationAttempt < 12 && RockCount < LocalTargetCount; ++FormationAttempt)
        {
            const float CenterX = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
            const float CenterY = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
            if (!TryPlaceRock(CenterX, CenterY, 1.80f, 4.80f, true))
            {
                continue;
            }

            const int32 SatelliteCount = FMath::Min(
                Random.RandRange(2, 5), LocalTargetCount - RockCount);
            const float Radius = Random.FRandRange(1800.0f, 7600.0f);
            for (int32 Satellite = 0; Satellite < SatelliteCount; ++Satellite)
            {
                const float Angle = Random.FRandRange(0.0f, 2.0f * PI);
                const float Distance = FMath::Sqrt(Random.FRand()) * Radius;
                TryPlaceRock(
                    CenterX + FMath::Cos(Angle) * Distance,
                    CenterY + FMath::Sin(Angle) * Distance,
                    0.22f,
                    Random.FRand() < 0.78f ? 1.10f : 2.20f,
                    true);
            }
            break;
        }
    }

    const int32 Attempts = LocalBudget * 36;
    for (int32 Attempt = 0; Attempt < Attempts && RockCount < LocalTargetCount; ++Attempt)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        const float SizeRoll = Random.FRand();
        if (SizeRoll < 0.64f)
        {
            TryPlaceRock(X, Y, 0.18f, 0.58f, false);
        }
        else if (SizeRoll < 0.92f)
        {
            TryPlaceRock(X, Y, 0.58f, 1.35f, false);
        }
        else if (SizeRoll < 0.992f)
        {
            TryPlaceRock(X, Y, 1.35f, 3.10f, false);
        }
        else
        {
            TryPlaceRock(X, Y, 3.40f, 6.40f, false);
        }
    }
}

bool AAetherBiomeScatterActor::IsChunkLandscapeReady(const FBox2D& Bounds) const
{
    const FVector2D Size = Bounds.GetSize();
    const FVector2D Inset = Size * 0.18f;
    const TArray<FVector2D> ProbePoints = {
        Bounds.GetCenter(),
        Bounds.Min + Inset,
        FVector2D(Bounds.Max.X - Inset.X, Bounds.Min.Y + Inset.Y),
        Bounds.Max - Inset,
        FVector2D(Bounds.Min.X + Inset.X, Bounds.Max.Y - Inset.Y)
    };

    int32 SuccessfulProbes = 0;
    for (const FVector2D& Point : ProbePoints)
    {
        float HeightMeters = 0.0f;
        FVector Normal = FVector::UpVector;
        if (SampleLandscape(Point.X, Point.Y, HeightMeters, Normal))
        {
            ++SuccessfulProbes;
        }
    }
    return SuccessfulProbes >= 3;
}

void AAetherBiomeScatterActor::StreamEnvironmentAroundPlayer()
{
    if (!bBuilt || !bLandscapeBoundsReady || !GetWorld())
    {
        return;
    }

    FVector FocusLocation = GetActorLocation();
    if (const APlayerController* PlayerController = GetWorld()->GetFirstPlayerController())
    {
        if (const APawn* PlayerPawn = PlayerController->GetPawn())
        {
            FocusLocation = PlayerPawn->GetActorLocation();
        }
    }

    const float ChunkSize = FMath::Max(100000.0f, EcosystemChunkSizeCm);
    const FIntPoint CenterChunk(
        FMath::FloorToInt(FocusLocation.X / ChunkSize),
        FMath::FloorToInt(FocusLocation.Y / ChunkSize));

    TArray<FIntPoint> PendingChunks;
    const int32 Radius = FMath::Max(1, StreamingRadiusInChunks);
    for (int32 OffsetY = -Radius; OffsetY <= Radius; ++OffsetY)
    {
        for (int32 OffsetX = -Radius; OffsetX <= Radius; ++OffsetX)
        {
            if (OffsetX * OffsetX + OffsetY * OffsetY > Radius * Radius)
            {
                continue;
            }

            const FIntPoint Chunk(CenterChunk.X + OffsetX, CenterChunk.Y + OffsetY);
            if (!GeneratedChunks.Contains(Chunk))
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

    const int32 ChunkLimit = GeneratedChunks.Num() == 0
        ? FMath::Max(MaxNewChunksPerUpdate, 16)
        : FMath::Max(1, MaxNewChunksPerUpdate);
    int32 NewChunks = 0;
    for (const FIntPoint& Chunk : PendingChunks)
    {
        FBox2D ChunkBounds(
            FVector2D(Chunk.X * ChunkSize, Chunk.Y * ChunkSize),
            FVector2D((Chunk.X + 1) * ChunkSize, (Chunk.Y + 1) * ChunkSize));
        ChunkBounds.Min.X = FMath::Max(ChunkBounds.Min.X, CachedLandscapeBounds.Min.X);
        ChunkBounds.Min.Y = FMath::Max(ChunkBounds.Min.Y, CachedLandscapeBounds.Min.Y);
        ChunkBounds.Max.X = FMath::Min(ChunkBounds.Max.X, CachedLandscapeBounds.Max.X);
        ChunkBounds.Max.Y = FMath::Min(ChunkBounds.Max.Y, CachedLandscapeBounds.Max.Y);
        if (ChunkBounds.Min.X >= ChunkBounds.Max.X || ChunkBounds.Min.Y >= ChunkBounds.Max.Y)
        {
            GeneratedChunks.Add(Chunk);
            continue;
        }

        if (!IsChunkLandscapeReady(ChunkBounds))
        {
            continue;
        }

        const uint32 ChunkHash =
            static_cast<uint32>(Chunk.X) * 73856093u
            ^ static_cast<uint32>(Chunk.Y) * 19349663u
            ^ static_cast<uint32>(EnvironmentSeed) * 83492791u;
        FRandomStream ChunkRandom(static_cast<int32>(ChunkHash));
        GenerateForest(ChunkBounds, ChunkRandom);
        GenerateRocks(ChunkBounds, ChunkRandom);
        GeneratedChunks.Add(Chunk);
        ++NewChunks;
        if (NewChunks >= ChunkLimit)
        {
            break;
        }
    }

    ++StreamUpdateCount;
    if (NewChunks > 0)
    {
        DisableLegacyScatterIfReplaced();
        if (GeneratedChunks.Num() <= NewChunks || StreamUpdateCount % 12 == 0)
        {
            UE_LOG(LogTemp, Display,
                TEXT("[Aether] Streamed %d ecosystem chunks: %d trees, %d foliage plants, %d rocks resident."),
                GeneratedChunks.Num(),
                GetTreeInstanceCount(),
                Shrubs->GetInstanceCount() + GroundCover->GetInstanceCount(),
                GetRockInstanceCount());
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
