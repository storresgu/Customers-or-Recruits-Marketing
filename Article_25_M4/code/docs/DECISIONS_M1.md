# M1 implementation decisions — 25 September 2026

## Authority and scope

Implemented from the current Article_25_Especificacion_minima_v0.1.md
retrieved from the project's 02_Modelo_y_ODD folder. The original specification
is preserved. This module is version 0.1.0-m1, with specification version 0.1.

No changes were made to the proposed scenario parameters or experimental
design. The user authorized M1 implementation and verification. No full
simulation, 80-trajectory pilot, or sensitivity experiment was run.

## Concrete implementation conventions

1. All initial distributors are roots with enrollment month 0 and first
   operation in month 1. Financial histories are empty at initialization.
2. Root IDs are selected by uniform pseudorandom keyed priorities among
   nonisolated people, without replacement. No degree-based preference applies.
3. Social graphs are generated once. Disconnected graphs are retained;
   an insufficient number of eligible roots raises an explicit error.
4. Every person's three Beta(2,2) attributes are generated independently
   before any later enrollment. Changing initial commercial roles does not
   change the same person's attributes.
5. Two extra history fields, customer_since_month and state_since_month,
   support the specification's same-month transition restrictions in M2.
   They do not introduce new behavioral assumptions.
6. The homogeneous_agents switch exposes the specified robustness variant;
   when true, all three attributes equal 0.5. Graphs and root selection retain
   the same seeds and are unaffected.
7. State contracts permit exactly U→C, U→D, C→U, C→D, and D→I.
   Remaining in the same state is not a transition. M1 validates contracts
   without executing stochastic behavior.
8. The sponsor graph initially contains roots only. Validators also accept
   correctly constructed later histories and retain links after exits.
   A sponsor must have been eligible to operate when the recruit enrolled.
9. A social degree of zero and zero initial distributors are allowed for
   extreme verification. Positive roots with no eligible social neighbors
   are rejected. Nonzero initial customers and qualification purchasing
   remain unsupported.
10. Snapshots require exact schema/model/randomness versions. Version
    migration must be explicit. Export paths never overwrite an existing run.

## Verification limits

- Sponsor evolution and customer states were checked with manual fixtures,
  not a functioning commercial scheduler.
- Clone and snapshot tests verify the M1 state; future modules must extend
  the snapshot whenever they add transaction ledgers or evolving histories.
- Probability equations, repurchase behavior, volume categories, commission
  calculations, churn decisions, and recruitment-shock effects are not M1
  capabilities and have not been verified here.
- Numerical reproducibility is established for the recorded environment.
  The package was not tested on every operating system or dependency version.
- No empirical calibration or validation claim is made.

The next implementation milestone is M2; the publication requirements and
15 December 2026 manuscript target remain unchanged.
