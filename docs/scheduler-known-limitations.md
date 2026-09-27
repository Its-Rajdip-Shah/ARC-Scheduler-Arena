# Scheduler Known Limitations

> Status: productionisation scaffold.

Current known limitations include:

- heuristic search does not prove global optimality;
- dense worlds can exhaust the evaluation budget;
- some better load distributions have been demonstrated outside the current
  heuristic result;
- real-user sensitivity to schedule churn has not yet been measured;
- production latency has not yet been benchmarked on integrated ARC workloads.

These are not hard-correctness failures.
