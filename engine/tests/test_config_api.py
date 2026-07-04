from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from migrations_engine.app import app
from migrations_engine.api.deps import get_current_user
from migrations_engine.routes import config as config_route_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_ai_model_defaults_requires_authentication() -> None:
    response = client.get("/config/ai-model-defaults")
    assert response.status_code == 401


def test_ai_model_defaults_returns_resolved_models(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_config = SimpleNamespace(
        models=SimpleNamespace(
            planning="planning-model",
            review="review-model",
            implementation="implementation-model",
        ),
        migration_models=SimpleNamespace(
            pii_review="pii-model",
            field_mapping="field-model",
            lookup_mapping="lookup-model",
            script_generation="script-generation-model",
            script_correction="script-correction-model",
            schema_dependency="schema-dependency-model",
            impact_analysis="impact-model",
            feed_analysis="feed-analysis-model",
        ),
    )
    monkeypatch.setattr(config_route_module, "get_ai_config", lambda: fake_config)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id="user-1")

    response = client.get(
        "/config/ai-model-defaults",
        headers={"Authorization": "Bearer token-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "source": "engine.yaml",
        "platform_models": {
            "planning": "planning-model",
            "review": "review-model",
            "implementation": "implementation-model",
        },
        "migration_models": {
            "pii_review": "pii-model",
            "field_mapping": "field-model",
            "lookup_mapping": "lookup-model",
            "script_generation": "script-generation-model",
            "script_correction": "script-correction-model",
            "schema_dependency": "schema-dependency-model",
            "impact_analysis": "impact-model",
            "feed_analysis": "feed-analysis-model",
        },
    }
