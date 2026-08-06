#pragma once

#include "UObject/Object.h"

// UE 5.8.1 launcher builds omit this experimental Engine header even though
// MeshPartitionCompiledSection.h includes it publicly. The MeshPartition public
// header only stores TObjectPtr<UMaterialCacheVirtualTexture> members in this
// editor bridge translation unit, so a complete UObject-compatible stand-in is
// sufficient here. No instances are created and no members are accessed.
class UMaterialCacheVirtualTexture : public UObject
{
};
