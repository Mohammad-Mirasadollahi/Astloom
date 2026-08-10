"""In-process Astloom backends and MCP capability dispatch."""

from .dispatch import dispatch_capability
from .platform import PlatformBackends

__all__ = ["PlatformBackends", "dispatch_capability"]
