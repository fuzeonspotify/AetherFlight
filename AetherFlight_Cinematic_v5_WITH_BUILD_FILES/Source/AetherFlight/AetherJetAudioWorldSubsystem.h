#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AetherJetAudioWorldSubsystem.generated.h"

/** Automatically installs the jet audio controller in PIE and game worlds. */
UCLASS()
class AETHERFLIGHT_API UAetherJetAudioWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
