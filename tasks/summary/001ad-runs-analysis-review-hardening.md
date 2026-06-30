# Summary 001ad — Runs and Analysis Review Hardening

Locked down the remaining review concerns around run scoping and source-analysis behavior:

- Added a run API regression test proving `launch` and `resume` return `run_not_found` when
  called under the wrong project.
- Added a source-analysis service regression test proving the `field_mapping` adapter slot is
  requested.
- Kept the existing run snapshot pinning behavior under test, including the multi-lookup version
  dict.
- Kept the source-analysis synchronous 200 response shape under test.

Verification:

- `cd engine && PYTHONPATH=src pytest tests/test_runs_api.py -q`
- `cd engine && PYTHONPATH=src pytest tests/test_source_analysis_service.py tests/test_source_analysis_api.py -q`
- `python -m compileall engine/src engine/tests`
- `git diff --check`

Result:

- 2 run API tests passed
- 6 source-analysis tests passed
- compileall passed
- diff check passed
