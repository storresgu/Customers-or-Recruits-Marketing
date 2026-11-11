# M3 implementation decisions — 0.3.0-m3

Date: 2026-09-27 UTC. Specification: 0.1.

1. **Reuse the established cash ledger.** M2 needed margins, one-level sponsor
   commissions, own purchases, operating/contact costs and one-time fees to apply
   its income-responsive exit rule. M3 adds reporting and experiments without
   changing these rules. A fresh M3 replay of the actual M2 N=2,000 control
   matches all 120 monthly records, 47,391 events, 5,296 transactions, 3,958
   earnings rows and the final population hash.

2. **Clone a complete preshock checkpoint.** Initialization and months 1–60 are
   computed once per pair. Both branches are exact deep copies before treatment
   is assigned. Only `recruitment_multiplier` changes. Histories, rolling incomes,
   exposure counters, seller/sponsor links, purchases and keyed randomness remain
   available. Control–control equality and shock-prefix equality are asserted.

3. **Keep a stable seed registry.** SHA-256 of the canonical JSON array
   `[article25-pair-seed-v1, master_seed, experiment_id, scenario_id, replicate_id]`
   yields a seed from its first eight hexadecimal characters (unsigned 32 bits).
   Pair seeds are distinct across the entire design; a collision rejects the
   design. Both branches share the seed; scenario ordering does not alter it.
   The existing event RNG schema and process identifiers remain unchanged.
   Changing experiment/scenario identifiers intentionally changes pair seeds.

4. **Track identities and immutability.** Pair IDs concatenate experiment,
   scenario and one-based replicate identifiers; run IDs add condition. Safe ID
   validation prevents path traversal and ambiguous double-underscore separators.
   Registries carry complete parameters, configuration hashes, source-code hashes,
   versions, seeds and status. Output directories use exclusive creation.
   Failed experiments are marked failed. Whole-batch resume is deferred; restart
   into a new destination. Checkpoints remain individually restartable.

5. **Specify earnings aggregation explicitly.** Window net earnings equal the
   arithmetic mean of the monthly earnings-cohort medians, with equal weight
   per month. All months must have a nonempty cohort; valid-month counts expose
   extinction. Paired net effects are differences only. Cumulative participant
   earnings are separately reported at the end of the run.

6. **Avoid survivorship filtering.** Participant rows contain all-ever enrollees,
   including exited people. A separate end-active subset reveals selection.
   `tenure_months` is elapsed time from enrollment to exit or observation end;
   `operating_months` counts eligible operating calendar months inclusively.
   Active participants are right-censored. The enrollment-month cash observation
   for a new recruit is not an operating month. No survival model is fitted.

7. **Preserve undefined and signed values.** Ratios need a positive control
   denominator. Zero/zero remains missing; raw values and differences remain
   available. Values above one and negative dependence indices are allowed.
   Conventional Gini is calculated only for nonnegative cumulative gross earnings;
   empty/all-zero cohorts return a reason. Signed net cash retains quantiles,
   IQR and loss/positive shares without shifting. Quantiles interpolate linearly
   at `(n-1)*p` (including singleton cohorts).

8. **Clarify additional reporting.** `repeat_contact_overlap` counts actual
   contacts beyond the month's distinct contacted people, across both channels
   and distributors. This does not override the existing within-distributor
   no-repeat rule. Historical sponsor depth is derived from the sponsor forest.
   Participant neighbor availability fields describe final social neighbors;
   they do not imply that an exited distributor operates. Full exposure counters
   for all people are retained in the final population snapshots.

9. **Keep uncertainty at the pair level.** Scenario/window/outcome summaries
   report number of valid paired effects, mean, median, IQR, simulation-distribution
   percentiles and the standard error of the mean difference. Missing differences
   and undefined ratios are counted. Duplicate pair/outcome records are rejected.
   No mean confidence interval or substantive regime threshold is asserted by M3.

10. **Prepare M4 explicitly.** The pilot design fixes four demand combinations,
    10 independent pairs each, N=500, 10 initial distributors, months 1–120 and
    shock month 61. `--prepare-only` validates and writes a registry without even
    initializing a simulation. M3 includes one distinct technical verification
    pair; it does not execute the 40-pair research pilot.

11. **Document the verification correction.** The first M3 suite found that
    numeric multipliers `1` and `1.0` could produce different serialized hashes
    despite identical dynamics. Registry multipliers now use a consistent float
    representation, and a null intervention retains the exact control field.
    The control–control test now passes, as do all 139 earlier tests and 65 new
    tests. No economic parameter or behavioral rule was changed to fix this.

12. **Retain the prototype's limits.** Full audit traces are retained in memory
    and exported for each pair. They are useful for verification and the small
    pilot; evaluate storage and runtime before large M5 designs. Parameter
    calibration, alternative structures, sensitivity, final regime definitions
    and manuscript conclusions remain later stages. M3 adds no empirical claims.
