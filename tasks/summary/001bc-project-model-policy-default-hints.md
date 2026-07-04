# Task 001bc Summary

- Exposed the resolved AI model defaults from `engine/config/engine.yaml` via a new authenticated backend endpoint `GET /config/ai-model-defaults`.
- Created the client fetch helper `getAiModelDefaults` in `web/lib/ai-model-defaults-api.ts`.
- Integrated model defaults into the project edit form, rendering the active global default model name as helper text under each override input.
- Added a read-only model policy section in the project detail view showing the effective model name and source (project override vs. global default).
- Verified backend and frontend test coverage. All tests pass successfully.
