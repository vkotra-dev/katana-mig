from __future__ import annotations

from types import SimpleNamespace

import pytest

from migrations_engine.ai.config import AIConfig, MigrationModelConfig, PlatformModelConfig, ProviderConfig, resolve_model
from migrations_engine.api.schemas import ModelPolicy, ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest


def _make_config() -> AIConfig:
    return AIConfig(
        models=PlatformModelConfig(
            planning="global-planning",
            review="global-review",
            implementation="global-implementation",
        ),
        migration_models=MigrationModelConfig(
            pii_review="global-pii-review",
            field_mapping="global-field-mapping",
            lookup_mapping="global-lookup-mapping",
            script_generation="global-script-generation",
            script_correction="global-script-correction",
            schema_dependency="global-schema-dependency",
            impact_analysis="global-impact-analysis",
            feed_analysis="global-feed-analysis",
        ),
        providers=ProviderConfig(
            anthropic_api_key_env="ANTHROPIC_API_KEY",
            openai_api_key_env="OPENAI_API_KEY",
        ),
    )


def _make_policy(**overrides: str | None) -> SimpleNamespace:
    values = {
        "pii_review": None,
        "field_mapping": None,
        "lookup_mapping": None,
        "script_generation": None,
        "script_correction": None,
        "schema_dependency": None,
        "impact_analysis": None,
        "feed_analysis": None,
        "planning": None,
        "review": None,
        "implementation": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("planning", "global-planning"),
        ("review", "global-review"),
        ("implementation", "global-implementation"),
        ("pii_review", "global-pii-review"),
        ("field_mapping", "global-field-mapping"),
        ("lookup_mapping", "global-lookup-mapping"),
        ("script_generation", "global-script-generation"),
        ("script_correction", "global-script-correction"),
        ("schema_dependency", "global-schema-dependency"),
        ("impact_analysis", "global-impact-analysis"),
        ("feed_analysis", "global-feed-analysis"),
    ],
)
def test_resolve_model_returns_global_when_policy_is_none(task: str, expected: str) -> None:
    assert resolve_model(task, None, _make_config()) == expected


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("planning", "global-planning"),
        ("review", "global-review"),
        ("implementation", "global-implementation"),
        ("pii_review", "global-pii-review"),
        ("field_mapping", "global-field-mapping"),
        ("lookup_mapping", "global-lookup-mapping"),
        ("script_generation", "global-script-generation"),
        ("script_correction", "global-script-correction"),
        ("schema_dependency", "global-schema-dependency"),
        ("impact_analysis", "global-impact-analysis"),
        ("feed_analysis", "global-feed-analysis"),
    ],
)
def test_resolve_model_returns_global_when_field_is_none(task: str, expected: str) -> None:
    assert resolve_model(task, _make_policy(), _make_config()) == expected


@pytest.mark.parametrize(
    ("task", "override"),
    [
        ("planning", "project-planning"),
        ("review", "project-review"),
        ("implementation", "project-implementation"),
        ("pii_review", "project-pii-review"),
        ("field_mapping", "project-field-mapping"),
        ("lookup_mapping", "project-lookup-mapping"),
        ("script_generation", "project-script-generation"),
        ("script_correction", "project-script-correction"),
        ("schema_dependency", "project-schema-dependency"),
        ("impact_analysis", "project-impact-analysis"),
        ("feed_analysis", "project-feed-analysis"),
    ],
)
def test_resolve_model_returns_override_when_field_is_set(task: str, override: str) -> None:
    policy = _make_policy(**{task: override})
    assert resolve_model(task, policy, _make_config()) == override


def test_resolve_model_rejects_unknown_task() -> None:
    with pytest.raises(ValueError, match="unknown_task"):
        resolve_model("unknown_task", None, _make_config())


def test_project_model_policy_is_typed_when_parsed() -> None:
    request = ProjectCreateRequest(
        name="Project",
        model_policy={"planning": "project-planning", "review": None},
    )

    assert request.model_policy is not None
    assert request.model_policy.__class__.__name__ == "ModelPolicy"
    assert request.model_policy.planning == "project-planning"
    assert request.model_policy.review is None


def test_project_schema_model_policy_fields_use_the_typed_model() -> None:
    expected = ModelPolicy | None

    assert ProjectResponse.model_fields["model_policy"].annotation == expected
    assert ProjectCreateRequest.model_fields["model_policy"].annotation == expected
    assert ProjectUpdateRequest.model_fields["model_policy"].annotation == expected
