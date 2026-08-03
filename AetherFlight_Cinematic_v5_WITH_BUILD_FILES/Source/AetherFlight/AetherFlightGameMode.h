#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "AetherFlightGameMode.generated.h"

UCLASS()
class AETHERFLIGHT_API AAetherFlightGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAetherFlightGameMode();
    virtual void StartPlay() override;
};
