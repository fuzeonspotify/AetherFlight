#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherLegacyRockSuppressorActor.generated.h"

/** Hides and clears the temporary PCG boulder component after the Fab rock pack takes over. */
UCLASS()
class AETHERFLIGHT_API AAetherLegacyRockSuppressorActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherLegacyRockSuppressorActor();

protected:
    virtual void BeginPlay() override;

private:
    void SuppressLegacyRocks();

    FTimerHandle SuppressTimer;
};
