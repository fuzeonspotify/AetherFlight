#include "AetherFlightHUD.h"

#include "CinematicFlightPawn.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"

void AAetherFlightHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }

    const ACinematicFlightPawn* Aircraft = Cast<ACinematicFlightPawn>(GetOwningPawn());
    if (!Aircraft)
    {
        return;
    }

    const float W = Canvas->ClipX;
    const float H = Canvas->ClipY;
    DrawReticle(W * 0.5f, H * 0.5f);

    DrawText(TEXT("AETHER // FLIGHT TEST"), FLinearColor(0.55f, 0.9f, 1.0f), 38.0f, 32.0f,
        GEngine->GetSmallFont(), 1.25f, false);
    DrawText(TEXT("Aircraft: radekstepan / CC BY 4.0"), FLinearColor(0.52f, 0.58f, 0.62f),
        W - 280.0f, 34.0f, GEngine->GetSmallFont(), 0.75f, false);
    DrawReadout(TEXT("SPD"), FString::Printf(TEXT("%04.0f KT"), Aircraft->GetAirspeedKnots()), 40.0f, H - 154.0f);
    DrawReadout(TEXT("ALT"), FString::Printf(TEXT("%05.0f FT"), Aircraft->GetAltitudeFeet()), 40.0f, H - 112.0f);
    DrawReadout(TEXT("THR"), FString::Printf(TEXT("%03.0f %%"), Aircraft->GetThrottle() * 100.0f), 260.0f, H - 154.0f);
    DrawReadout(TEXT("MACH"), FString::Printf(TEXT("%.2f"), Aircraft->GetMach()), 260.0f, H - 112.0f);
    DrawReadout(TEXT("LOAD"), FString::Printf(TEXT("%+.1f G"), Aircraft->GetGForce()), 462.0f, H - 154.0f);
    DrawReadout(TEXT("CAM"), Aircraft->GetCameraModeName(), 462.0f, H - 112.0f);

    DrawText(TEXT("W/S throttle   A/D roll   arrows pitch   Q/E yaw   RMB free look"),
        FLinearColor(0.72f, 0.78f, 0.82f), 38.0f, H - 56.0f, GEngine->GetSmallFont(), 0.9f, false);
    DrawText(TEXT("C camera   V cinematic   T weather   R reset"),
        FLinearColor(0.72f, 0.78f, 0.82f), 38.0f, H - 34.0f, GEngine->GetSmallFont(), 0.9f, false);
}

void AAetherFlightHUD::DrawReticle(const float CenterX, const float CenterY)
{
    const FLinearColor Cyan(0.45f, 0.92f, 1.0f, 0.85f);
    DrawLine(CenterX - 28.0f, CenterY, CenterX - 8.0f, CenterY, Cyan, 1.5f);
    DrawLine(CenterX + 8.0f, CenterY, CenterX + 28.0f, CenterY, Cyan, 1.5f);
    DrawLine(CenterX, CenterY - 22.0f, CenterX, CenterY - 7.0f, Cyan, 1.5f);
}

void AAetherFlightHUD::DrawReadout(const FString& Label, const FString& Value, const float X, const float Y)
{
    DrawText(Label, FLinearColor(0.45f, 0.65f, 0.7f), X, Y, GEngine->GetSmallFont(), 0.78f, false);
    DrawText(Value, FLinearColor(0.88f, 0.98f, 1.0f), X, Y + 15.0f, GEngine->GetMediumFont(), 1.0f, false);
}
