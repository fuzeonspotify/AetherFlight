#include "AetherEnhancedEnvironmentActor.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Modules/ModuleManager.h"
#include "UObject/UObjectGlobals.h"

namespace AetherEnhancedEnvironment
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
    constexpr float HalfWorldCm = 2400000.0f;
    constexpr float WorldInsetCm = 12000.0f;
    constexpr int32 MaximumPrepareAttempts = 20;

    bool IsRejectedRockPath(const FString& LowerPath)
    {
        return LowerPath.Contains(TEXT("/pcg/"))
            || LowerPath.Contains(TEXT("mediaplate"))
            || LowerPath.Contains(TEXT("icon"))
            || LowerPath.Contains(TEXT("collision"))
            || LowerPath.Contains(TEXT("proxy"))
            || LowerPath.Contains(TEXT("billboard"))
            || LowerPath.Contains(TEXT("overview"))
            || LowerPath.Contains(TEXT("showcase"))
            || LowerPath.Contains(TEXT("example"))
            || LowerPath.Contains(TEXT("_lod"))
            || LowerPath.Contains(TEXT("lod_"));
    }
}

AAetherEnhancedEnvironmentActor::AAetherEnhancedEnvironmentActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    NaniteTreeA = CreateScatterComponent(TEXT("NaniteSampleTreeA"), 900000);
    NaniteTreeB = CreateScatterComponent(TEXT("NaniteSampleTreeB"), 900000);
    AbeliaShrubs = CreateScatterComponent(TEXT("NaniteAbeliaShrubs"), 320000);
    LoliumGrass = CreateScatterComponent(TEXT("NaniteLoliumGrass"), 220000);
    OphiopogonGroundCover = CreateScatterComponent(TEXT("NaniteOphiopogonGroundCover"), 200000);

    RockVariant01 = CreateScatterComponent(TEXT("RockCollection04Variant01"), 900000);
    RockVariant02 = CreateScatterComponent(TEXT("RockCollection04Variant02"), 900000);
    RockVariant03 = CreateScatterComponent(TEXT("RockCollection04Variant03"), 900000);
    RockVariant04 = CreateScatterComponent(TEXT("RockCollection04Variant04"), 900000);
    RockVariant05 = CreateScatterComponent(TEXT("RockCollection04Variant05"), 900000);
    RockVariant06 = CreateScatterComponent(TEXT("RockCollection04Variant06"), 900000);
    RockVariant07 = CreateScatterComponent(TEXT("RockCollection04Variant07"), 900000);
}

UHierarchicalInstancedStaticMeshComponent*
AAetherEnhancedEnvironmentActor::CreateScatterComponent(
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

TArray<UHierarchicalInstancedStaticMeshComponent*>
AAetherEnhancedEnvironmentActor::RockComponents() const
{
    return {
        RockVariant01,
        RockVariant02,
        RockVariant03,
        RockVariant04,
        RockVariant05,
        RockVariant06,
        RockVariant07,
    };
}

void AAetherEnhancedEnvironmentActor::BeginPlay()
{
    Super::BeginPlay();
    if (!GetWorld())
    {
        return;
    }

    GetWorldTimerManager().SetTimer(
        PrepareTimer,
        this,
        &AAetherEnhancedEnvironmentActor::PrepareEnvironment,
        7.0f,
        false);
}

bool AAetherEnhancedEnvironmentActor::LoadPlantAssets()
{
    NaniteTreeA->SetStaticMesh(LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_02_002_Free.SM_3DGardenPlants_Acer_buergerianum_02_002_Free")));
    NaniteTreeB->SetStaticMesh(LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_01_003_Free.SM_3DGardenPlants_Acer_buergerianum_01_003_Free")));
    AbeliaShrubs->SetStaticMesh(LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Abelia_x_grandiflora_Nanite_Free_Sample.SM_Abelia_x_grandiflora_Nanite_Free_Sample")));
    LoliumGrass->SetStaticMesh(LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Lolium_perenne_3DGardenPlants.SM_Free_Lolium_perenne_3DGardenPlants")));
    OphiopogonGroundCover->SetStaticMesh(LoadObject<UStaticMesh>(
        nullptr,
        TEXT("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants.SM_Free_Ophiopogon_japonicus_3DGardenPlants")));

    const bool bLoaded = NaniteTreeA->GetStaticMesh()
        && NaniteTreeB->GetStaticMesh()
        && AbeliaShrubs->GetStaticMesh()
        && LoliumGrass->GetStaticMesh()
        && OphiopogonGroundCover->GetStaticMesh();

    UE_LOG(
        LogTemp,
        bLoaded ? Display : Error,
        TEXT("[Aether Enhanced Environment] Nanite sample assets: treeA=%s treeB=%s shrub=%s grass=%s ground=%s."),
        NaniteTreeA->GetStaticMesh() ? *NaniteTreeA->GetStaticMesh()->GetPathName() : TEXT("None"),
        NaniteTreeB->GetStaticMesh() ? *NaniteTreeB->GetStaticMesh()->GetPathName() : TEXT("None"),
        AbeliaShrubs->GetStaticMesh() ? *AbeliaShrubs->GetStaticMesh()->GetPathName() : TEXT("None"),
        LoliumGrass->GetStaticMesh() ? *LoliumGrass->GetStaticMesh()->GetPathName() : TEXT("None"),
        OphiopogonGroundCover->GetStaticMesh() ? *OphiopogonGroundCover->GetStaticMesh()->GetPathName() : TEXT("None"));

    return bLoaded;
}

int32 AAetherEnhancedEnvironmentActor::DiscoverAndAssignRockCollection()
{
    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    IAssetRegistry& Registry = AssetRegistryModule.Get();
    Registry.SearchAllAssets(true);

    FARFilter Filter;
    Filter.PackagePaths.Add(FName(TEXT("/Game")));
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;
    Filter.bRecursiveClasses = true;

    TArray<FAssetData> Assets;
    Registry.GetAssets(Filter, Assets);

    TMap<FString, TArray<FAssetData>> Groups;
    for (const FAssetData& Asset : Assets)
    {
        const FString ObjectPath = Asset.GetSoftObjectPath().ToString();
        const FString LowerPath = ObjectPath.ToLower();
        if (!LowerPath.Contains(TEXT("rock"))
            || AetherEnhancedEnvironment::IsRejectedRockPath(LowerPath))
        {
            continue;
        }

        TArray<FString> Segments;
        ObjectPath.ParseIntoArray(Segments, TEXT("/"), true);
        if (Segments.Num() < 2 || !Segments[0].Equals(TEXT("Game")))
        {
            continue;
        }

        const FString RootFolder = FString::Printf(TEXT("/Game/%s"), *Segments[1]);
        Groups.FindOrAdd(RootFolder).Add(Asset);
    }

    FString BestRoot;
    TArray<FAssetData> BestAssets;
    int32 BestScore = MIN_int32;

    for (const TPair<FString, TArray<FAssetData>>& Pair : Groups)
    {
        if (Pair.Value.Num() < 7)
        {
            continue;
        }

        const FString LowerRoot = Pair.Key.ToLower();
        int32 Score = Pair.Value.Num() * 10;
        Score += LowerRoot.Contains(TEXT("rock")) ? 400 : 0;
        Score += LowerRoot.Contains(TEXT("04")) ? 300 : 0;
        Score += LowerRoot.Contains(TEXT("collection")) ? 200 : 0;
        Score += LowerRoot.Contains(TEXT("environment")) ? 100 : 0;
        Score += LowerRoot.Contains(TEXT("shadowmire")) ? 100 : 0;

        for (const FAssetData& Asset : Pair.Value)
        {
            const FString LowerPath = Asset.GetSoftObjectPath().ToString().ToLower();
            Score += LowerPath.Contains(TEXT("rock")) ? 8 : 0;
            Score += LowerPath.Contains(TEXT("04")) ? 6 : 0;
        }

        if (Score > BestScore)
        {
            BestScore = Score;
            BestRoot = Pair.Key;
            BestAssets = Pair.Value;
        }
    }

    BestAssets.Sort([](const FAssetData& Left, const FAssetData& Right)
    {
        return Left.AssetName.ToString() < Right.AssetName.ToString();
    });

    const TArray<UHierarchicalInstancedStaticMeshComponent*> Components = RockComponents();
    int32 Assigned = 0;
    for (int32 Index = 0;
         Index < Components.Num() && Index < BestAssets.Num();
         ++Index)
    {
        UStaticMesh* Mesh = Cast<UStaticMesh>(BestAssets[Index].GetAsset());
        if (!Mesh)
        {
            continue;
        }

        Components[Index]->SetStaticMesh(Mesh);
        ++Assigned;
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[Aether Enhanced Environment] Rock Collection 04 variant %d=%s"),
            Index + 1,
            *Mesh->GetPathName());
    }

    if (Assigned != 7)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("[Aether Enhanced Environment] Expected all 7 Rock Collection 04 meshes but assigned %d. Selected root=%s candidates=%d."),
            Assigned,
            BestRoot.IsEmpty() ? TEXT("None") : *BestRoot,
            BestAssets.Num());
    }
    else
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[Aether Enhanced Environment] ALL 7 ROCK COLLECTION 04 VARIANTS LOADED from %s."),
            *BestRoot);
    }

    return Assigned;
}

bool AAetherEnhancedEnvironmentActor::LooksLikeWater(const FHitResult& Hit) const
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

bool AAetherEnhancedEnvironmentActor::TraceTerrain(
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
    FCollisionQueryParams Parameters(
        SCENE_QUERY_STAT(AetherEnhancedEnvironmentTrace),
        false,
        this);
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Parameters.AddIgnoredActor(Controller->GetPawn());
    }

    if (!GetWorld()->LineTraceSingleByChannel(
            Hit,
            FVector(X, Y, AetherEnhancedEnvironment::TraceTopCm),
            FVector(X, Y, AetherEnhancedEnvironment::TraceBottomCm),
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

FBox2D AAetherEnhancedEnvironmentActor::ChunkBounds(const FIntPoint& Chunk) const
{
    FBox2D Bounds(
        FVector2D(Chunk.X * ChunkSizeCm, Chunk.Y * ChunkSizeCm),
        FVector2D((Chunk.X + 1) * ChunkSizeCm, (Chunk.Y + 1) * ChunkSizeCm));

    const float Minimum = -AetherEnhancedEnvironment::HalfWorldCm
        + AetherEnhancedEnvironment::WorldInsetCm;
    const float Maximum = AetherEnhancedEnvironment::HalfWorldCm
        - AetherEnhancedEnvironment::WorldInsetCm;
    Bounds.Min.X = FMath::Max(Bounds.Min.X, Minimum);
    Bounds.Min.Y = FMath::Max(Bounds.Min.Y, Minimum);
    Bounds.Max.X = FMath::Min(Bounds.Max.X, Maximum);
    Bounds.Max.Y = FMath::Min(Bounds.Max.Y, Maximum);
    return Bounds;
}

bool AAetherEnhancedEnvironmentActor::IsInsideWorld(const FIntPoint& Chunk) const
{
    const FBox2D Bounds = ChunkBounds(Chunk);
    return Bounds.Min.X < Bounds.Max.X && Bounds.Min.Y < Bounds.Max.Y;
}

bool AAetherEnhancedEnvironmentActor::IsTerrainReady(const FBox2D& Bounds) const
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

FVector AAetherEnhancedEnvironmentActor::FocusLocation() const
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

float AAetherEnhancedEnvironmentActor::ScaleForHeight(
    const UStaticMesh* Mesh,
    const float DesiredHeightCm) const
{
    if (!Mesh)
    {
        return 1.0f;
    }

    const float MeshHeightCm = FMath::Max(
        25.0f,
        Mesh->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / MeshHeightCm, 0.16f, 5.0f);
}

bool AAetherEnhancedEnvironmentActor::ReserveCell(
    TSet<uint64>& Cells,
    const float X,
    const float Y,
    const float CellSizeCm) const
{
    const int32 CellX = FMath::FloorToInt(X / CellSizeCm);
    const int32 CellY = FMath::FloorToInt(Y / CellSizeCm);
    const uint64 Key =
        (static_cast<uint64>(static_cast<uint32>(CellX)) << 32u)
        | static_cast<uint32>(CellY);
    if (Cells.Contains(Key))
    {
        return false;
    }
    Cells.Add(Key);
    return true;
}

int32 AAetherEnhancedEnvironmentActor::ScatterPlants(
    UHierarchicalInstancedStaticMeshComponent* Component,
    FRandomStream& Random,
    const FBox2D& Bounds,
    const int32 CandidateCount,
    const float MinimumNormalZ,
    const float MinimumHeightMeters,
    const float MaximumHeightMeters,
    const float MinimumDesiredHeightCm,
    const float MaximumDesiredHeightCm,
    const float CellSizeCm,
    TSet<uint64>& ReservedCells,
    const bool bAlignToSurface)
{
    if (!Component || !Component->GetStaticMesh())
    {
        return 0;
    }

    int32 Added = 0;
    for (int32 Candidate = 0; Candidate < CandidateCount; ++Candidate)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (!ReserveCell(ReservedCells, X, Y, CellSizeCm))
        {
            continue;
        }

        FVector Location;
        FVector Normal;
        if (!TraceTerrain(X, Y, Location, Normal)
            || Normal.Z < MinimumNormalZ)
        {
            continue;
        }

        const float HeightMeters = Location.Z * 0.01f;
        if (HeightMeters < MinimumHeightMeters
            || HeightMeters > MaximumHeightMeters)
        {
            continue;
        }

        const float DesiredHeightCm = Random.FRandRange(
            MinimumDesiredHeightCm,
            MaximumDesiredHeightCm);
        const float Scale = ScaleForHeight(Component->GetStaticMesh(), DesiredHeightCm);
        FRotator Rotation = bAlignToSurface
            ? FRotationMatrix::MakeFromZ(Normal).Rotator()
            : FRotator(
                Random.FRandRange(-1.0f, 1.0f),
                0.0f,
                Random.FRandRange(-1.0f, 1.0f));
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);

        const int32 InstanceIndex = Component->AddInstance(
            FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(0.5f, 4.0f)),
                FVector(
                    Scale * Random.FRandRange(0.88f, 1.14f),
                    Scale * Random.FRandRange(0.88f, 1.14f),
                    Scale * Random.FRandRange(0.90f, 1.18f))),
            true);
        if (InstanceIndex != INDEX_NONE)
        {
            ++Added;
        }
    }

    if (Added > 0)
    {
        Component->MarkRenderStateDirty();
    }
    return Added;
}

int32 AAetherEnhancedEnvironmentActor::ScatterRocks(
    FRandomStream& Random,
    const FBox2D& Bounds,
    const int32 CandidateCount,
    TSet<uint64>& ReservedCells)
{
    TArray<UHierarchicalInstancedStaticMeshComponent*> ActiveRockComponents;
    for (UHierarchicalInstancedStaticMeshComponent* Component : RockComponents())
    {
        if (Component && Component->GetStaticMesh())
        {
            ActiveRockComponents.Add(Component);
        }
    }

    if (ActiveRockComponents.Num() == 0)
    {
        return 0;
    }

    int32 Added = 0;
    for (int32 Candidate = 0; Candidate < CandidateCount; ++Candidate)
    {
        const float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
        const float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
        if (!ReserveCell(ReservedCells, X, Y, 2400.0f))
        {
            continue;
        }

        FVector Location;
        FVector Normal;
        if (!TraceTerrain(X, Y, Location, Normal) || Normal.Z < 0.24f)
        {
            continue;
        }

        UHierarchicalInstancedStaticMeshComponent* Target =
            ActiveRockComponents[Added % ActiveRockComponents.Num()];

        const int32 SizeTier = Added % 10;
        float DesiredHeightCm = 0.0f;
        if (SizeTier < 5)
        {
            DesiredHeightCm = Random.FRandRange(120.0f, 380.0f);
        }
        else if (SizeTier < 8)
        {
            DesiredHeightCm = Random.FRandRange(380.0f, 950.0f);
        }
        else
        {
            DesiredHeightCm = Random.FRandRange(950.0f, 2200.0f);
        }

        const float Scale = ScaleForHeight(Target->GetStaticMesh(), DesiredHeightCm);
        FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);
        Rotation.Pitch += Random.FRandRange(-9.0f, 9.0f);
        Rotation.Roll += Random.FRandRange(-9.0f, 9.0f);

        const float BurialCm = DesiredHeightCm * Random.FRandRange(0.08f, 0.22f);
        const int32 InstanceIndex = Target->AddInstance(
            FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, BurialCm),
                FVector(
                    Scale * Random.FRandRange(0.72f, 1.38f),
                    Scale * Random.FRandRange(0.72f, 1.38f),
                    Scale * Random.FRandRange(0.70f, 1.24f))),
            true);
        if (InstanceIndex != INDEX_NONE)
        {
            ++Added;
        }
    }

    for (UHierarchicalInstancedStaticMeshComponent* Component : ActiveRockComponents)
    {
        Component->MarkRenderStateDirty();
    }
    return Added;
}

void AAetherEnhancedEnvironmentActor::ClearInstances()
{
    NaniteTreeA->ClearInstances();
    NaniteTreeB->ClearInstances();
    AbeliaShrubs->ClearInstances();
    LoliumGrass->ClearInstances();
    OphiopogonGroundCover->ClearInstances();
    for (UHierarchicalInstancedStaticMeshComponent* Component : RockComponents())
    {
        Component->ClearInstances();
    }

    PendingChunks.Reset();
    GeneratedChunks.Reset();
    TotalNaniteTrees = 0;
    TotalShrubs = 0;
    TotalGrass = 0;
    TotalGroundCover = 0;
    TotalRocks = 0;
}

void AAetherEnhancedEnvironmentActor::BeginLocalRing(
    const FIntPoint& CenterChunk)
{
    ClearInstances();
    CurrentCenterChunk = CenterChunk;
    bHasCenterChunk = true;

    for (int32 OffsetY = -ActiveRadiusChunks;
         OffsetY <= ActiveRadiusChunks;
         ++OffsetY)
    {
        for (int32 OffsetX = -ActiveRadiusChunks;
             OffsetX <= ActiveRadiusChunks;
             ++OffsetX)
        {
            if (OffsetX * OffsetX + OffsetY * OffsetY
                > ActiveRadiusChunks * ActiveRadiusChunks)
            {
                continue;
            }

            const FIntPoint Chunk(
                CenterChunk.X + OffsetX,
                CenterChunk.Y + OffsetY);
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
        return LeftX * LeftX + LeftY * LeftY
            < RightX * RightX + RightY * RightY;
    });

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Enhanced Environment] Dense local ring centered on (%d,%d); %d chunks queued."),
        CenterChunk.X,
        CenterChunk.Y,
        PendingChunks.Num());
}

bool AAetherEnhancedEnvironmentActor::GenerateChunk(const FIntPoint& Chunk)
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
        ^ 4082604u;
    FRandomStream Random(static_cast<int32>(Hash));

    TSet<uint64> TreeCells;
    TSet<uint64> ShrubCells;
    TSet<uint64> GrassCells;
    TSet<uint64> GroundCells;
    TSet<uint64> RockCells;

    const int32 TreeAAdded = ScatterPlants(
        NaniteTreeA,
        Random,
        Bounds,
        NaniteTreesPerChunk / 2,
        0.62f,
        2.0f,
        4300.0f,
        420.0f,
        760.0f,
        1450.0f,
        TreeCells,
        false);
    const int32 TreeBAdded = ScatterPlants(
        NaniteTreeB,
        Random,
        Bounds,
        NaniteTreesPerChunk - NaniteTreesPerChunk / 2,
        0.62f,
        2.0f,
        4300.0f,
        450.0f,
        820.0f,
        1450.0f,
        TreeCells,
        false);
    const int32 ShrubsAdded = ScatterPlants(
        AbeliaShrubs,
        Random,
        Bounds,
        ShrubsPerChunk,
        0.64f,
        2.0f,
        4300.0f,
        85.0f,
        190.0f,
        620.0f,
        ShrubCells,
        true);
    const int32 GrassAdded = ScatterPlants(
        LoliumGrass,
        Random,
        Bounds,
        LoliumPerChunk,
        0.72f,
        2.0f,
        4300.0f,
        32.0f,
        78.0f,
        280.0f,
        GrassCells,
        true);
    const int32 GroundAdded = ScatterPlants(
        OphiopogonGroundCover,
        Random,
        Bounds,
        OphiopogonPerChunk,
        0.72f,
        2.0f,
        4300.0f,
        24.0f,
        58.0f,
        260.0f,
        GroundCells,
        true);
    const int32 RocksAdded = ScatterRocks(
        Random,
        Bounds,
        RocksPerChunk,
        RockCells);

    GeneratedChunks.Add(Chunk);
    TotalNaniteTrees += TreeAAdded + TreeBAdded;
    TotalShrubs += ShrubsAdded;
    TotalGrass += GrassAdded;
    TotalGroundCover += GroundAdded;
    TotalRocks += RocksAdded;

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Enhanced Environment] Chunk (%d,%d): naniteTrees=%d shrubs=%d grass=%d ground=%d rocks=%d. Ring=%d/%d/%d/%d/%d."),
        Chunk.X,
        Chunk.Y,
        TreeAAdded + TreeBAdded,
        ShrubsAdded,
        GrassAdded,
        GroundAdded,
        RocksAdded,
        TotalNaniteTrees,
        TotalShrubs,
        TotalGrass,
        TotalGroundCover,
        TotalRocks);

    if (GEngine && GeneratedChunks.Num() == 1)
    {
        GEngine->AddOnScreenDebugMessage(
            -1,
            20.0f,
            FColor(120, 255, 170),
            FString::Printf(
                TEXT("AETHER NANITE DETAIL // %d TREES // %d SHRUBS // %d GROUND // %d ROCKS // %d/7 ROCK TYPES"),
                TotalNaniteTrees,
                TotalShrubs,
                TotalGrass + TotalGroundCover,
                TotalRocks,
                LoadedRockVariants));
    }

    return true;
}

void AAetherEnhancedEnvironmentActor::PrepareEnvironment()
{
    ++PrepareAttempts;
    if (!bAssetsReady)
    {
        const bool bPlantsLoaded = LoadPlantAssets();
        LoadedRockVariants = DiscoverAndAssignRockCollection();
        if (!bPlantsLoaded)
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("[Aether Enhanced Environment] Required Nanite sample assets failed to load; enhanced placement stopped."));
            return;
        }
        bAssetsReady = true;
    }

    const FVector Focus = FocusLocation();
    const FIntPoint FocusChunk(
        FMath::FloorToInt(Focus.X / ChunkSizeCm),
        FMath::FloorToInt(Focus.Y / ChunkSizeCm));

    if (!IsInsideWorld(FocusChunk)
        || !IsTerrainReady(ChunkBounds(FocusChunk)))
    {
        if (PrepareAttempts < AetherEnhancedEnvironment::MaximumPrepareAttempts)
        {
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[Aether Enhanced Environment] Waiting for Mesh Terrain collision (%d/%d)."),
                PrepareAttempts,
                AetherEnhancedEnvironment::MaximumPrepareAttempts);
            GetWorldTimerManager().SetTimer(
                PrepareTimer,
                this,
                &AAetherEnhancedEnvironmentActor::PrepareEnvironment,
                1.5f,
                false);
        }
        else
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("[Aether Enhanced Environment] Mesh Terrain collision never became ready."));
        }
        return;
    }

    BeginLocalRing(FocusChunk);
    UpdateEnvironment();
    GetWorldTimerManager().SetTimer(
        UpdateTimer,
        this,
        &AAetherEnhancedEnvironmentActor::UpdateEnvironment,
        1.5f,
        true);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Enhanced Environment] DENSE NANITE PLANTS AND MULTI-ROCK STREAMING READY."));
}

void AAetherEnhancedEnvironmentActor::UpdateEnvironment()
{
    if (!bAssetsReady || !GetWorld())
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
    for (int32 Check = 0;
         Check < Checks && PendingChunks.Num() > 0;
         ++Check)
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
