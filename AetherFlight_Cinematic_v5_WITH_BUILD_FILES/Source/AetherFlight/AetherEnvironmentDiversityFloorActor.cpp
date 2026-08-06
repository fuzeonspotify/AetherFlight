#include "AetherEnvironmentDiversityFloorActor.h"

#include "AetherVerifiedEnvironmentActor.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"

namespace AetherEnvironmentDiversityFloor
{
    constexpr float TraceTopCm = 1000000.0f;
    constexpr float TraceBottomCm = -300000.0f;
}

AAetherEnvironmentDiversityFloorActor::AAetherEnvironmentDiversityFloorActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);
}

void AAetherEnvironmentDiversityFloorActor::BeginPlay()
{
    Super::BeginPlay();
    if (!GetWorld())
    {
        return;
    }

    // The main environment begins after Mesh Terrain collision becomes ready.
    // Wait longer than that initial preparation, then keep checking in case the
    // local ring is rebuilt while the aircraft crosses a chunk boundary.
    GetWorldTimerManager().SetTimer(
        DiversityTimer,
        this,
        &AAetherEnvironmentDiversityFloorActor::ApplyDiversityFloor,
        4.0f,
        true,
        12.0f);
}

AAetherVerifiedEnvironmentActor*
AAetherEnvironmentDiversityFloorActor::FindEnvironmentActor() const
{
    if (!GetWorld())
    {
        return nullptr;
    }

    for (TActorIterator<AAetherVerifiedEnvironmentActor> It(GetWorld()); It; ++It)
    {
        return *It;
    }
    return nullptr;
}

UHierarchicalInstancedStaticMeshComponent*
AAetherEnvironmentDiversityFloorActor::FindComponent(
    AAetherVerifiedEnvironmentActor* Environment,
    const FName ComponentName) const
{
    if (!Environment)
    {
        return nullptr;
    }

    TArray<UHierarchicalInstancedStaticMeshComponent*> Components;
    Environment->GetComponents<UHierarchicalInstancedStaticMeshComponent>(Components);
    for (UHierarchicalInstancedStaticMeshComponent* Component : Components)
    {
        if (Component && Component->GetFName() == ComponentName)
        {
            return Component;
        }
    }
    return nullptr;
}

bool AAetherEnvironmentDiversityFloorActor::LooksLikeWater(const FHitResult& Hit) const
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

bool AAetherEnvironmentDiversityFloorActor::TraceTerrain(
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
        SCENE_QUERY_STAT(AetherEnvironmentDiversityFloorTrace),
        false,
        this);
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        Parameters.AddIgnoredActor(Controller->GetPawn());
    }

    if (!GetWorld()->LineTraceSingleByChannel(
            Hit,
            FVector(X, Y, AetherEnvironmentDiversityFloor::TraceTopCm),
            FVector(X, Y, AetherEnvironmentDiversityFloor::TraceBottomCm),
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

FVector AAetherEnvironmentDiversityFloorActor::FocusLocation() const
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

float AAetherEnvironmentDiversityFloorActor::ScaleForHeight(
    const UHierarchicalInstancedStaticMeshComponent* Component,
    const float DesiredHeightCm) const
{
    if (!Component || !Component->GetStaticMesh())
    {
        return 1.0f;
    }

    const float MeshHeightCm = FMath::Max(
        50.0f,
        Component->GetStaticMesh()->GetBounds().BoxExtent.Z * 2.0f);
    return FMath::Clamp(DesiredHeightCm / MeshHeightCm, 0.25f, 4.0f);
}

int32 AAetherEnvironmentDiversityFloorActor::EnsureMinimumInstances(
    UHierarchicalInstancedStaticMeshComponent* Component,
    const TCHAR* Label,
    const int32 MinimumCount,
    const float MinimumRadiusCm,
    const float MaximumRadiusCm,
    const float DesiredHeightMinCm,
    const float DesiredHeightMaxCm,
    const float MinimumNormalZ,
    const int32 SeedOffset)
{
    if (!Component || !Component->GetStaticMesh())
    {
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[Aether Diversity Floor] %s component or mesh is unavailable."),
            Label);
        return 0;
    }

    const int32 Before = Component->GetInstanceCount();
    if (Before >= MinimumCount)
    {
        return 0;
    }

    const FVector Focus = FocusLocation();
    const int32 ChunkX = FMath::FloorToInt(Focus.X / 160000.0f);
    const int32 ChunkY = FMath::FloorToInt(Focus.Y / 160000.0f);
    const uint32 Seed = static_cast<uint32>(ChunkX) * 73856093u
        ^ static_cast<uint32>(ChunkY) * 19349663u
        ^ static_cast<uint32>(SeedOffset) * 83492791u
        ^ static_cast<uint32>(PassNumber) * 2654435761u;
    FRandomStream Random(static_cast<int32>(Seed));

    const int32 Missing = MinimumCount - Before;
    const int32 MaximumAttempts = FMath::Max(60, Missing * 28);
    int32 Added = 0;
    TSet<uint64> ReservedCells;

    const float CellSizeCm = DesiredHeightMaxCm >= 1000.0f
        ? 1800.0f
        : (DesiredHeightMaxCm >= 200.0f ? 800.0f : 420.0f);

    for (int32 Attempt = 0; Attempt < MaximumAttempts && Added < Missing; ++Attempt)
    {
        const float Angle = Random.FRandRange(-PI, PI);
        const float Radius = FMath::Sqrt(Random.FRand())
            * (MaximumRadiusCm - MinimumRadiusCm)
            + MinimumRadiusCm;
        const float X = Focus.X + FMath::Cos(Angle) * Radius;
        const float Y = Focus.Y + FMath::Sin(Angle) * Radius;

        const int32 CellX = FMath::FloorToInt(X / CellSizeCm);
        const int32 CellY = FMath::FloorToInt(Y / CellSizeCm);
        const uint64 CellKey =
            (static_cast<uint64>(static_cast<uint32>(CellX)) << 32u)
            | static_cast<uint32>(CellY);
        if (ReservedCells.Contains(CellKey))
        {
            continue;
        }

        FVector Location;
        FVector Normal;
        if (!TraceTerrain(X, Y, Location, Normal) || Normal.Z < MinimumNormalZ)
        {
            continue;
        }
        ReservedCells.Add(CellKey);

        const float DesiredHeightCm = Random.FRandRange(
            DesiredHeightMinCm,
            DesiredHeightMaxCm);
        const float Scale = ScaleForHeight(Component, DesiredHeightCm);
        FRotator Rotation = DesiredHeightMaxCm >= 700.0f
            ? FRotator(
                Random.FRandRange(-1.2f, 1.2f),
                Random.FRandRange(-180.0f, 180.0f),
                Random.FRandRange(-1.2f, 1.2f))
            : FRotationMatrix::MakeFromZ(Normal).Rotator();
        Rotation.Yaw += Random.FRandRange(-180.0f, 180.0f);

        const int32 InstanceIndex = Component->AddInstance(
            FTransform(
                Rotation,
                Location - FVector(0.0f, 0.0f, Random.FRandRange(1.0f, 6.0f)),
                FVector(
                    Scale * Random.FRandRange(0.90f, 1.10f),
                    Scale * Random.FRandRange(0.90f, 1.10f),
                    Scale * Random.FRandRange(0.94f, 1.14f))),
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

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[Aether Diversity Floor] %s: before=%d added=%d after=%d minimum=%d mesh=%s"),
        Label,
        Before,
        Added,
        Component->GetInstanceCount(),
        MinimumCount,
        *Component->GetStaticMesh()->GetPathName());

    return Added;
}

void AAetherEnvironmentDiversityFloorActor::ApplyDiversityFloor()
{
    ++PassNumber;

    AAetherVerifiedEnvironmentActor* Environment = FindEnvironmentActor();
    if (!Environment)
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[Aether Diversity Floor] Waiting for the map-wide environment actor."));
        return;
    }

    struct FDiversityEntry
    {
        FName ComponentName;
        const TCHAR* Label;
        int32 MinimumCount;
        float MinimumRadiusCm;
        float MaximumRadiusCm;
        float DesiredHeightMinCm;
        float DesiredHeightMaxCm;
        float MinimumNormalZ;
        int32 SeedOffset;
    };

    const FDiversityEntry Entries[] = {
        {TEXT("CinematicPineTrees"), TEXT("DZ Pine"), 48, 30000.0f, 95000.0f, 2100.0f, 3300.0f, 0.58f, 101},
        {TEXT("CinematicAspenTrees"), TEXT("DZ Aspen"), 20, 28000.0f, 90000.0f, 1900.0f, 2850.0f, 0.66f, 102},
        {TEXT("CinematicOakTrees"), TEXT("DZ Cork Oak"), 20, 26000.0f, 88000.0f, 1550.0f, 2350.0f, 0.70f, 103},
        {TEXT("CinematicCoastalTrees"), TEXT("DZ Coconut/Palm"), 6, 42000.0f, 100000.0f, 1700.0f, 2500.0f, 0.72f, 104},
        {TEXT("CinematicShrubPrimary"), TEXT("GV Shrub A"), 18, 16000.0f, 70000.0f, 170.0f, 330.0f, 0.68f, 201},
        {TEXT("CinematicShrubSecondary"), TEXT("GV Shrub B"), 18, 17000.0f, 72000.0f, 210.0f, 390.0f, 0.68f, 202},
        {TEXT("CinematicGroundPlants"), TEXT("Nanite Abelia"), 26, 10000.0f, 58000.0f, 70.0f, 135.0f, 0.72f, 203},
        {TEXT("CinematicRocks"), TEXT("Rock"), 12, 22000.0f, 85000.0f, 250.0f, 900.0f, 0.38f, 204},
    };

    int32 TotalAdded = 0;
    for (const FDiversityEntry& Entry : Entries)
    {
        TotalAdded += EnsureMinimumInstances(
            FindComponent(Environment, Entry.ComponentName),
            Entry.Label,
            Entry.MinimumCount,
            Entry.MinimumRadiusCm,
            Entry.MaximumRadiusCm,
            Entry.DesiredHeightMinCm,
            Entry.DesiredHeightMaxCm,
            Entry.MinimumNormalZ,
            Entry.SeedOffset);
    }

    if (TotalAdded > 0)
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[Aether Diversity Floor] Added %d missing local instances across cinematic variants."),
            TotalAdded);
    }
}
