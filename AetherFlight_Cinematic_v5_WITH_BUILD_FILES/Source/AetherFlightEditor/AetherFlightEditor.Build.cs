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

        // UE 5.8.1's public MeshPartitionCompiledSection.h includes
        // MaterialCache/MaterialCacheVirtualTexture.h from Engine/Internal.
        // Launcher builds do not add that internal root to external modules,
        // so expose the exact installed header location to this editor-only bridge.
        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Internal"),
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Private")
        });
    }
}
