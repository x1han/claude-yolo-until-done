# Completion Rules

This workflow may stop only when completion is positively verified.

Minimum completion conditions:

- `state.json` says the workflow is `complete`
- the durable review verdict is `approve`
- the review contains concrete acceptance basis
- required worker submission evidence is still present
- `trace.md` records the watcher review and watcher completion events
- the corresponding completion validator passes
- the run is either explicitly cleaned up at completion or still guarded by the mounted prompt gate until cleanup is chosen

The workflow may not stop just because:

- code was changed
- one test passed
- one file was edited
- the worker wrote a convincing summary
- the remaining work feels small
