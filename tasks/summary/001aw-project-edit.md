# Summary 001aw — Project Edit

- Added a routeable project edit screen under `/projects/[id]/edit`.
- Added a structured `SamplePolicy` contract with `strategy`, `max_rows`, and `stratified_column`.
- Added `destination_schema` to the project domain config and exposed it in the edit form and detail view.
- Replaced the sample policy JSON textarea with structured controls.
- Hid execution environments from the edit screen while preserving the existing payload value.
- Updated project API mappings, backend schema, docs, and tests to match the new contract.
- Verified the backend project CRUD tests and the focused web test slice pass.
