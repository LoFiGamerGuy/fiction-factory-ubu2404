"""Pydantic models for structured agent outputs (Instructor-enforced)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Dirty draft produced by WriterAgent."""

    draft_text: str = Field(description="The generated scene prose.")
    word_count: int = Field(default=0, description="Approximate word count.")
    scene_id: str = Field(default="", description="Scene identifier.")


class EditorOutput(BaseModel):
    """Edited scene produced by EditorAgent."""

    edited_text: str = Field(description="The edited scene prose.")
    nofly_violations: int = Field(default=0)
    structural_flags: int = Field(default=0)
    structural_weighted_score: int = Field(default=0)
    edit_passes: int = Field(default=0)
    is_clean: bool = Field(default=True)


class QualityResult(BaseModel):
    """Quality Gate decision produced by QualityAgent."""

    needs_review: bool = Field(default=False)
    tier: str = Field(default="pass", description="pass | warn | fail")
    nofly_violations: int = Field(default=0)
    structural_flags: int = Field(default=0)
    structural_weighted_score: int = Field(default=0)
    sensitivity_violation: bool = Field(default=False)
    scene_id: str = Field(default="")
    notes: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
