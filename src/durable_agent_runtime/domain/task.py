"""Canonical task domain model — re-exports from plan module.

Task is defined in plan.py to avoid circular imports since Plan references Task
and Task is conceptually part of the plan structure. This module exists for the
canonical directory layout specified in Section 8.
"""

from .plan import Task  # noqa: F401
