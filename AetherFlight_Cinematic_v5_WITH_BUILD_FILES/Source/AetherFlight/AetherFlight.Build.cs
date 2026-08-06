using UnrealBuildTool;

public class AetherFlight : ModuleRules
{
    public AetherFlight(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "AudioMixer",
            "Landscape",
            "ProceduralMeshComponent",
            "AssetRegistry"
        });
    }
}
