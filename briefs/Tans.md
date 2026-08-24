---
priority: high
tags: active surveillance, spatio-temporal, information gain, sentinel selection,
  epidemiology
---

## Summary

This paper proposes IGDAS, an information-guided adaptive learning approach for dynamically selecting which spatio-temporal locations to monitor in infectious disease surveillance under limited resources, rather than relying on a fixed set of sentinel sites. It first trains a variational (probabilistic) neural network on incomplete spatio-temporal case data, using masking of missing entries and an observed-data-only loss, to model spatial-temporal correlations and produce a Gaussian latent representation of infection counts. From the resulting covariance structure, it computes (conditional) mutual information between candidate monitoring points and the rest of the system as an information-gain score, combines this with an infection-coverage score via a weighted sum, and greedily selects K targets per time step; unmonitored locations are then inferred via conditional Gaussian posterior updating. On a synthetic SEIR-network dataset and two real-world datasets (Yunnan malaria surveillance, 2021 US COVID-19 state-level testing), IGDAS consistently achieves lower RMSE/MAE than static/linear-inverse baselines (GPMI, FrameSense, MNEP, MPME, SNMA), and the paper shows the informativeness/coverage trade-off weight has a mid-range optimum that varies with the monitoring budget.

## Takeaways

- Directly relevant reference architecture: probabilistic (VAE-style) spatio-temporal model → per-candidate mutual-information/conditional-mutual-information score → greedy selection under a cardinality budget K → conditional Gaussian posterior inference of unmonitored sites — a template applicable to choosing next time/location/both under resource constraints.
- The information-gain criterion (Eq. 4) is computed analytically from the estimated joint Gaussian covariance (Σ = W diag(σ) Wᵀ) via log-determinant ratios, avoiding the need to retrain the model per candidate evaluation — worth considering for efficient design-score computation in an active-learning loop.
- They explicitly combine an informativeness score with a task-relevant "coverage" score (estimated infection risk) via a tunable weighted sum (Eq. 5), showing pure informativeness-based selection underperforms a blended objective — a reminder that optimal-design objectives beyond pure information gain (e.g., decision-relevant coverage) can materially change inference accuracy.
- Missing-data handling is simplistic (mask with -1, loss computed only over observed entries) and explicitly flagged by the authors as a limitation — an area for improvement if adopting this pipeline.
- Selection is done via single-step greedy search without accounting for downstream accessibility/operational constraints between chosen sites (acknowledged limitation) — relevant if the target application has non-trivial costs coupling location choices (e.g., travel/logistics between sites).
- Reported per-step planning+inference runtime (~0.78s for K=10 on 51-state COVID data) suggests the greedy MI-based approach is computationally practical for moderate N, useful as a rough feasibility benchmark.
