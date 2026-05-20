"""Compatibility module for legacy imports.

This module re-exports the active orchestration class from ``agents.py``.
"""

from agents import OrchestrationAgent

__all__ = ["OrchestrationAgent"]
