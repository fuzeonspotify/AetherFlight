#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AetherMeshPartitionDiagnostics.generated.h"

UCLASS()
class AETHERFLIGHT_API UAetherMeshPartitionDiagnostics : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Aether|Diagnostics")
    static FString AuditPIEMeshPartitionCollision();
};
