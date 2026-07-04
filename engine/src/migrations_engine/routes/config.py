from __future__ import annotations

from fastapi import APIRouter, Depends

from ..ai.config import get_ai_config
from ..api.deps import get_current_user
from ..api.schemas import (
    AIModelDefaultsResponse,
    MigrationModelDefaults,
    PlatformModelDefaults,
)
from ..db.models import User

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/ai-model-defaults", response_model=AIModelDefaultsResponse)
def get_ai_model_defaults(actor: User = Depends(get_current_user)) -> AIModelDefaultsResponse:
    _ = actor
    config = get_ai_config()
    return AIModelDefaultsResponse(
        source="engine.yaml",
        platform_models=PlatformModelDefaults(
            planning=config.models.planning,
            review=config.models.review,
            implementation=config.models.implementation,
        ),
        migration_models=MigrationModelDefaults(
            pii_review=config.migration_models.pii_review,
            field_mapping=config.migration_models.field_mapping,
            lookup_mapping=config.migration_models.lookup_mapping,
            script_generation=config.migration_models.script_generation,
            script_correction=config.migration_models.script_correction,
            schema_dependency=config.migration_models.schema_dependency,
            impact_analysis=config.migration_models.impact_analysis,
            feed_analysis=config.migration_models.feed_analysis,
        ),
    )
