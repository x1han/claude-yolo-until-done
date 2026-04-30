# Failure Behavior

When any gate fails:

- say the workflow cannot advance
- identify the failed stage
- identify the exact missing or failed runtime check, artifact, field, gate, or verification result
- limit work to diagnosis, repair, regeneration, re-verification, and state repair
- do not claim completion, approval, or readiness to stop

When a gate passes:

- say which stage passed
- name the hook result, artifact, or state update proving it
- move only to the next stage permitted by the run bundle

If context is compressed or partially restored:

- reload the required policy files for the active stage
- reload `<run-root>/run_state.json`
- reload the current plan path from `run_state.json`
- resume from disk state instead of memory
