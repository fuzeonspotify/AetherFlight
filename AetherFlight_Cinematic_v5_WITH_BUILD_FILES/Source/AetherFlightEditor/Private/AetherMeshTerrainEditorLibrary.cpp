#include "AetherMeshTerrainEditorLibrary.h"

#include "Editor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "MeshPartitionEditorComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogAetherMeshTerrainEditor, Log, All);

namespace
{
UMeshPartitionEditorComponent* FindMeshPartitionEditorComponent(
    const FString& MeshPartitionActorLabel,
    FString& OutError)
{
    if (!GEditor)
    {
        OutError = TEXT("GEditor is unavailable.");
        return nullptr;
    }

    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        OutError = TEXT("The editor world is unavailable.");
        return nullptr;
    }

    UMeshPartitionEditorComponent* FoundComponent = nullptr;
    int32 MatchingActorCount = 0;

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!IsValid(Actor) || Actor->GetActorLabel() != MeshPartitionActorLabel)
        {
            continue;
        }

        ++MatchingActorCount;
        UMeshPartitionEditorComponent* Candidate =
            Actor->FindComponentByClass<UMeshPartitionEditorComponent>();
        if (!IsValid(Candidate))
        {
            OutError = FString::Printf(
                TEXT("Actor '%s' has no UMeshPartitionEditorComponent."),
                *MeshPartitionActorLabel);
            return nullptr;
        }

        if (FoundComponent)
        {
            OutError = FString::Printf(
                TEXT("More than one actor is labelled '%s'."),
                *MeshPartitionActorLabel);
            return nullptr;
        }

        FoundComponent = Candidate;
    }

    if (MatchingActorCount != 1 || !FoundComponent)
    {
        OutError = FString::Printf(
            TEXT("Expected exactly one actor labelled '%s'; found %d."),
            *MeshPartitionActorLabel,
            MatchingActorCount);
        return nullptr;
    }

    return FoundComponent;
}
}

bool UAetherMeshTerrainEditorLibrary::BuildBoundedPreviewSections(
    const FString& MeshPartitionActorLabel,
    FVector Center,
    FVector Extent,
    bool bForceSynchronous)
{
    if (MeshPartitionActorLabel.IsEmpty())
    {
        UE_LOG(LogAetherMeshTerrainEditor, Error,
            TEXT("AETHER_CPP_BOUNDED_PREVIEW_BUILD=FAIL reason=EMPTY_ACTOR_LABEL"));
        return false;
    }

    if (Center.ContainsNaN() || Extent.ContainsNaN()
        || Extent.X <= 0.0 || Extent.Y <= 0.0 || Extent.Z <= 0.0)
    {
        UE_LOG(LogAetherMeshTerrainEditor, Error,
            TEXT("AETHER_CPP_BOUNDED_PREVIEW_BUILD=FAIL reason=INVALID_BOUNDS center=%s extent=%s"),
            *Center.ToString(),
            *Extent.ToString());
        return false;
    }

    FString Error;
    UMeshPartitionEditorComponent* EditorComponent =
        FindMeshPartitionEditorComponent(MeshPartitionActorLabel, Error);
    if (!EditorComponent)
    {
        UE_LOG(LogAetherMeshTerrainEditor, Error,
            TEXT("AETHER_CPP_BOUNDED_PREVIEW_BUILD=FAIL reason=%s"),
            *Error);
        return false;
    }

    const bool bPreviousBuildEnabled = EditorComponent->IsPreviewSectionBuildEnabled();
    const bool bPreviousForceSynchronous =
        EditorComponent->IsSynchronousPreviewSectionBuildForced();

    EditorComponent->UpdateModifierList();
    EditorComponent->SetPreviewSectionBuildEnabled(true);
    EditorComponent->SetForceSynchronousPreviewSectionBuild(bForceSynchronous);

    TArray<FBox> BoundsToBuild;
    BoundsToBuild.Emplace(Center - Extent, Center + Extent);

    UE_LOG(LogAetherMeshTerrainEditor, Warning,
        TEXT("AETHER_CPP_BOUNDED_PREVIEW_REQUEST actor=%s center=%s extent=%s synchronous=%s"),
        *MeshPartitionActorLabel,
        *Center.ToString(),
        *Extent.ToString(),
        bForceSynchronous ? TEXT("TRUE") : TEXT("FALSE"));

    EditorComponent->BuildMegaMeshPreviewSections(BoundsToBuild);

    const bool bBuildStillActive = EditorComponent->IsAnyPreviewSectionBuildActive();

    EditorComponent->SetForceSynchronousPreviewSectionBuild(bPreviousForceSynchronous);
    EditorComponent->SetPreviewSectionBuildEnabled(bPreviousBuildEnabled);

    UE_LOG(LogAetherMeshTerrainEditor, Warning,
        TEXT("AETHER_CPP_BOUNDED_PREVIEW_BUILD=PASS active_after_call=%s previous_enabled=%s previous_sync=%s"),
        bBuildStillActive ? TEXT("TRUE") : TEXT("FALSE"),
        bPreviousBuildEnabled ? TEXT("TRUE") : TEXT("FALSE"),
        bPreviousForceSynchronous ? TEXT("TRUE") : TEXT("FALSE"));

    return true;
}
