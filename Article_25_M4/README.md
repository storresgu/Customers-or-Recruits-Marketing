# Article 25 — M4 pilot v0.1

This package executes the already registered pilot with model 0.3.0-m3 and
specification 0.1. It retains the original four scenarios, 40 pair seeds,
80 branches, N=500 and 120 months. No behavioral parameter is changed.

## Reproduce

Extract the analysis/code archive and all four raw scenario archives into the
same parent directory. Their common `Article_25_M4/` root reconstructs the full
package; `pilot_v01/manifest.json` lists the SHA-256 of all raw result files.

From `Article_25_M4/`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r code/requirements.lock.txt
python -m pip install -e code --no-build-isolation --no-deps
python -m pytest code/tests -q
python -m article25.experiments --config code/configs/pilot_m3.json --output reproduced_pilot
python analysis/analyze_pilot.py --raw reproduced_pilot --prepared pilot_registration --output reproduced_analysis
```

To regenerate the descriptive figure, install the Matplotlib version recorded
in `figures/plot_environment.json`, then run:

```bash
python analysis/plot_pilot.py reproduced_analysis reproduced_figures
```

Model execution and analysis use the pinned NumPy version. Plotting may use its
separately recorded environment. Scientific values come from the exported CSV,
not from the plotting environment. Output directories for model/analysis must
be new. Timings and platform strings can vary between runs.

## Analysis choices

- Primary pilot comparison: late-window (109–120) external units, shock minus
  control, one difference per independent matched pair.
- Scenario mean effects have the sample standard error and an exploratory 95%
  percentile bootstrap interval for the mean: 20,000 resamples of whole pairs,
  seeded by SHA-256 of `article25-m4-bootstrap-v1:<scenario_id>` (first eight
  hexadecimal characters). This is not a simulation prediction interval.
  Ten pairs per scenario are too few for precise tail/rare-event claims.
- Median resilience uses only pairs with a positive control denominator; the
  number undefined is reported. A ratio of mean volumes is labeled separately
  and is not a mean or median of pair-level ratios.
- Extinction means zero end-of-month distributors by month 120. Because inactive
  state is absorbing, later recovery cannot occur in the implemented model.
- Local opportunity diagnostics report unused contact slots and available
  recruitment neighbors. Unused slots reflect eligibility, overlap and channel
  ordering; they are not by themselves proof of global market saturation.
  Final unused-pool summaries exclude undefined cases (no operating distributors).
- All-ever participant loss share is first calculated within each run, then
  averaged with equal weight across the ten runs in each condition/scenario.
  It is not a pooled participant loss share. End-active outcomes remain separate.
- The figure shows means and the interquartile range of ten trajectories per
  scenario/condition. Bands describe simulation variation, not confidence
  intervals. The line at month 61 marks the intervention.

`audit.json` checks the original seed registry, completion of all 40 pairs,
file integrity, conservation across all 9,600 monthly rows, absence of treated
postshock enrollment, preshock paired differences and cash reconciliation.
The complete model suite was rerun before execution; its report is included.

The pilot is an exploratory diagnostic stage. It does not authorize or replace
the main design, structural robustness or sensitivity experiments.
