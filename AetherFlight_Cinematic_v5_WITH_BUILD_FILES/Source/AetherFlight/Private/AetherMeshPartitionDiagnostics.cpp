#include "AetherMeshPartitionDiagnostics.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "PhysicsEngine/BodySetup.h"
#include "UObject/UObjectIterator.h"
#include "MeshPartitionCollisionComponent.h"

namespace
{
using FMeshPartitionCollisionComponent = UE::MeshPartition::UMeshPartitionCollisionComponent;

UWorld* FindPIEWorld()
{
    if (!GEngine)
    {
        return nullptr;
    }

    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType == EWorldType::PIE && Context.World())
        {
            return Context.World();
        }
    }

    return nullptr;
}

const TCHAR* BoolText(const bool bValue)
{
    return bValue ? TEXT("True") : TEXT("False");
}

bool VerticalSegmentOverlapsBounds(const FVector& Start, const FVector& End, const FBoxSphereBounds& Bounds)
{
    const FVector Min = Bounds.Origin - Bounds.BoxExtent;
    const FVector Max = Bounds.Origin + Bounds.BoxExtent;
    const double SegmentMinZ = FMath::Min(Start.Z, End.Z);
    const double SegmentMaxZ = FMath::Max(Start.Z, End.Z);

    return Start.X >= Min.X && Start.X <= Max.X
        && Start.Y >= Min.Y && Start.Y <= Max.Y
        && SegmentMaxZ >= Min.Z && SegmentMinZ <= Max.Z;
}

double HorizontalDistanceToBounds(const FVector& Point, const FBoxSphereBounds& Bounds)
{
    const FVector Min = Bounds.Origin - Bounds.BoxExtent;
    const FVector Max = Bounds.Origin + Bounds.BoxExtent;
    const double DX = Point.X < Min.X ? Min.X - Point.X : (Point.X > Max.X ? Point.X - Max.X : 0.0);
    const double DY = Point.Y < Min.Y ? Min.Y - Point.Y : (Point.Y > Max.Y ? Point.Y - Max.Y : 0.0);
    return FMath::Sqrt(DX * DX + DY * DY);
}
}

FString UAetherMeshPartitionDiagnostics::AuditPIEMeshPartitionCollision()
{
    TArray<FString> Lines;
    Lines.Add(TEXT("AETHER STAGE 14I - NATIVE RIVER COLLISION REGISTRATION AUDIT"));
    Lines.Add(FString::ChrN(100, TEXT('=')));
    Lines.Add(TEXT("READ_ONLY=TRUE"));
    Lines.Add(TEXT("Reads native Mesh Partition data, bounds, direct component traces, and world scene queries only; no rebuild, mutation, save, PIE command, cook, or commandlet is invoked."));

    UWorld* World = FindPIEWorld();
    if (!World)
    {
        Lines.Add(TEXT("NATIVE_AUDIT_RESULT=FAIL"));
        Lines.Add(TEXT("ERROR=No PIE world exists"));
        return FString::Join(Lines, TEXT("\n"));
    }

    TArray<FMeshPartitionCollisionComponent*> Components;
    TSet<const AActor*> SectionOwners;
    int32 RegisteredCount = 0;
    int32 ActiveCount = 0;
    int32 ShouldCreatePhysicsCount = 0;
    int32 PhysicsStateCreatedCount = 0;
    int32 ValidPhysicsStateCount = 0;
    int32 NonZeroBoundsCount = 0;
    int32 CollisionDataValidCount = 0;
    int32 CollisionMeshValidCount = 0;
    int32 ContainsTriMeshDataCount = 0;
    int32 BodySetupValidCount = 0;
    int32 BodySetupCreatedPhysicsMeshesCount = 0;
    int32 BodySetupFailedPhysicsMeshesCount = 0;
    int32 BodySetupHasCookedDataCount = 0;
    int32 BodySetupTriMeshGeometryCount = 0;
    int32 QueryCollisionEnabledCount = 0;
    int32 VisibilityBlockingCount = 0;

    Lines.Add(FString::Printf(TEXT("PIE_WORLD=%s"), *World->GetPathName()));

    for (TObjectIterator<FMeshPartitionCollisionComponent> It; It; ++It)
    {
        FMeshPartitionCollisionComponent* Component = *It;
        if (!Component || Component->IsTemplate() || Component->GetWorld() != World)
        {
            continue;
        }

        Components.Add(Component);
        if (const AActor* Owner = Component->GetOwner())
        {
            SectionOwners.Add(Owner);
        }

        const bool bRegistered = Component->IsRegistered();
        const bool bActive = Component->IsActive();
        const bool bShouldCreatePhysics = Component->ShouldCreatePhysicsState();
        const bool bPhysicsStateCreated = Component->IsPhysicsStateCreated();
        const bool bValidPhysicsState = Component->HasValidPhysicsState();
        const auto MeshCollisionData = Component->GetMeshCollisionData();
        const bool bCollisionDataValid = MeshCollisionData.IsValid();
        const bool bCollisionMeshValid = bCollisionDataValid && MeshCollisionData->Mesh.IsSet();
        const bool bContainsTriMeshData = Component->ContainsPhysicsTriMeshData(true);
        const ECollisionEnabled::Type CollisionEnabled = Component->GetCollisionEnabled();
        const ECollisionResponse VisibilityResponse = Component->GetCollisionResponseToChannel(ECC_Visibility);
        const FBoxSphereBounds Bounds = Component->CalcBounds(Component->GetComponentTransform());
        UBodySetup* BodySetup = Component->GetBodySetup();

        RegisteredCount += bRegistered ? 1 : 0;
        ActiveCount += bActive ? 1 : 0;
        ShouldCreatePhysicsCount += bShouldCreatePhysics ? 1 : 0;
        PhysicsStateCreatedCount += bPhysicsStateCreated ? 1 : 0;
        ValidPhysicsStateCount += bValidPhysicsState ? 1 : 0;
        NonZeroBoundsCount += !Bounds.BoxExtent.IsNearlyZero() ? 1 : 0;
        CollisionDataValidCount += bCollisionDataValid ? 1 : 0;
        CollisionMeshValidCount += bCollisionMeshValid ? 1 : 0;
        ContainsTriMeshDataCount += bContainsTriMeshData ? 1 : 0;
        QueryCollisionEnabledCount += CollisionEnabled != ECollisionEnabled::NoCollision ? 1 : 0;
        VisibilityBlockingCount += VisibilityResponse == ECR_Block ? 1 : 0;

        if (BodySetup)
        {
            ++BodySetupValidCount;
            BodySetupCreatedPhysicsMeshesCount += BodySetup->bCreatedPhysicsMeshes ? 1 : 0;
            BodySetupFailedPhysicsMeshesCount += BodySetup->bFailedToCreatePhysicsMeshes ? 1 : 0;
            BodySetupHasCookedDataCount += BodySetup->bHasCookedCollisionData ? 1 : 0;
            BodySetupTriMeshGeometryCount += BodySetup->TriMeshGeometries.Num();
        }
    }

    AActor* EnvironmentActor = nullptr;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (Actor && Actor->GetName().Contains(TEXT("Aether_VideoStage13_RiverEnvironment")))
        {
            EnvironmentActor = Actor;
            break;
        }
    }

    FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(AetherStage14NativeRiverCollision), true);
    if (EnvironmentActor)
    {
        QueryParams.AddIgnoredActor(EnvironmentActor);
    }

    const TArray<FVector> RiverSamples =
    {
        FVector(-761172.776, -815274.627, 371397.203),
        FVector(-754406.684, -811245.353, 365588.037),
        FVector(-748631.631, -806370.110, 359902.349),
        FVector(-751144.762, -802194.216, 359291.883),
        FVector(-722802.629, -775916.178, 357759.711),
        FVector(-707427.845, -781602.544, 360025.558),
        FVector(-744915.744, -797549.327, 359116.343),
        FVector(-737071.298, -795626.538, 359542.562),
        FVector(-726244.551, -783489.027, 355908.270),
        FVector(-764572.587, -810460.711, 364491.214)
    };

    int32 SamplesWithAnyBoundsOverlap = 0;
    int32 SamplesWithRegisteredBoundsOverlap = 0;
    int32 DirectComponentHits = 0;
    int32 WorldTerrainHits = 0;
    int32 WorldNonTerrainHits = 0;

    Lines.Add(TEXT(""));
    Lines.Add(TEXT("RIVER_TARGETED_TESTS"));
    Lines.Add(FString::ChrN(100, TEXT('-')));
    Lines.Add(FString::Printf(TEXT("ENVIRONMENT_ACTOR_IGNORED=%s"), BoolText(EnvironmentActor != nullptr)));

    for (int32 SampleIndex = 0; SampleIndex < RiverSamples.Num(); ++SampleIndex)
    {
        const FVector Sample = RiverSamples[SampleIndex];
        const FVector Start(Sample.X, Sample.Y, Sample.Z + 250000.0);
        const FVector End(Sample.X, Sample.Y, Sample.Z - 250000.0);

        int32 AnyBoundsOverlap = 0;
        int32 RegisteredBoundsOverlap = 0;
        int32 SampleDirectHits = 0;
        double NearestRegisteredBoundsXY = TNumericLimits<double>::Max();
        FString NearestRegisteredComponent = TEXT("None");
        FString FirstDirectHitComponent = TEXT("None");
        FVector FirstDirectHitPoint = FVector::ZeroVector;

        for (FMeshPartitionCollisionComponent* Component : Components)
        {
            if (!Component)
            {
                continue;
            }

            const FBoxSphereBounds Bounds = Component->CalcBounds(Component->GetComponentTransform());
            const double DistanceXY = HorizontalDistanceToBounds(Sample, Bounds);
            if (Component->IsRegistered() && DistanceXY < NearestRegisteredBoundsXY)
            {
                NearestRegisteredBoundsXY = DistanceXY;
                NearestRegisteredComponent = Component->GetPathName();
            }

            if (!VerticalSegmentOverlapsBounds(Start, End, Bounds))
            {
                continue;
            }

            ++AnyBoundsOverlap;
            if (!Component->IsRegistered())
            {
                continue;
            }

            ++RegisteredBoundsOverlap;
            FHitResult DirectHit;
            if (Component->LineTraceComponent(DirectHit, Start, End, QueryParams))
            {
                ++SampleDirectHits;
                if (FirstDirectHitComponent == TEXT("None"))
                {
                    FirstDirectHitComponent = Component->GetPathName();
                    FirstDirectHitPoint = DirectHit.ImpactPoint;
                }
            }
        }

        FHitResult WorldHit;
        const bool bWorldHit = World->LineTraceSingleByChannel(WorldHit, Start, End, ECC_Visibility, QueryParams);
        const UPrimitiveComponent* WorldHitComponent = bWorldHit ? WorldHit.GetComponent() : nullptr;
        const bool bWorldTerrainHit = WorldHitComponent && WorldHitComponent->IsA<FMeshPartitionCollisionComponent>();

        SamplesWithAnyBoundsOverlap += AnyBoundsOverlap > 0 ? 1 : 0;
        SamplesWithRegisteredBoundsOverlap += RegisteredBoundsOverlap > 0 ? 1 : 0;
        DirectComponentHits += SampleDirectHits > 0 ? 1 : 0;
        WorldTerrainHits += bWorldTerrainHit ? 1 : 0;
        WorldNonTerrainHits += bWorldHit && !bWorldTerrainHit ? 1 : 0;

        Lines.Add(FString::Printf(
            TEXT("SAMPLE_%d=location:%s any_bounds:%d registered_bounds:%d nearest_registered_xy_cm:%.3f nearest_component:%s"),
            SampleIndex,
            *Sample.ToString(),
            AnyBoundsOverlap,
            RegisteredBoundsOverlap,
            NearestRegisteredBoundsXY,
            *NearestRegisteredComponent));
        Lines.Add(FString::Printf(
            TEXT("SAMPLE_%d_DIRECT=hit_components:%d first_component:%s first_point:%s"),
            SampleIndex,
            SampleDirectHits,
            *FirstDirectHitComponent,
            *FirstDirectHitPoint.ToString()));
        Lines.Add(FString::Printf(
            TEXT("SAMPLE_%d_WORLD=blocking:%s terrain_component:%s actor:%s component:%s point:%s"),
            SampleIndex,
            BoolText(bWorldHit),
            BoolText(bWorldTerrainHit),
            bWorldHit && WorldHit.GetActor() ? *WorldHit.GetActor()->GetName() : TEXT("None"),
            WorldHitComponent ? *WorldHitComponent->GetName() : TEXT("None"),
            *WorldHit.ImpactPoint.ToString()));
    }

    Lines.Add(TEXT(""));
    Lines.Add(TEXT("SUMMARY"));
    Lines.Add(FString::ChrN(100, TEXT('-')));
    Lines.Add(FString::Printf(TEXT("PIE_COMPILED_SECTION_OWNERS=%d"), SectionOwners.Num()));
    Lines.Add(FString::Printf(TEXT("COLLISION_COMPONENTS=%d"), Components.Num()));
    Lines.Add(FString::Printf(TEXT("REGISTERED_COMPONENTS=%d"), RegisteredCount));
    Lines.Add(FString::Printf(TEXT("UNREGISTERED_COMPONENTS=%d"), Components.Num() - RegisteredCount));
    Lines.Add(FString::Printf(TEXT("ACTIVE_COMPONENTS=%d"), ActiveCount));
    Lines.Add(FString::Printf(TEXT("SHOULD_CREATE_PHYSICS_COMPONENTS=%d"), ShouldCreatePhysicsCount));
    Lines.Add(FString::Printf(TEXT("PHYSICS_STATE_CREATED_COMPONENTS=%d"), PhysicsStateCreatedCount));
    Lines.Add(FString::Printf(TEXT("VALID_PHYSICS_STATE_COMPONENTS=%d"), ValidPhysicsStateCount));
    Lines.Add(FString::Printf(TEXT("NONZERO_BOUNDS_COMPONENTS=%d"), NonZeroBoundsCount));
    Lines.Add(FString::Printf(TEXT("QUERY_COLLISION_ENABLED_COMPONENTS=%d"), QueryCollisionEnabledCount));
    Lines.Add(FString::Printf(TEXT("VISIBILITY_BLOCKING_COMPONENTS=%d"), VisibilityBlockingCount));
    Lines.Add(FString::Printf(TEXT("COLLISION_DATA_VALID_COMPONENTS=%d"), CollisionDataValidCount));
    Lines.Add(FString::Printf(TEXT("COLLISION_MESH_VALID_COMPONENTS=%d"), CollisionMeshValidCount));
    Lines.Add(FString::Printf(TEXT("CONTAINS_TRI_MESH_DATA_COMPONENTS=%d"), ContainsTriMeshDataCount));
    Lines.Add(FString::Printf(TEXT("BODY_SETUP_VALID_COMPONENTS=%d"), BodySetupValidCount));
    Lines.Add(FString::Printf(TEXT("BODY_SETUP_CREATED_PHYSICS_MESHES_COMPONENTS=%d"), BodySetupCreatedPhysicsMeshesCount));
    Lines.Add(FString::Printf(TEXT("BODY_SETUP_FAILED_PHYSICS_MESHES_COMPONENTS=%d"), BodySetupFailedPhysicsMeshesCount));
    Lines.Add(FString::Printf(TEXT("BODY_SETUP_HAS_COOKED_DATA_COMPONENTS=%d"), BodySetupHasCookedDataCount));
    Lines.Add(FString::Printf(TEXT("BODY_SETUP_TRI_MESH_GEOMETRIES=%d"), BodySetupTriMeshGeometryCount));
    Lines.Add(FString::Printf(TEXT("RIVER_SAMPLES=%d"), RiverSamples.Num()));
    Lines.Add(FString::Printf(TEXT("SAMPLES_WITH_ANY_COLLISION_BOUNDS=%d"), SamplesWithAnyBoundsOverlap));
    Lines.Add(FString::Printf(TEXT("SAMPLES_WITH_REGISTERED_COLLISION_BOUNDS=%d"), SamplesWithRegisteredBoundsOverlap));
    Lines.Add(FString::Printf(TEXT("SAMPLES_WITH_DIRECT_COMPONENT_HITS=%d"), DirectComponentHits));
    Lines.Add(FString::Printf(TEXT("SAMPLES_WITH_WORLD_TERRAIN_HITS=%d"), WorldTerrainHits));
    Lines.Add(FString::Printf(TEXT("SAMPLES_WITH_WORLD_NON_TERRAIN_HITS=%d"), WorldNonTerrainHits));

    FString Diagnosis;
    if (Components.Num() == 0)
    {
        Diagnosis = TEXT("NO_COMPILED_COLLISION_COMPONENTS");
    }
    else if (CollisionDataValidCount == 0 || CollisionMeshValidCount == 0 || ContainsTriMeshDataCount == 0)
    {
        Diagnosis = TEXT("COLLISION_TRANSFORMER_OUTPUT_HAS_NO_NATIVE_TRIANGLE_DATA");
    }
    else if (BodySetupValidCount == 0)
    {
        Diagnosis = TEXT("COLLISION_TRIANGLE_DATA_EXISTS_BUT_BODY_SETUP_IS_MISSING");
    }
    else if (BodySetupFailedPhysicsMeshesCount > 0)
    {
        Diagnosis = TEXT("BODY_SETUP_PHYSICS_MESH_CREATION_FAILED");
    }
    else if (BodySetupCreatedPhysicsMeshesCount == 0 || BodySetupTriMeshGeometryCount == 0)
    {
        Diagnosis = TEXT("BODY_SETUP_EXISTS_BUT_PHYSICS_TRIANGLE_MESHES_WERE_NOT_CREATED");
    }
    else if (PhysicsStateCreatedCount == 0 || ValidPhysicsStateCount == 0)
    {
        Diagnosis = TEXT("PHYSICS_MESHES_EXIST_BUT_COMPONENT_PHYSICS_STATE_WAS_NOT_CREATED");
    }
    else if (SamplesWithRegisteredBoundsOverlap == 0)
    {
        Diagnosis = TEXT("RIVER_REGION_HAS_NO_REGISTERED_COLLISION_BOUNDS");
    }
    else if (DirectComponentHits == 0)
    {
        Diagnosis = TEXT("REGISTERED_RIVER_COLLISION_BOUNDS_EXIST_BUT_DIRECT_GEOMETRY_TRACES_MISS");
    }
    else if (WorldTerrainHits == 0)
    {
        Diagnosis = TEXT("DIRECT_TERRAIN_COMPONENT_TRACES_WORK_BUT_WORLD_SCENE_QUERY_REGISTRATION_FAILS");
    }
    else
    {
        Diagnosis = TEXT("NATIVE_RIVER_TERRAIN_COLLISION_TRACES_SUCCEED_PYTHON_TRACE_PATH_WAS_INVALID");
    }

    Lines.Add(FString::Printf(TEXT("DIAGNOSIS=%s"), *Diagnosis));
    Lines.Add(TEXT("NATIVE_AUDIT_RESULT=PASS"));
    Lines.Add(TEXT("NO_COLLISION_SETTINGS_CHANGED=TRUE"));
    Lines.Add(TEXT("NO_COMPONENT_REBUILD_CALLED=TRUE"));
    Lines.Add(TEXT("NO_PACKAGES_SAVED=TRUE"));
    Lines.Add(TEXT("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE"));
    Lines.Add(TEXT("NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE"));

    return FString::Join(Lines, TEXT("\n"));
}
