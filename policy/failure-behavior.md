# Failure Behavior

When a validator or guard fails:

- say the workflow cannot advance
- identify the exact missing or failed state field, trace evidence, hook result, or verification result
- limit work to diagnosis, repair, regeneration, re-verification, and state repair
- do not claim completion, approval, or readiness to stop

When a validator passes:

- say which validator or guard passed
- name the hook result, trace evidence, or state update proving it
- move only to the next worker/watcher action permitted by the durable state

If context is compressed or partially restored:

- reload the required policy files
- reload `<run-root>/state.json`
- reload the current plan path from `state.json`
- resume from disk state instead of memory
