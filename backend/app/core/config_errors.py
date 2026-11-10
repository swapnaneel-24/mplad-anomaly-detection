"""Sanitized configuration errors.

Raised at application startup when the configuration is internally
inconsistent. The error message never includes credentials, connection
strings, file paths or internal hostnames — only the names of the
misconfigured settings and a short, safe explanation.
"""

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """Raised when application configuration is internally inconsistent.

    The message is safe to surface in logs and error responses: it
    contains only setting names and a brief explanation, never
    credentials, connection strings, or paths.
    """


class DatabaseConfigurationError(ConfigurationError):
    """Raised when a required database is not properly configured."""
