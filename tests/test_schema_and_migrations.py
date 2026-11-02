from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from observatory.config import PROJECT_ROOT
from observatory.db.dictionary import render_data_dictionary
from observatory.db.models import Base

REQUIRED_TABLES = {
    "source_dataset",
    "source_version",
    "license",
    "occupation",
    "occupation_alias",
    "occupation_source_mapping",
    "task",
    "occupation_task",
    "skill",
    "knowledge",
    "ability",
    "occupation_skill",
    "task_skill",
    "ai_capability",
    "ai_capability_version",
    "ai_evidence",
    "embedding",
    "semantic_mapping",
    "exposure_assessment",
    "exposure_component",
    "curriculum",
    "professional_profile",
    "curriculum_competency",
    "curriculum_learning_outcome",
    "curriculum_unit",
    "curriculum_exposure_assessment",
    "validation_sample",
    "expert_review",
    "methodology_version",
    "system_release",
}


def test_model_covers_required_entities():
    assert REQUIRED_TABLES <= set(Base.metadata.tables)


def test_transformed_records_carry_provenance_columns():
    for name in ("occupation", "task", "skill", "knowledge", "ability", "curriculum"):
        cols = set(Base.metadata.tables[name].columns.keys())
        assert {
            "original_id",
            "original_text",
            "normalized_text",
            "language",
            "translation_method",
            "content_hash",
            "transformation_rules",
            "confidence",
            "created_at",
            "is_synthetic",
        } <= cols, name


def test_alembic_upgrade_and_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mig.sqlite').as_posix()}"
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}


def test_data_dictionary_is_up_to_date():
    path = PROJECT_ROOT / "docs" / "data-dictionary.md"
    assert path.read_text(encoding="utf-8") == render_data_dictionary(), (
        "run: python -m observatory.cli data-dictionary"
    )
