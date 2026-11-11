# Article 25 — Minimum model specification v0.1

**Working title:** Customers or Recruits? An Agent-Based Model of Retail Demand, Recruitment Dependence, and Sustainability in Multilevel Marketing Networks.

**Project:** Article 25 — ABM — Santiago; Universidad Nacional de Colombia, Sede de La Paz.  
**Date:** 25 September 2026, America/Bogota.  
**Implementation language:** Python.  
**Status:** Proposed, implementation-ready starting specification. Numerical values and simplifications are exploratory decisions for review and verification; they are not final manuscript decisions. This document contains no executed simulations or research findings.  
**Source:** The supplied *Indications — Article 25 — ABM — Demand — Student Guide*. This specification operationalizes its core mechanisms while distinguishing the first implementation from the complete publication study.  
**Destination:** `02_Modelo_y_ODD/Article_25_Especificacion_minima_v0.1.md`.

## 1. Purpose and minimum scope

The model will examine when recurring purchases by nonparticipant customers support commercial activity after distributor recruitment slows or stops. The central distinction is between expansion of the distributor network and expansion of the external customer market. Neither distributor growth nor total product volume alone will be interpreted as evidence of stronger external demand.

The first implementation addresses three linked questions:

1. How do retail conversion and customer repurchase affect the development and persistence of external demand?
2. How do recruitment effort, finite social reach, participant purchasing, and distributor exit affect network and market growth?
3. How much do external retail sales and distributor activity change after a recruitment interruption, compared with a matched control?

The unit of analysis is a complete simulation run. Monthly observations, transactions, and individual agents are nested within runs; they are not independent experimental replications.

### Included in v0.1

- A finite population and an undirected social-contact network.
- Four mutually exclusive commercial states and a directed sponsor network.
- Limited contact opportunities divided between retail acquisition and recruitment.
- External first purchases, customer repurchases, participant personal consumption, and entry purchases recorded separately.
- A transparent retail margin, one paid sponsor level, operating expenses, and gross and net participant earnings.
- Customer exit, loss-responsive distributor exit, exposure fatigue, and competition for contacts.
- Matched recruitment-shock experiments, deterministic random-number management, and automated verification.

### Deferred mechanisms and their consequences

| Mechanism | Initial decision | Consequence and later work |
|---|---|---|
| Adaptive effort allocation | Fixed recruitment share within a scenario | Isolates demand and recruitment mechanisms. Add a documented adaptive rule as a structural robustness test; v0.1 cannot establish how incentive learning changes allocation. |
| Dynamic satisfaction, price sensitivity, and trust | Fixed product-fit heterogeneity and stochastic decisions | Avoids introducing several poorly identified behavioral submodels. Dynamic satisfaction remains an extension. |
| Customer referrals and digital outreach | Disabled | Acquisition occurs through distributor social neighbors. Findings are conditional on local reach. |
| Qualification purchases and eligibility thresholds | Disabled; category retained with zero volume | Prevents qualification rules from dominating the first model. They require separate rules and tests before activation. |
| Participant reactivation, former-participant retail purchases, and market entry | Disabled | Inactive former participants remain outside commercial activity. These boundaries can materially affect long-run demand. |
| Inventory, financing, firm overhead, and firm profit | Not modeled | Purchases are recorded transactions, not proof of final use or firm solvency. No company profitability claim follows from participant earnings. |

These reductions make the initial implementation manageable without removing the central comparison. They do not replace the guide's publication requirements: full ODD documentation, repeated experiments, global sensitivity screening, and at least three substantive robustness analyses remain necessary. Major additions require a version change, updated documentation, new tests, and rerunning affected experiments.

## 2. Population, networks, and states

### 2.1 Two distinct networks

The social graph `G_social` contains all `N` people throughout the run. It is undirected and static in v0.1. The baseline generator is Watts–Strogatz with an even neighborhood degree `k` and rewiring probability `rewiring_p`. Self-loops and duplicate edges are prohibited. Save the realized edge list and component statistics; do not silently regenerate inconvenient or disconnected realizations.

The sponsor graph `G_sponsor` is directed from sponsor to recruit. It contains all people who have ever enrolled and retains historical links after exit. Each nonseed participant has exactly one sponsor; initial distributors are independent roots. Enrollment creates an edge; it never creates a new person. Sponsor relationships do not change social edges. There is no reassignment or compression of sponsor links when a sponsor exits.

Initial distributors are sampled uniformly without replacement from people with at least one social neighbor. If too few eligible people exist, initialization raises a clear configuration error. Initially there are no customers. All remaining people are nonparticipant prospects.

### 2.2 Commercial states

| Code | State | Permitted transitions in v0.1 |
|---|---|---|
| `U` | Nonparticipant prospect, including a lapsed customer | `U → C` after an external first/reacquisition purchase; `U → D` after enrollment |
| `C` | Nonparticipant with an active customer relationship | `C → U` after customer churn; `C → D` after enrollment |
| `D` | Enrolled, active-status distributor | `D → I` after distributor exit |
| `I` | Inactive former participant | Absorbing state in v0.1 |

At every boundary, `n_U + n_C + n_D + n_I = N`. A customer is never simultaneously a distributor. A customer can skip a monthly purchase and remain in state `C`; relationship retention and purchasing are different outcomes. A customer becoming a distributor is recorded as role conversion, not customer churn.

New distributors enroll and make any configured entry purchase in the current month. They begin selling, recruiting, and facing ordinary distributor churn in the next month. Report both the end-of-month stock in state `D` and the number eligible to operate during the month. New customers cannot be recruited or repurchase in their acquisition month.

### 2.3 Minimum agent attributes

Store `person_id`, `state`, `product_fit`, `selling_skill`, `recruiting_skill`, `sponsor_id`, `seller_id`, `enrollment_month`, `first_operating_month`, `last_purchase_month`, `ever_customer`, `retail_exposures`, `recruitment_exposures`, recent net-income history, cumulative gross earnings, cumulative net cash earnings, and exit month.

Draw `product_fit`, `selling_skill`, and `recruiting_skill` independently from `Beta(2, 2)` for every person at initialization. These attributes lie between zero and one, with mean 0.5; they are illustrative heterogeneity, not empirical measurements. Predrawing skills prevents enrollment order from changing a person's attributes. A homogeneous-agent robustness variant sets all three to 0.5.

## 3. Behavioral rules and monthly schedule

### 3.1 Probability function

For a baseline probability `p` and behavioral adjustment `z`, define:

`B(p, z) = logistic(log(p / (1 - p)) + z)` for `0 < p < 1`.

Use the exact endpoint definitions `B(0, z) = 0` and `B(1, z) = 1`. Implement the interior with numerically stable arithmetic. The configured baseline probability describes a neutral agent with no fatigue; it is not necessarily the realized average probability across heterogeneous people.

### 3.2 Contact budget and selection

Each distributor eligible at the start of month `t` receives `contact_budget` slots. Assign `floor(contact_budget × recruitment_share)` slots to recruitment and the remaining slots to retail acquisition. There is no automatic reallocation of unused slots in v0.1.

Retail acquisition targets social neighbors currently in `U`. Recruitment targets neighbors in `U` or `C`, excluding customers newly acquired that month. States are rechecked when the event is processed. Each distributor can approach a person at most once per month across both channels. Different distributors may approach the same person. Sample candidates uniformly without replacement; stop when no eligible uncontacted neighbors remain. Unused slots do not generate fictitious contacts or expenses.

Randomize distributor order independently within each contact phase using reproducible priorities. A successful retail contact assigns its seller to that customer; a successful enrollment assigns its recruiter as sponsor. Subsequent events recheck eligibility, preventing duplicate assignments. This event order is a declared assumption, not a claim about actual sales processes.

### 3.3 Retail acquisition and exposure fatigue

For seller `i` and prospect `j`:

`p_buy(i,j,t) = B(p_retail, (2 × product_fit_j - 1) + (2 × selling_skill_i - 1) - fatigue × retail_exposures_j)`.

Use the exposure count before the current contact, then increment it whether the contact succeeds or fails. Success creates one external unit sale, records a `U → C` transition, and assigns `seller_id = i`. Distinguish a person's first-ever customer episode from reacquisition after churn. There is at most one external purchase per person per month.

Fatigue accumulates without decay in the baseline. Recruitment and retail exposure counters are separate. Saturation emerges from finite local neighborhoods, declining eligible pools, repeated exposure, and overlapping contacts; no network-size threshold forces collapse.

### 3.4 Recruitment

For recruiter `i` and eligible prospect `j`:

`p_join(i,j,t) = recruitment_multiplier_t × B(p_recruit, (2 × product_fit_j - 1) + (2 × recruiting_skill_i - 1) - fatigue × recruitment_exposures_j)`.

Increment recruitment exposure after each actual opportunity contact. Success changes the person immediately to `D`, records the sponsor edge and enrollment month, and schedules operation for `t + 1`. An existing customer's seller relationship ends upon enrollment; the person cannot repurchase as an external customer in that month. A person who just became a customer during the retail phase is not eligible for recruitment until the next month.

The shock changes only `recruitment_multiplier_t`. Recruitment contacts still consume their assigned slots and incur the same contact cost, even under a complete enrollment interruption. Their exposure effects are still recorded. This isolates an enrollment-success shock without automatically shifting effort to retail. A later effort-reallocation variant is a separate experiment.

### 3.5 Repurchase and customer continuity

Each person who was a customer at the start of the month and remains in `C` after recruitment receives one repurchase opportunity:

`p_repeat(j,t) = B(p_repurchase, 2 × product_fit_j - 1)`.

A purchase requires an operating distributor. If the assigned seller exited in an earlier month, choose uniformly among the customer's social neighbors eligible to operate this month. If none exists, retain the customer relationship for now but record an unserved opportunity and no sale. Do not silently sell directly through the company.

A successful repurchase creates one external unit sale and credits the selected seller. Repeat sales do not consume acquisition slots in the baseline: existing relationships receive automatic service when a seller is available. This unlimited repeat-service capacity is a simplifying assumption; seller reassignment and service availability are important robustness dimensions.

For customers present at the start and still in `C`, end-of-month churn probability is:

`p_customer_exit = min(1, customer_churn + unserved_churn_increment × unserved_flag)`.

The flag equals one only when no eligible seller was available. A customer who buys can still churn at the end of the month. Newly acquired customers first face churn in the next month. On churn, clear `seller_id`, retain purchase history and exposures, and return the person to `U`.

### 3.6 Participant purchases and distributor exit

Each new entrant purchases `entry_units` at enrollment. Initial seed distributors receive the same entry-purchase and entry-fee treatment in month 1. An entry purchase replaces personal consumption in that enrollment month. A zero entry quantity does not trigger a replacement personal purchase that month.

Other operating distributors independently purchase one personal-use unit with probability `B(p_personal, 2 × product_fit - 1)`. There is no purchase requirement for qualification in v0.1. Entry and personal-use purchases do not create an external customer. The first three months starting at enrollment form a reporting-only `new_entrant_window`; this tag can overlap purchase categories and must not be added to total volume again.

After accounting, compute `recent_net` as mean monthly net cash earnings over the latest three available participant months, including the current month. For distributors eligible to operate at the month's start:

`p_distributor_exit = min(1, distributor_churn + loss_exit_weight × min(1, max(0, -recent_net / loss_scale)))`.

On exit, change `D → I`, preserve all financial and sponsorship history, and end selling and commission eligibility from the next month. Their customers seek replacement sellers in the next monthly service phase. New entrants do not exit in their enrollment month. With both exit components set to zero, distributor exit must be impossible.

### 3.7 Execution order

1. Identify operating distributors and start-of-month customers; apply the month's recruitment multiplier.
2. Resolve seller availability for existing customers against the operating set.
3. Allocate fixed contact budgets and execute retail acquisition contacts.
4. Execute recruitment contacts, update states and sponsor links, and record entry purchases and fees.
5. Process repurchase for eligible existing customers; retain the distinction between stochastic nonpurchase and absence of service.
6. Process seed entry purchases in month 1 and personal consumption by eligible operating distributors.
7. Calculate retail margins, sponsor commissions, operating expenses, and earnings.
8. Evaluate customer and distributor exits using the rules above.
9. Record end-of-month states, stock-flow checks, transaction totals, and metrics.

The sponsor and operating sets used for current-month commissions are those eligible to operate at the start. An exit at the end of the month does not retroactively remove already earned commissions. New entrants cannot recruit within their enrollment month, preventing instantaneous recruitment cascades.

## 4. Purchase ledger and earnings

### 4.1 Mutually exclusive purchase categories

| Category | Buyer and event | Counts as external retail? |
|---|---|---|
| `external_first` | Nonparticipant's first-ever customer purchase | Yes |
| `external_reacquisition` | Purchase after a previous customer episode ended | Yes |
| `external_repeat` | Existing nonparticipant customer's repurchase | Yes |
| `participant_personal` | Active distributor's personal-use purchase | No |
| `participant_entry` | Initial purchase on enrollment; seed equivalent in month 1 | No |
| `participant_qualification` | Reserved; quantity always zero in v0.1 | No |

External unit volume is the sum of the first three categories. Total product units equal external units plus personal, entry, and qualification units. Entry fees, commissions, and operating expenses are not product volume. Report units separately from monetary flows because external and participant purchase prices differ.

### 4.2 Transparent compensation

Let `P` be retail price, `W` wholesale/participant price, and `c` the sponsor commission rate. Each transaction identifies a responsible distributor: the seller for an external purchase, or the buyer for a participant purchase.

For distributor `i` in month `t`:

- `retail_margin = (P - W) × external_units_sold`.
- `commission = c × W × eligible_units_attributable_to_direct_recruits`.
- `gross_earnings = retail_margin + commission`.
- `own_purchase_cost = W × (personal_units + entry_units + qualification_units)`.
- `net_cash = gross_earnings - own_purchase_cost - operating_cost - contact_cost - entry_fee_due`.

`operating_cost` is charged to distributors eligible to operate that month. `contact_cost` equals cost per contact multiplied by actual contacts across both channels. The entry fee is charged once, at enrollment; seed distributors pay in month 1. Resold units' wholesale cost is already deducted in retail margin and must not be deducted twice.

Eligible sponsor volume includes direct recruits' external sales and participant purchases. Pay at most one sponsor level per unit. If the immediate sponsor was not eligible to operate at the month's start, its commission is unpaid; do not pass it upward. The sponsor structure can have many levels even though the minimal compensation rule pays one. There is no payment for enrollment itself and no commission on entry fees.

Gross earnings are earned margin plus commissions, not gross customer receipts. Personal consumption may have value to a participant, but that value is not cash income. Track cash earnings separately from an optional imputed effort-cost outcome. The baseline excludes imputed labor cost; it does not claim to measure total economic welfare.

As a payment check, total sponsor commissions cannot exceed `c × W × total_units`. Firm production costs and overhead are outside this specification, so this check does not establish firm profitability.

## 5. Proposed starting parameters

All values below are exploratory modeling choices, not observed MLM estimates. Probability units are per stated event or month. The pilot must assess runtime and behavior before the main configuration is frozen. Store all constants, including heterogeneity weights and window lengths, in configuration files.

| Code name | Baseline | Unit or interpretation | Planned alternative/range |
|---|---:|---|---|
| `population_size` | 2,000 | People, fixed population | Pilot: 500; robustness: 1,000 and 5,000 |
| `initial_distributors` | 10 | Randomly selected roots | Initialization robustness to be documented |
| `initial_customers` | 0 | People | Zero retained for initial experiments |
| `horizon_months` | 120 | Monthly periods; initialization is month 0 | Longer horizon if late decline remains unresolved |
| `social_degree` | 10 | Even initial neighborhood degree | 6–20 |
| `rewiring_p` | 0.10 | Rewiring probability | 0.05–0.30 |
| `contact_budget` | 10 | Slots per operating distributor/month | 6–20 |
| `recruitment_share` | 0.50 | Fraction of contact slots | Main factors: 0.25, 0.75 |
| `p_retail` | 0.08 | Neutral prospect conversion/contact | Main: 0.03, 0.12; screening: 0.01–0.20 |
| `p_repurchase` | 0.60 | Neutral customer's repurchase/opportunity | Main: 0.30, 0.80; screening: 0.10–0.90 |
| `p_recruit` | 0.04 | Neutral enrollment/contact before shock | 0.005–0.10 |
| `customer_churn` | 0.02 | Base exit probability/customer/month | 0.01–0.10 |
| `unserved_churn_increment` | 0.05 | Additional churn probability without service | 0–0.10 |
| `distributor_churn` | 0.01 | Base exit probability/distributor/month | Main: 0.01, 0.05 |
| `loss_exit_weight` | 0.04 | Maximum additional exit probability | 0–0.10 |
| `loss_scale` | 0.30 | Normalized monthly cash-loss scale | Positive; varied in exit-rule robustness |
| `income_window` | 3 | Months used in recent net income | 1, 6 in later robustness if needed |
| `fatigue` | 0.10 | Log-odds penalty/prior same-channel exposure | 0–0.30 |
| `heterogeneity_alpha`, `heterogeneity_beta` | 2, 2 | Beta distribution shapes | Homogeneous variant: all attributes 0.5 |
| `fit_weight`, `selling_weight`, `recruiting_weight` | 1, 1, 1 | Coefficients on centered attributes | Fixed initially |
| `p_personal` | 0.30 | Neutral personal purchase probability/month | 0–0.60 |
| `entry_units` | 1 | Product units at enrollment | 0, 1, 2 |
| `new_entrant_window` | 3 | Reporting months from enrollment | Fixed initially |
| `retail_price` | 1.00 | Normalized currency/unit | Fixed initially |
| `wholesale_price` | 0.70 | Normalized currency/unit | Fixed initially; must not exceed retail price |
| `commission_rate` | 0.10 | Share of eligible wholesale volume | 0–0.20 |
| `fixed_operating_cost` | 0.05 | Currency/operating distributor/month | 0–0.15 |
| `cost_per_contact` | 0.005 | Currency/actual contact | 0–0.02 |
| `entry_fee` | 0.20 | Currency/new participant, once | 0–0.50 |
| `qualification_enabled` | false | Additional qualification purchases | Extension only |
| `shock_start_month` | 61 | First affected month, after 60 complete months | 31, 91 as timing robustness |
| `recruitment_multiplier` | 1.00 control; 0.00 shock | Multiplier from month 61 onward | 0.10 for a 90% reduction |

The implemented parameter dictionary must also contain definition, valid bounds, distribution, experimental role, rationale, source category, and model version. Reject invalid configurations rather than silently clipping inputs. Probability clipping is permitted only where the behavioral equation explicitly defines it.

## 6. Matched recruitment-shock experiment

Each scenario and replicate produces a control and a shock branch. Generate one initial population, network, attribute set, and random-number plan. Run the common trajectory through month 60 and clone the complete state, including histories and counters. Continue both branches through month 120.

The control keeps the recruitment multiplier at 1. The primary shock sets it to 0 at the beginning of month 61. Retail conversion, repurchase, churn equations, prices, costs, contact budget, and the social graph retain their same configured rules. These unchanged rules can still produce different realized demand as the two trajectories evolve.

### Reproducible randomness

A shared seed alone is insufficient if branch-specific events consume random draws in different orders. Use a documented random tape or stable event-keyed generator with separate process identifiers. Keys include `(replicate_seed, process_id, month, person_id[, partner_id, opportunity_index])`. Shared events must receive the same variate regardless of branch or the existence of unrelated events. Do not include treatment condition in shared event keys, use wall-clock seeds, or use Python's process-randomized built-in hash for persistent identifiers.

Initialization and network generation use recorded seeds. Contact ordering, contact selection, conversions, repurchase, participant purchases, and churn have distinct process identifiers. Deterministic keyed priorities can rank candidate contacts. After the shock, realized candidates and events may differ; common random numbers do not force the branches to stay identical.

Two controls with multiplier 1 must reproduce identical histories for every month. The shock and control must be identical through month 60. From month 61, no new enrollments may occur in the complete-interruption branch.

### Windows and estimands

Use months 49–60 as the preshock window, 61–72 as the immediate response, and 109–120 as the late response. Report paired differences in external unit volume as the primary shock effect:

`delta_external = sum(external_units_shock) - sum(external_units_control)` within each window.

For the late window, also report `external_resilience = sum(external_units_shock) / sum(external_units_control)` when the denominator is positive. A value above one is valid; do not truncate it. A control denominator of zero makes this ratio undefined, including when both branches are zero. Record `NA` with a reason and report both raw totals and the paired difference. Show a low-control-volume flag when late control volume is below 12 units; do not use ratios alone to classify these runs.

Calculate an analogous distributor-stock ratio from the sum of monthly end-of-month distributor counts. Use paired differences for median net earnings because zero or negative income makes income ratios misleading. If a recruitment-dependence index is reported, define it as `1 - resilience` separately for each suitable nonnegative outcome; negative values are permissible.

## 7. Outputs, denominators, and analysis

### Minimum recorded outcomes

| Dimension | Required outputs |
|---|---|
| Population and network | Counts in all four states, operating distributors, new enrollments, participant exits, sponsor depth, cumulative sponsor edges |
| External customers | New unique customers, reacquisitions, repurchases, customer churn, customer-to-distributor conversions, unserved opportunities |
| Product flows | Units in each purchase category, external units, total units, external retail share, new-entrant-tagged units |
| Exposure and effort | Realized contacts by channel, unused slots, distinct contacted people, repeat-contact overlap, exposure counts, eligible social prospects per distributor |
| Participant outcomes | Gross earnings, net cash earnings, cumulative net cash, positive-income shares, earnings quantiles, survival durations |
| Shock response | Window totals, paired differences, valid ratios, denominator flags, preshock state and demand measures |

Compute external retail share as external units divided by total units; use `NA` when total volume is zero. Compute observed repurchase rate over eligible existing customers after recruitment, including unserved customers; also provide the conditional rate among customers with service. Report denominators explicitly. A relationship count is not the number who bought that month.

For monthly participant earnings, provide a cohort of everyone in `D` at the month's start or who enrolled during it, including people who exit at month end. For cumulative participant viability, include all-ever-enrolled participants, retaining exited participants' final cumulative earnings. Report end-active participants separately to reveal survivorship differences. Empty populations yield `NA`, not fabricated zero median income.

Compute conventional Gini only on nonnegative cumulative gross earnings among all-ever-enrolled participants; it is undefined when everyone earned zero. Net cash earnings may be negative, so report their quantiles, interquartile range, and loss share rather than shifting them arbitrarily to calculate a conventional Gini. Label this distinction in every table.

Summarize independent replicates with means, medians, interquartile ranges, and simulation percentile intervals. Estimate uncertainty in mean paired shock differences by resampling whole matched pairs or using their standard error. Distinguish a simulation-distribution interval from a confidence interval for a mean. Monthly observations do not increase the number of independent replications.

No regime threshold is fixed by this first specification. Before the final experiment, document a transparent rule for demand strength, shock vulnerability, and participant viability, test threshold sensitivity, and retain ambiguous/low-volume cases. Do not force every run into a favorable or unfavorable category. The Demand–Recruitment Sustainability Matrix remains a later synthesis of these dimensions, not a legal classification.

## 8. Pilot, main design, sensitivity, and robustness

### Verification before the pilot

Complete the tests in Section 10 first. A debug trajectory can inspect transitions and accounting but cannot support substantive findings.

### Proposed pilot

Use `N = 500`, 10 initial distributors, 120 months, and four demand combinations: `p_retail ∈ {0.03, 0.12}` crossed with `p_repurchase ∈ {0.30, 0.80}`. Keep other settings at baseline. Use 10 independent replicate seeds per combination, each producing control and shock branches: **40 matched pairs, or 80 branch trajectories**. The common prefix can be computed once per pair.

The pilot checks correctness, runtime, extinction frequency, local saturation, zero denominators, and whether the outcome space warrants expanding the design. It is not the final evidence base. Do not change parameters merely to obtain a desired conclusion. Record each change and its reason.

### Proposed main experiment

Cross four factors at two levels: retail conversion (0.03/0.12), repurchase (0.30/0.80), recruitment effort share (0.25/0.75), and base distributor churn (0.01/0.05). With 16 settings, 100 independent matched pairs per setting imply **1,600 pairs or 3,200 branch trajectories**. Use the main population size of 2,000 after checking runtime.

This is a proposed design, not an already approved or executed run count. Retain at least 100 replications per central setting as the guide's starting requirement, then adjust using Monte Carlo precision. Before execution, record a tolerance for primary paired effects. A proposed diagnostic target is a 95% mean-effect interval half-width no greater than 10% of `max(mean control late external units, 12)`; report achieved precision rather than claiming this convention establishes substantive significance. Inspect ratio uncertainty and the proportion of undefined ratios separately.

### Sensitivity and structural challenges

After the baseline is verified, use Morris or an equivalent documented global screening design over approximately 10–12 uncertain parameters, including conversion, repurchase, recruitment conversion, effort allocation, exit, fatigue, personal consumption, and expenses. Preserve multiple stochastic replications at each parameter point and archive the sample. Select a feasible detailed sensitivity design after screening; Sobol or another justified method remains conditional on computational cost. Repeat screening under at least one alternative structural assumption.

The publication study must include at least three robustness analyses capable of changing the conclusion. Prioritize: (1) an alternative social topology with comparable mean degree; (2) seller loss with no automatic reassignment, or a documented bounded service-capacity rule; and (3) an alternative distributor-exit rule, including removal of the loss penalty. Add partial/earlier/later shocks, population size, participant entry purchases, and adaptive effort if resources permit. Define each alternative fully before running it.

A finite closed market with an absorbing inactive state and positive distributor exit can eventually lose all distributors when recruitment stops. Therefore the study measures persistence over a stated horizon, not indefinite survival. Report this structural limit and inspect longer horizons when conclusions depend on the final observation date.

## 9. Python implementation and file contracts

Use Python with NumPy, NetworkX, pandas, and pytest. Use Matplotlib for figures. A lightweight explicit scheduler is sufficient; Mesa is optional and is not required for v0.1. Freeze the tested Python and package versions when implementation is complete. No package version is claimed to have been tested by this document.

| Module or file | Responsibility |
|---|---|
| `src/article25/config.py` | Parameter schema, bounds, defaults, and configuration validation |
| `src/article25/agents.py` | Agent state, attributes, transitions, and histories |
| `src/article25/networks.py` | Social graph, initialization, sponsor edges, and graph checks |
| `src/article25/randomness.py` | Stable event keys and reproducible random streams/tapes |
| `src/article25/demand.py` | Acquisition, seller availability, repurchase, customer churn |
| `src/article25/recruitment.py` | Enrollment, activation timing, and shock multiplier |
| `src/article25/accounting.py` | Purchase ledger, margins, commissions, fees, and costs |
| `src/article25/model.py` | Monthly schedule and state cloning |
| `src/article25/metrics.py` | Outcome definitions, denominators, and missing-value flags |
| `src/article25/experiments.py` | Single-run, matched-pair, pilot, and scenario runners |
| `tests/` | Unit, accounting, state, paired-randomness, and extreme-condition tests |
| `configs/` | JSON parameter files; no hardcoded experiment settings |
| `notebooks/` | Optional inspection and teaching; model logic remains in modules |

Expected entry points, to be implemented and documented, are `python -m article25.experiments --config <file> --output <directory>` and `python -m pytest`. They are interface requirements, not commands tested in this specification.

Every run carries `model_version`, `code_hash`, `config_hash`, `experiment_id`, `scenario_id`, `replicate_id`, `pair_id`, `seed`, and `condition`. Define `pair_id` from scenario and replicate identifiers; define `run_id` by adding condition. Distinguish pilot and main configuration identities.

Required output schemas:

- `run_manifest`: identifiers above, full parameter values, environment version, execution status, runtime, and initial-state identifier.
- `initial_state`: complete agents, social edges, root identities, and random initialization identifiers; `checkpoint_060` additionally stores all evolving state needed for branching.
- `monthly_metrics`: one row per run/month, with the outcomes and denominator flags in Section 7.
- `run_summary`: one row per run with window summaries and cumulative participant outcomes.
- `paired_effects`: one row per matched pair/window/outcome with control value, shock value, difference, ratio if valid, and reason if missing.
- `participant_summary`: one row per ever-enrolled person/run with entry, exit, tenure, depth, and cumulative earnings.
- `transactions` and `events`: full ledgers for verification and selected debug runs; aggregate by category for large experiments if full ledgers are too large.

Use CSV for small reviewable outputs and a documented efficient table format for larger outputs if necessary. Do not dump every agent at every month by default. Save raw outputs in `06_Simulaciones` under the relevant experiment subfolder, analysis scripts and processed results in `07_Analisis`, figures/tables in `08_Figuras_y_tablas`, and environment/reproduction instructions in `10_Reproducibilidad`. Keep parameter and seed registries in `03_Parametros_y_escenarios` and test reports in `05_Pruebas_y_verificacion`. Versioned final raw outputs are immutable.

## 10. Verification and acceptance criteria

| Test | Required result |
|---|---|
| Population conservation | Exactly `N` unique people and one permitted state/person at every step |
| Stock-flow reconciliation | Customer and distributor ending stocks reconcile with beginnings, acquisitions, enrollments, and exits |
| Sponsor integrity | Roots have no sponsor; every later enrollee has one historically valid sponsor; no self-links or cycles |
| Activation timing | No selling, recruiting, or ordinary exit in enrollment month; no same-tick cascades |
| Zero retail conversion | No new or reacquired customers from acquisition contacts; existing customer repurchase remains governed separately |
| Zero recruitment conversion | No new enrollments, including without the shock |
| Complete interruption | Zero enrollments from month 61; contacts and their costs still follow the configured schedule |
| Repurchase endpoints | At probability 0 no repeats; at 1 every eligible served customer repeats; unserved customers never purchase |
| Zero churn | With all respective exit components disabled, no spontaneous customer or distributor exits |
| Role conversion | A recruited customer stops external repurchase; new acquisition is not recruited in the same month |
| Exhausted contact pool | No invented contacts, customers, or people; unused slots are recorded |
| No operating distributors | Zero external sales and recruitment under the stated service rule |
| Contact overlap | A person has at most one seller and one sponsor; repeated attempts update exposure once per actual event |
| Volume reconciliation | Total units equal exclusive category sums; entrant tags and financial transfers do not inflate volume |
| Accounting fixture | Hand-calculated retail margin, one-level commissions, purchases, and costs equal code outputs |
| Commission boundary | No commission for enrollment alone; inactive sponsors are unpaid; payout cap holds |
| Seeds and branching | Identical configurations/seeds reproduce outputs; two control branches match throughout; shock/control match through month 60 |
| Event randomness | Skipping an unrelated event or changing loop order cannot shift a shared event's keyed variate |
| Numerical boundaries | Valid probabilities, finite earnings, and explicit `NA` flags for empty/zero-denominator metrics |
| Extreme runs | Homogeneous agents, no fatigue, no participant purchasing, no exits, and severe exits all obey their declared rules |

Use small deterministic fixtures for accounting and transitions; use multiple fixed seeds for integrated checks. Examine invariants after each phase in debug mode. Unexpected trajectories can be valid findings; failures of accounting, state conservation, or reproducibility are defects.

The implementation is ready for the pilot when these tests pass, the student can explain every rule, both supervisors have reviewed the boundaries, and one documented command regenerates a small matched experiment and its outputs. Passing verification establishes consistency with the specified rules, not empirical validation of real organizations.

## 11. Delivery sequence and responsibilities

1. **M1 — Population and networks:** implement configuration, agent states, social graph, sponsor initialization, and deterministic randomness; verify invariants.
2. **M2 — Commercial dynamics:** implement contact allocation, purchases, repurchase, enrollment, activation, and exits; verify state transitions and stock-flow identities.
3. **M3 — Earnings and matched experiments:** implement the financial ledger, commission rules, metrics, checkpoints, and shock pairing; pass the complete test suite.
4. **M4 — Pilot:** execute the proposed small design, report runtime and defects, and issue a versioned decision log before freezing main parameters.
5. **M5 — Publication experiments:** run the repeated main design, sensitivity, and robustness; prepare figures, full ODD, and the replication package before drawing manuscript conclusions.

The student remains the operational lead for literature, understanding and checking the code, experiments, analysis, and first manuscript drafts. Professors review theoretical boundaries, model rules, verification, uncertainty, and interpretation. Record substantive contributions and changes. Assistance with specification or programming does not replace the student's responsibility to reproduce and explain the study.

The immediate next action is **M1 in Python, followed by its verification tests**. The manuscript target remains 15 December 2026; later extensions should be selected for their ability to challenge the scientific claim without jeopardizing completion.

## 12. Interpretation and change record

All conclusions must be expressed as conditional on the model's assumptions, horizon, and parameter ranges. The model is an educational and theoretical computational study. It does not classify named organizations, estimate industry prevalence, predict actual participant income, or provide a regulatory test. Strong external retail demand does not by itself establish overall firm or participant viability.

| Date | Version | Decision |
|---|---|---|
| 2026-09-25 | Specification 0.1 | Python selected; minimal four-state model, two networks, exclusive purchase categories, fixed effort, simplified compensation, and matched enrollment interruption proposed. All numeric choices are provisional. No simulations executed. |

Before final experiments, the decision log must record the reviewed parameter dictionary, exact scenario design, precision criteria, robustness rules, interpretation thresholds, model/code versions, and completed verification report. Changes motivated by pilot findings must remain visible and must not be described as prespecified after the fact.

