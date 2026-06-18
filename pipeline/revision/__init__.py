"""Revision planning and book autopsy utilities."""

from pipeline.revision.book_autopsy import build_book_revision_backlog
from pipeline.revision.models import AnalyzedScene, BookRunContext, RevisionIssue
from pipeline.revision.revision_compare import compare_revision_outputs
from pipeline.revision.targeted_packets import build_targeted_revision_packets

__all__ = [
    "AnalyzedScene",
    "BookRunContext",
    "RevisionIssue",
    "build_book_revision_backlog",
    "build_targeted_revision_packets",
    "compare_revision_outputs",
]
