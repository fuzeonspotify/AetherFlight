using UnrealBuildTool;
using System.Collections.Generic;

public class AetherFlightEditorTarget : TargetRules
{
    public AetherFlightEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("AetherFlight");
    }
}
