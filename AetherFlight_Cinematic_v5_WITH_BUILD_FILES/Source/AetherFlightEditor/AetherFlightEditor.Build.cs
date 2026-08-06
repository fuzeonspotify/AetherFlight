using System.IO;
using UnrealBuildTool;

public class AetherFlightEditor : ModuleRules
{
    public AetherFlightEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",
            "MeshPartition",
            "MeshPartitionEditor"
        });

        // UE 5.8.1 launcher builds omit the experimental material-cache header
        // that MeshPartitionCompiledSection.h includes publicly. Resolve the
        // editor-only compatibility type from this module first. The Engine
        // roots remain available for all other MeshPartition dependencies.
        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Private"),
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Classes"),
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Private")
        });
    }
}
