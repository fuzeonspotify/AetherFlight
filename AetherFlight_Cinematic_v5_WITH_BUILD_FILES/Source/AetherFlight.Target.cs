using UnrealBuildTool;
using System.Collections.Generic;

public class AetherFlightTarget : TargetRules
{
    public AetherFlightTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("AetherFlight");
    }
}
