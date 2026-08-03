#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "AetherFlightHUD.generated.h"

UCLASS()
class AETHERFLIGHT_API AAetherFlightHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;

private:
    void DrawReticle(float CenterX, float CenterY);
    void DrawReadout(const FString& Label, const FString& Value, float X, float Y);
};
