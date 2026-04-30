# Required Superpowers

`superpowers` is a hard dependency for this workflow.

This workflow may run only after `superpowers` has already produced:

- an approved design or spec
- an approved implementation plan
- explicit execution gates
- explicit completion criteria
- explicit checkoff markers for stage or task progress
- an initialized run bundle under a chosen run root, with `artifacts/yolo/` as the default example layout

This workflow is the execution backend for a superpowers-created plan. It is not allowed to replace or imitate superpowers planning inside the execution session.

If `superpowers` is missing, or if the required plan artifacts were not produced by superpowers first, fail closed and stop.
