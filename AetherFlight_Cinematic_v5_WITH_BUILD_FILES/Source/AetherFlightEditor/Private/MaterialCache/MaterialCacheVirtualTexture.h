#pragma once

// UE 5.8.1 launcher builds expose MeshPartitionCompiledSection.h publicly,
// but that header includes this Engine-internal path even though consumers only
// require the UObject type declaration for TObjectPtr members. Keep this shim
// editor-only and intentionally limited to the forward declaration.
class UMaterialCacheVirtualTexture;
