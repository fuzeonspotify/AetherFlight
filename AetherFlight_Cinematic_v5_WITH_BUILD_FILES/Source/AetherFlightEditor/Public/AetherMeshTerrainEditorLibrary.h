#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "AetherMeshTerrainEditorLibrary.generated.h"

UCLASS()
class AETHERFLIGHTEDITOR_API UAetherMeshTerrainEditorLibrary final : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /**
     * Builds only Mesh Terrain preview sections intersecting the supplied box.
     * This is editor-only and does not create compiled/runtime sections.
     */
    UFUNCTION(BlueprintCallable, Category = "Aether|Mesh Terrain")
    static bool BuildBoundedPreviewSections(
        const FString& MeshPartitionActorLabel,
        FVector Center,
        FVector Extent,
        bool bForceSynchronous = true);
};
