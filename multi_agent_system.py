"""DEPRECATED: use `project_starter.OrchestrationAgent`.

This module is retained only as a compatibility shim so older imports do not
break. The active implementation now lives in `project_starter.py` and is
wired using pydantic-ai `Agent` instances and `@agent.tool` registrations.
"""

from warnings import warn

from project_starter import OrchestrationAgent

warn(
    "multi_agent_system.py is deprecated; import OrchestrationAgent from project_starter instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["OrchestrationAgent"]
