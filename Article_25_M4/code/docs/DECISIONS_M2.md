# M2 decisions and specification traceability — 26 September 2026

## Implemented scope

Version 0.2.0-m2 implements the monthly rules in specification v0.1, sections
3.1–3.7, the exclusive purchase categories and simplified cash calculations in
section 4, and the monthly output subset in section 7. No baseline parameter,
behavioral coefficient, or social-network assumption was changed.

The source specification remains a dated design document. Its statement that
no simulations had been executed described the status when v0.1 was written;
M2's technical executions are recorded separately in this release.

## Necessary sequencing adjustment

The original milestone outline placed all accounting in M3, while M2 included
loss-responsive distributor exit. Those responsibilities are dependent:
exit needs the current month's net income after purchases and expenses.

M2 therefore implements and verifies the specified minimum cash ledger now.
This avoids either supplying invented incomes or silently disabling the loss
mechanism. The adjustment advances an already specified dependency; it adds no
new behavioral rule and does not expand the planned research design.

M3 will develop the experiment runner for matched pairs, common prefixes and
conditions; the scenario/replication/seed registry; shock-window differences
and resilience ratios; distribution and cumulative-cohort indicators; and
experiment-level output audits before the pilot.

## Implementation conventions and clarifications

1. The schedule follows retail acquisition before recruitment, then repurchase,
   participant purchases, cash settlement, and exits.
2. No-repeat contact means no repeated distributor/prospect pair within one month
   across both contact channels. Recontact in later months and overlap between
   different distributors remain allowed and logged.
3. Acquisition records the buyer as a nonparticipant at transaction time.
   Newly acquired customers are excluded from recruitment for that month.
   A customer enrolled during the recruitment phase cannot repurchase afterward.
4. Each participant entry purchase replaces personal consumption in the enrollment
   month, including when entry quantity is zero. Seed entry purchases and fees are
   handled in month 1. Seed entrant tags cover months 1–3; ordinary entrants use
   enrollment month through enrollment month + 2.
5. Entrant tags apply only to participant purchases. They overlap the entry/personal
   categories for reporting and are never added a second time to total volume.
6. Commission eligibility uses the start-of-month operating set, so an end-of-month
   exit cannot retroactively cancel a commission already earned in that month.
7. Cash histories contain available participant months, including enrollment-month
   costs, and retain only the configured rolling window. Cumulative income is
   preserved after exit.
8. Each monthly step uses a temporary population clone and commits only after
   conservation and accounting checks. The social graph's exact edge hash must
   remain unchanged.
9. Complete Simulation checkpoints are distinct from Population snapshots. Only
   the former preserve all audit traces. Both preserve the behavioral state.
10. M1 month-zero population snapshots are explicitly compatible with M2 because
    their schema and initialization mechanisms are unchanged. Historical M1 code
    and deliverables are retained. Unknown schema/model versions are rejected.

## Verification boundaries

The automated suite checks the monthly mechanisms, extreme cases, accounting
fixtures, short matched control/interruption trajectories, multiple seeds over
120 months, and exact restart. A 2,000-person, 120-month baseline trajectory is
included as technical evidence.

These executions are not the 80-trajectory pilot, the main experiment, global
sensitivity screening, or structural robustness experiments. They support
continuing to M3. They do not justify substantive findings from one trajectory.
