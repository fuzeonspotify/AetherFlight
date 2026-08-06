#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AetherBiomeWorldSubsystem.generated.h"

/** Automatically adds the production biome scatter actor to game worlds. */
UCLASS()
class AETHERFLIGHT_API UAetherBiomeWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
