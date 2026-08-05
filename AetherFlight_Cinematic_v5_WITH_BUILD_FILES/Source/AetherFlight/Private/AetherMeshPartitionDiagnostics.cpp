#include "AetherMeshPartitionDiagnostics.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "UObject/UObjectIterator.h"
#include "PhysicsEngine/BodySetup.h"
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
}

FString UAetherMeshPartitionDiagnostics::AuditPIEMeshPartitionCollision()
{
    TArray<FString> Lines;
    Lines.Add(TEXT("AETHER STAGE 14H - NATIVE MESH PARTITION COLLISION AUDIT"));
    Lines.Add(FString::ChrN(100, TEXT('=')));
    Lines.Add(TEXT("READ_ONLY=TRUE"));
    Lines.Add(TEXT("Reads native Mesh Partition collision data/body state only; no rebuild, mutation, save, PIE command, cook, or commandlet is invoked."));

    UWorld* World = FindPIEWorld();
    if (!World)
    {
        Lines.Add(TEXT("NATIVE_AUDIT_RESULT=FAIL"));
        Lines.Add(TEXT("ERROR=No PIE world exists"));
        return FString::Join(Lines, TEXT("\n"));
    }

    TSet<const AActor*> SectionOwners;
    int32 ComponentCount = 0;
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
    int32 DetailCount = 0;

    Lines.Add(FString::Printf(TEXT("PIE_WORLD=%s"), *World->GetPathName()));

    for (TObjectIterator<FMeshPartitionCollisionComponent> It; It; ++It)
    {
        FMeshPartitionCollisionComponent* Component = *It;
        if (!Component || Component->IsTemplate() || Component->GetWorld() != World)
        {
            continue;
        }

        ++ComponentCount;
        const AActor* Owner = Component->GetOwner();
        if (Owner)
        {
            SectionOwners.Add(Owner);
        }

        const bool bRegistered = Component->IsRegistered();
        const bool bActive = Component->IsActive();
        const bool bShouldCreatePhysics = Component->ShouldCreatePhysicsState();
        const bool bPhysicsStateCreated = Component->IsPhysicsStateCreated();
        const bool bValidPhysicsState = Component->HasValidPhysicsState();
        const bool bCollisionDataValid = Component->GetMeshCollisionData().IsValid();
        const bool bCollisionMeshValid = Component->GetCollisionMesh() != nullptr;
        const bool bContainsTriMeshData = Component->ContainsPhysicsTriMeshData(true);
        const ECollisionEnabled::Type CollisionEnabled = Component->GetCollisionEnabled();
        const ECollisionResponse VisibilityResponse = Component->GetCollisionResponseToChannel(ECC_Visibility);
        const FBoxSphereBounds Bounds = Component->CalcBounds(Component->GetComponentTransform());
        const bool bNonZeroBounds = !Bounds.BoxExtent.IsNearlyZero();
        UBodySetup* BodySetup = Component->GetBodySetup();

        RegisteredCount += bRegistered ? 1 : 0;
        ActiveCount += bActive ? 1 : 0;
        ShouldCreatePhysicsCount += bShouldCreatePhysics ? 1 : 0;
        PhysicsStateCreatedCount += bPhysicsStateCreated ? 1 : 0;
        ValidPhysicsStateCount += bValidPhysicsState ? 1 : 0;
        NonZeroBoundsCount += bNonZeroBounds ? 1 : 0;
        CollisionDataValidCount += bCollisionDataValid ? 1 : 0;
        CollisionMeshValidCount += bCollisionMeshValid ? 1 : 0;
        ContainsTriMeshDataCount += bContainsTriMeshData ? 1 : 0;
        QueryCollisionEnabledCount += CollisionEnabled != ECollisionEnabled::NoCollision ? 1 : 0;
        VisibilityBlockingCount += VisibilityResponse == ECR_Block ? 1 : 0;

        bool bBodyCreated = false;
        bool bBodyFailed = false;
        bool bBodyHasCookedData = false;
        int32 TriMeshGeometryCount = 0;

        if (BodySetup)
        {
            ++BodySetupValidCount;
            bBodyCreated = BodySetup->bCreatedPhysicsMeshes;
            bBodyFailed = BodySetup->bFailedToCreatePhysicsMeshes;
            bBodyHasCookedData = BodySetup->bHasCookedCollisionData;
            TriMeshGeometryCount = BodySetup->TriMeshGeometries.Num();

            BodySetupCreatedPhysicsMeshesCount += bBodyCreated ? 1 : 0;
            BodySetupFailedPhysicsMeshesCount += bBodyFailed ? 1 : 0;
            BodySetupHasCookedDataCount += bBodyHasCookedData ? 1 : 0;
            BodySetupTriMeshGeometryCount += TriMeshGeometryCount;
        }

        if (DetailCount < 24)
        {
            const FString OwnerName = Owner ? Owner->GetName() : TEXT("None");
            const FString ComponentName = Component->GetName();
            const FString BoundsOrigin = Bounds.Origin.ToString();
            const FString BoundsExtent = Bounds.BoxExtent.ToString();

            FString Detail = FString::Printf(
                TEXT("COMPONENT_%d=owner:%s name:%s"),
                DetailCount,
                *OwnerName,
                *ComponentName);
            Detail += FString::Printf(
                TEXT(" registered:%s active:%s should_create_physics:%s physics_state_created:%s valid_physics_state:%s"),
                BoolText(bRegistered),
                BoolText(bActive),
                BoolText(bShouldCreatePhysics),
                BoolText(bPhysicsStateCreated),
                BoolText(bValidPhysicsState));
            Detail += FString::Printf(
                TEXT(" collision_enabled:%d visibility_response:%d nonzero_bounds:%s bounds_origin:%s bounds_extent:%s"),
                static_cast<int32>(CollisionEnabled),
                static_cast<int32>(VisibilityResponse),
                BoolText(bNonZeroBounds),
                *BoundsOrigin,
                *BoundsExtent);
            Detail += FString::Printf(
                TEXT(" collision_data:%s collision_mesh:%s contains_trimesh:%s body_setup:%s"),
                BoolText(bCollisionDataValid),
                BoolText(bCollisionMeshValid),
                BoolText(bContainsTriMeshData),
                BoolText(BodySetup != nullptr));
            Detail += FString::Printf(
                TEXT(" body_created:%s body_failed:%s body_has_cooked_data:%s trimesh_geometries:%d"),
                BoolText(bBodyCreated),
                BoolText(bBodyFailed),
                BoolText(bBodyHasCookedData),
                TriMeshGeometryCount);
            Lines.Add(MoveTemp(Detail));
            ++DetailCount;
        }
    }

    Lines.Add(TEXT(""));
    Lines.Add(TEXT("SUMMARY"));
    Lines.Add(FString::ChrN(100, TEXT('-')));
    Lines.Add(FString::Printf(TEXT("PIE_COMPILED_SECTION_OWNERS=%d"), SectionOwners.Num()));
    Lines.Add(FString::Printf(TEXT("COLLISION_COMPONENTS=%d"), ComponentCount));
    Lines.Add(FString::Printf(TEXT("REGISTERED_COMPONENTS=%d"), RegisteredCount));
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

    FString Diagnosis;
    if (ComponentCount == 0)
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
    else if (NonZeroBoundsCount == 0)
    {
        Diagnosis = TEXT("COLLISION_DATA_AND_PHYSICS_STATE_EXIST_BUT_COMPONENT_BOUNDS_ARE_ZERO");
    }
    else
    {
        Diagnosis = TEXT("NATIVE_COLLISION_STATE_EXISTS_TRACE_REGISTRATION_PATH_NEEDS_TARGETED_TEST");
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
