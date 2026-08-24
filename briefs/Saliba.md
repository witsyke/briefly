---
priority: high
tags: active sensing, epidemic state estimation, particle-filter RNN, agent-based
  modeling, optimal test allocation
---

## Summary

This paper tackles epidemic state estimation—inferring the true (unobserved) proportion of infectious individuals across N regions over time—by jointly learning a state estimator and a test-allocation policy. It adapts Particle Filter Recurrent Neural Networks (PF-RNNs) to output both a next-step prevalence estimate and the number of prevalence tests to assign to each region for the next time step, under a per-region test budget (1 to M tests). Training uses a detailed agent-based epidemic simulator (EpiHiper) run over synthetic populations of 12 Virginia counties across a range of transmissibility values, so the model learns disease transition dynamics without ever seeing ground-truth state directly. The reward combines estimation error against test results, a test-cost penalty (tunable via weight η), and particle-set entropy/variance to encourage uncertainty reduction. Results show the learned "with action" test-allocation policy achieves near-best RMSE using only ~4 tests/day per region on average, roughly a 30x reduction in tests versus fixed/random allocation for equivalent accuracy, and a "multi-trajectory" variant trained across transmissibility values transfers reasonably to unseen disease parameters with only 3 tests/day.

## Takeaways

- Frames "where to sense next" as a joint learned policy: the same recurrent architecture (PF-RNN) outputs both the state estimate and the next allocation of a scarce, spatially-distributed sampling budget (tests per county) — a direct template for spatio-temporal active-design problems where you must pick location AND accept the resulting observation feeds back into the estimator.
- Uses an entropy/variance term over particle-filter hidden states as a proxy reward for "reduce estimator uncertainty," sidestepping the intractability of exact entropy computation over particle sets — a reusable trick if entropy/information-gain terms are hard to compute exactly in your own active-learning objective.
- Trains entirely on a high-fidelity agent-based simulator (never on ground-truth real data) so the transition model is learned from simulation while allocation decisions are validated against simulated "ground truth" — relevant if your project also needs an ABM-in-the-loop training pipeline to avoid needing real labeled disease-state data.
- Demonstrates transfer to unseen dynamics only when trained across a *range* of parameter values (multi-trajectory scenario); a single-trajectory-trained policy is not shown to generalize — worth noting if your setting needs robustness to shifting disease/process parameters.
- Objective design separates accuracy, cost, and uncertainty into weighted terms (η for cost, γ for an ELBO-like regularizer) — a concrete worked example of balancing exploration cost vs. estimation accuracy that could inform reward shaping for your own resource-constrained optimal-design formulation.
- Limitation to note: the method only allocates tests across space at each fixed, regular time step (no choice over *when* to observe, and a minimum of 1 test/region/step is hard-coded) — it does not address the temporal component of "next time point" selection that your project also cares about.
