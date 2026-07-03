# 001ao — Feed Comment Model + Thread

Implemented threaded feed comments end to end:

- added the `FeedComment` model and Alembic migration `0020_feed_comments`
- added `FeedCommentCreateRequest` and `FeedCommentResponse` schemas
- created `list_feed_comments` and `create_feed_comment` backend handlers
- exposed `GET /projects/{project_id}/feeds/{feed_id}/comments` and `POST /projects/{project_id}/feeds/{feed_id}/comments`
- added best-effort notification fan-out for central-team and stakeholder comments
- added the `FeedCommentThread` frontend component and `feeds-api` helpers

Verification:

- `PYTHONPATH=engine/src pytest engine/tests/test_feed_comments_api.py -q`
- `cd web && npm test -- --run feeds-api FeedCommentThread`
- `cd web && npm test -- --run`
- `set -a && source /Users/vjkotra/projects/katana/engine/.env && set +a && /Users/vjkotra/projects/katana/.venv/bin/python -m alembic upgrade head`

Result:

- backend comment tests: `13 passed`
- focused web tests: `23 passed`
- full web suite: `180 passed`

