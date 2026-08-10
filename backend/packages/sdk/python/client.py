"""Compatibility shim — prefer `astloom_sdk`."""

from astloom_sdk import AstloomClient, SdkError

__all__ = ["AstloomClient", "SdkError"]
