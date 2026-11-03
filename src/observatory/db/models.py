"""Versioned relational model with provenance on every transformed record.

Column comments double as the data dictionary (``observatory.db.dictionary``
renders ``docs/data-dictionary.md`` from this module), so the documentation
cannot drift from the schema.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from observatory.db.types import JSONType, VectorType


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ProvenanceMixin:
    """Fields required by section 3 for every transformed record."""

    original_id: Mapped[str | None] = mapped_column(String(255), comment="Identifier in the original source")
    original_text: Mapped[str | None] = mapped_column(Text, comment="Text exactly as published by the source")
    normalized_text: Mapped[str | None] = mapped_column(Text, comment="Text after normalization rules")
    language: Mapped[str | None] = mapped_column(String(16), comment="BCP-47 language of original_text")
    translation_method: Mapped[str | None] = mapped_column(
        String(64), comment="none | source_official | machine:<model> | manual"
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), comment="SHA-256 of original_text")
    transformation_rules: Mapped[dict | None] = mapped_column(
        JSONType, comment="Ordered list of normalization/transformation rules applied"
    )
    confidence: Mapped[float | None] = mapped_column(Float, comment="0-1 confidence of the transformation")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, comment="True only for synthetic test fixtures")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- sources
class License(Base):
    __tablename__ = "license"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    spdx_id: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)


class SourceDataset(Base):
    __tablename__ = "source_dataset"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, comment="CBO | ESCO | ONET | AEI | ...")
    name: Mapped[str] = mapped_column(String(255))
    publisher: Mapped[str] = mapped_column(String(255))
    homepage: Mapped[str | None] = mapped_column(String(512))
    versions: Mapped[list[SourceVersion]] = relationship(back_populates="dataset")


class SourceVersion(Base):
    __tablename__ = "source_version"
    __table_args__ = (UniqueConstraint("dataset_id", "version", "file_sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("source_dataset.id"))
    version: Mapped[str] = mapped_column(String(64), comment="Version as declared by the publisher")
    source_url: Mapped[str | None] = mapped_column(String(1024), comment="Exact URL or API endpoint used")
    retrieval_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retrieval_method: Mapped[str] = mapped_column(String(64), comment="download | api | manual_file")
    file_sha256: Mapped[str | None] = mapped_column(String(64), comment="Hash of raw file / response")
    license_id: Mapped[int | None] = mapped_column(ForeignKey("license.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    dataset: Mapped[SourceDataset] = relationship(back_populates="versions")
    license: Mapped[License | None] = relationship()


# --------------------------------------------------------------------------- occupations
class Occupation(ProvenanceMixin, Base):
    __tablename__ = "occupation"
    __table_args__ = (UniqueConstraint("taxonomy", "code", "source_version_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_version_id: Mapped[int] = mapped_column(ForeignKey("source_version.id"))
    taxonomy: Mapped[str] = mapped_column(String(16), comment="CBO | ESCO | ONET")
    code: Mapped[str] = mapped_column(String(255), comment="CBO code, ESCO URI or O*NET-SOC code")
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    group_code: Mapped[str | None] = mapped_column(String(64), comment="CBO family / ISCO unit group / SOC")
    qualification_level: Mapped[float | None] = mapped_column(
        Float, comment="Harmonized 0-1 qualification level (Job Zone / ISCO skill level)"
    )
    attributes: Mapped[dict | None] = mapped_column(
        JSONType, comment="Source-specific fields kept verbatim (job zone, ISCO code, conditions...)"
    )
    source_version: Mapped[SourceVersion] = relationship()
    aliases: Mapped[list[OccupationAlias]] = relationship(back_populates="occupation")
    tasks: Mapped[list[OccupationTask]] = relationship(back_populates="occupation")


class OccupationAlias(Base):
    __tablename__ = "occupation_alias"
    id: Mapped[int] = mapped_column(primary_key=True)
    occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    label: Mapped[str] = mapped_column(String(512))
    language: Mapped[str | None] = mapped_column(String(16))
    alias_type: Mapped[str] = mapped_column(String(32), comment="preferred | alternative | synonym | reported")
    occupation: Mapped[Occupation] = relationship(back_populates="aliases")


class OccupationSourceMapping(Base):
    """Crosswalk proposal/decision between two occupations of different taxonomies."""

    __tablename__ = "occupation_source_mapping"
    __table_args__ = (UniqueConstraint("source_occupation_id", "target_occupation_id", "methodology_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    target_occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    method: Mapped[str] = mapped_column(String(64), comment="official_code | composite_v0 | manual")
    title_similarity: Mapped[float | None] = mapped_column(Float)
    task_similarity: Mapped[float | None] = mapped_column(Float)
    skill_similarity: Mapped[float | None] = mapped_column(Float)
    hierarchy_consistency: Mapped[float | None] = mapped_column(Float)
    qualification_consistency: Mapped[float | None] = mapped_column(Float)
    mapping_confidence: Mapped[float] = mapped_column(Float)
    confidence_class: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16), default="proposed", comment="proposed | accepted | rejected | edited | split | merged"
    )
    rules_applied: Mapped[dict | None] = mapped_column(JSONType)
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    methodology_version: Mapped[str] = mapped_column(String(32))
    justification: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    source_occupation: Mapped[Occupation] = relationship(foreign_keys=[source_occupation_id])
    target_occupation: Mapped[Occupation] = relationship(foreign_keys=[target_occupation_id])
    history: Mapped[list[CrosswalkChange]] = relationship(back_populates="mapping")


class CrosswalkChange(Base):
    __tablename__ = "crosswalk_change"
    id: Mapped[int] = mapped_column(primary_key=True)
    mapping_id: Mapped[int] = mapped_column(ForeignKey("occupation_source_mapping.id"))
    action: Mapped[str] = mapped_column(String(32), comment="create | accept | reject | edit | split | merge")
    before: Mapped[dict | None] = mapped_column(JSONType)
    after: Mapped[dict | None] = mapped_column(JSONType)
    actor: Mapped[str] = mapped_column(String(255))
    justification: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    mapping: Mapped[OccupationSourceMapping] = relationship(back_populates="history")


# --------------------------------------------------------------------------- tasks
class Task(ProvenanceMixin, Base):
    __tablename__ = "task"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_version_id: Mapped[int] = mapped_column(ForeignKey("source_version.id"))
    unit_type: Mapped[str] = mapped_column(
        String(32), comment="onet_task | onet_emerging_task | esco_skill | cbo_activity"
    )
    statement: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str | None] = mapped_column(String(32), comment="O*NET Core/Supplemental; CBO area")
    attributes: Mapped[dict | None] = mapped_column(JSONType)
    source_version: Mapped[SourceVersion] = relationship()


class OccupationTask(Base):
    """Task ratings preserved per scale (never summed raw) plus the derived weight."""

    __tablename__ = "occupation_task"
    __table_args__ = (UniqueConstraint("occupation_id", "task_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id"))
    importance: Mapped[float | None] = mapped_column(Float, comment="O*NET IM (1-5), raw")
    importance_n: Mapped[int | None] = mapped_column(Integer)
    importance_se: Mapped[float | None] = mapped_column(Float)
    importance_ci_low: Mapped[float | None] = mapped_column(Float)
    importance_ci_high: Mapped[float | None] = mapped_column(Float)
    importance_suppressed: Mapped[bool | None] = mapped_column(Boolean)
    relevance: Mapped[float | None] = mapped_column(Float, comment="O*NET RT (0-100), raw")
    relevance_n: Mapped[int | None] = mapped_column(Integer)
    relevance_suppressed: Mapped[bool | None] = mapped_column(Boolean)
    frequency_distribution: Mapped[dict | None] = mapped_column(
        JSONType, comment="O*NET FT: {category: percent} for categories 1-7, raw"
    )
    frequency_suppressed: Mapped[bool | None] = mapped_column(Boolean)
    weight_raw: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float, comment="Normalized within occupation (sum = 1)")
    weight_method: Mapped[str | None] = mapped_column(String(64))
    missing_flags: Mapped[dict | None] = mapped_column(JSONType)
    occupation: Mapped[Occupation] = relationship(back_populates="tasks")
    task: Mapped[Task] = relationship()


# --------------------------------------------------------------------------- skills / knowledge / abilities
class _DescriptorMixin(ProvenanceMixin):
    id: Mapped[int] = mapped_column(primary_key=True)
    source_version_id: Mapped[int] = mapped_column(ForeignKey("source_version.id"))
    taxonomy: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)


class Skill(_DescriptorMixin, Base):
    __tablename__ = "skill"
    skill_type: Mapped[str | None] = mapped_column(
        String(32), comment="skill | competence | transversal | digital | green | essential | transferable"
    )


class Knowledge(_DescriptorMixin, Base):
    __tablename__ = "knowledge"


class Ability(_DescriptorMixin, Base):
    __tablename__ = "ability"


class OccupationSkill(Base):
    __tablename__ = "occupation_skill"
    id: Mapped[int] = mapped_column(primary_key=True)
    occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.id"))
    relation: Mapped[str] = mapped_column(String(32), comment="essential | optional | rated")
    scale_id: Mapped[str | None] = mapped_column(String(8))
    value: Mapped[float | None] = mapped_column(Float)
    suppressed: Mapped[bool | None] = mapped_column(Boolean)


class OccupationDescriptorValue(Base):
    """Any O*NET descriptor rating (knowledge, ability, work context, work activity), scale preserved."""

    __tablename__ = "occupation_descriptor_value"
    id: Mapped[int] = mapped_column(primary_key=True)
    occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    domain: Mapped[str] = mapped_column(
        String(32), comment="knowledge | ability | work_context | work_activity | skill"
    )
    element_id: Mapped[str] = mapped_column(String(64))
    element_name: Mapped[str] = mapped_column(String(512))
    scale_id: Mapped[str] = mapped_column(String(8))
    category: Mapped[str | None] = mapped_column(String(8))
    value: Mapped[float | None] = mapped_column(Float)
    n: Mapped[int | None] = mapped_column(Integer)
    standard_error: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    suppressed: Mapped[bool | None] = mapped_column(Boolean)
    not_relevant: Mapped[bool | None] = mapped_column(Boolean)
    data_date: Mapped[str | None] = mapped_column(String(16))
    domain_source: Mapped[str | None] = mapped_column(String(64))


class TaskSkill(Base):
    __tablename__ = "task_skill"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id"))
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skill.id"))
    element_id: Mapped[str | None] = mapped_column(String(64), comment="e.g. O*NET DWA element id")
    relation: Mapped[str] = mapped_column(String(32), comment="dwa | semantic | manual")
    score: Mapped[float | None] = mapped_column(Float)


# --------------------------------------------------------------------------- AI capabilities
class AICapabilityVersion(Base):
    __tablename__ = "ai_capability_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    released_at: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)


class AICapability(Base):
    __tablename__ = "ai_capability"
    __table_args__ = (UniqueConstraint("version_id", "capability_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("ai_capability_version.id"))
    capability_id: Mapped[str] = mapped_column(String(32))
    family: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(255))
    definition: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONType, comment="Full capability record as in the YAML")
    content_hash: Mapped[str] = mapped_column(String(64))


class AIEvidence(Base):
    __tablename__ = "ai_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_type: Mapped[str] = mapped_column(
        String(32), comment="observed_usage | benchmark | experiment | expert_prior"
    )
    task_id: Mapped[int | None] = mapped_column(ForeignKey("task.id"))
    capability_pk: Mapped[int | None] = mapped_column(ForeignKey("ai_capability.id"))
    source_version_id: Mapped[int | None] = mapped_column(ForeignKey("source_version.id"))
    reference_id: Mapped[str | None] = mapped_column(String(128), comment="Key in references.json")
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict | None] = mapped_column(JSONType)
    peer_reviewed: Mapped[bool | None] = mapped_column(Boolean)
    match_method: Mapped[str | None] = mapped_column(String(64))


# --------------------------------------------------------------------------- embeddings
class Embedding(Base):
    __tablename__ = "embedding"
    __table_args__ = (UniqueConstraint("cache_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), comment="sha256(model_key|params|language|text_hash)")
    model_key: Mapped[str] = mapped_column(String(255), comment="provider/model@revision")
    dimension: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict | None] = mapped_column(JSONType)
    language: Mapped[str | None] = mapped_column(String(16))
    text_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    vector: Mapped[list[float]] = mapped_column(VectorType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SemanticMapping(Base):
    __tablename__ = "semantic_mapping"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id"))
    capability_pk: Mapped[int] = mapped_column(ForeignKey("ai_capability.id"))
    model_key: Mapped[str] = mapped_column(String(255))
    raw_similarity: Mapped[float] = mapped_column(Float)
    negative_similarity: Mapped[float | None] = mapped_column(Float)
    calibrated_similarity: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(32))
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("exposure_assessment.id"))


# --------------------------------------------------------------------------- methodology / exposure
class MethodologyVersion(Base):
    __tablename__ = "methodology_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    released_at: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class ExposureAssessment(Base):
    __tablename__ = "exposure_assessment"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64))
    occupation_id: Mapped[int] = mapped_column(ForeignKey("occupation.id"))
    methodology_version: Mapped[str] = mapped_column(String(32))
    methodology_fingerprint: Mapped[str] = mapped_column(String(64))
    capability_version: Mapped[str] = mapped_column(String(32))
    embedding_model: Mapped[str] = mapped_column(String(255))
    embedding_calibration: Mapped[dict | None] = mapped_column(JSONType)
    pipeline_version: Mapped[dict] = mapped_column(JSONType, comment="git commit, dirty flag, source tree hash")
    scores: Mapped[dict] = mapped_column(JSONType, comment="OAE, OAP, OAuP, OTP")
    intervals: Mapped[dict | None] = mapped_column(JSONType, comment="Monte Carlo 90% intervals")
    quality: Mapped[dict | None] = mapped_column(JSONType, comment="coverage, source quality, crosswalk quality")
    sensitivity: Mapped[dict | None] = mapped_column(JSONType)
    limitations: Mapped[list | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    occupation: Mapped[Occupation] = relationship()
    components: Mapped[list[ExposureComponent]] = relationship(back_populates="assessment")


class ExposureComponent(Base):
    """Per-task result: the 14 dimensions, the four synthetic outputs and the explanation."""

    __tablename__ = "exposure_component"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("exposure_assessment.id"))
    occupation_task_id: Mapped[int] = mapped_column(ForeignKey("occupation_task.id"))
    task_weight: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict] = mapped_column(JSONType, comment="E1..E14 values")
    dimension_sources: Mapped[dict] = mapped_column(JSONType, comment="Where each dimension came from")
    technical_exposure: Mapped[float] = mapped_column(Float)
    automation_potential: Mapped[float] = mapped_column(Float)
    augmentation_potential: Mapped[float] = mapped_column(Float)
    transformation_potential: Mapped[float] = mapped_column(Float)
    task_class: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    justification: Mapped[str] = mapped_column(Text)
    matched_capabilities: Mapped[list] = mapped_column(JSONType)
    evidence: Mapped[list | None] = mapped_column(JSONType)
    barriers: Mapped[list | None] = mapped_column(JSONType)
    missing_flags: Mapped[list | None] = mapped_column(JSONType)
    assessment: Mapped[ExposureAssessment] = relationship(back_populates="components")
    occupation_task: Mapped[OccupationTask] = relationship()


# --------------------------------------------------------------------------- curriculum (phase 8 scaffold)
class Curriculum(ProvenanceMixin, Base):
    __tablename__ = "curriculum"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    institution: Mapped[str | None] = mapped_column(String(512))
    level: Mapped[str | None] = mapped_column(String(64))
    total_hours: Mapped[float | None] = mapped_column(Float)
    document_path: Mapped[str | None] = mapped_column(String(1024))


class ProfessionalProfile(Base):
    __tablename__ = "professional_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curriculum.id"))
    text: Mapped[str] = mapped_column(Text)
    linked_occupation_ids: Mapped[list | None] = mapped_column(JSONType)


class CurriculumUnit(Base):
    __tablename__ = "curriculum_unit"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curriculum.id"))
    title: Mapped[str] = mapped_column(String(512))
    hours: Mapped[float | None] = mapped_column(Float)
    contents: Mapped[str | None] = mapped_column(Text)
    assessment_strategies: Mapped[str | None] = mapped_column(Text)


class CurriculumCompetency(Base):
    __tablename__ = "curriculum_competency"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curriculum.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("curriculum_unit.id"))
    kind: Mapped[str] = mapped_column(String(32), comment="general | specific | technical | socioemotional")
    text: Mapped[str] = mapped_column(Text)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class CurriculumLearningOutcome(Base):
    __tablename__ = "curriculum_learning_outcome"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curriculum.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("curriculum_unit.id"))
    text: Mapped[str] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class CurriculumExposureAssessment(Base):
    __tablename__ = "curriculum_exposure_assessment"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(ForeignKey("curriculum.id"))
    methodology_version: Mapped[str] = mapped_column(String(32))
    indices: Mapped[dict] = mapped_column(JSONType)
    recommendations: Mapped[list] = mapped_column(JSONType)
    traceability: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- validation / governance
class ValidationSample(Base):
    """One label for one benchmark pair by one annotator (human annotations are never mixed with AI drafts)."""

    __tablename__ = "validation_sample"
    __table_args__ = (Index("ix_validation_sample_item", "sample_set", "item_id", "right_ref", "annotator"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_set: Mapped[str] = mapped_column(String(64))
    item_id: Mapped[str | None] = mapped_column(String(64), comment="Benchmark item id (e.g. tc-001)")
    item_type: Mapped[str] = mapped_column(String(32), comment="task_capability | occupation_pair")
    left_text: Mapped[str] = mapped_column(Text)
    right_ref: Mapped[str] = mapped_column(String(255))
    label: Mapped[int] = mapped_column(Integer, comment="2 related | 1 partial | 0 unrelated")
    tags: Mapped[list | None] = mapped_column(JSONType)
    language: Mapped[str] = mapped_column(String(16))
    annotator: Mapped[str] = mapped_column(String(64))
    is_gold: Mapped[bool] = mapped_column(Boolean, default=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    comment: Mapped[str | None] = mapped_column(Text, comment="Annotator's free-text note")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExpertReview(Base):
    __tablename__ = "expert_review"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(255))
    reviewer: Mapped[str] = mapped_column(String(255))
    decision: Mapped[str] = mapped_column(String(32))
    score: Mapped[float | None] = mapped_column(Float)
    justification: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SystemRelease(Base):
    __tablename__ = "system_release"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    methodology_version: Mapped[str] = mapped_column(String(32))
    capability_version: Mapped[str] = mapped_column(String(32))
    pipeline_version: Mapped[dict] = mapped_column(JSONType)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict | None] = mapped_column(JSONType)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
