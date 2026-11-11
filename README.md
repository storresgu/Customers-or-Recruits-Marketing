# Customers or Recruits? — model, data and analysis

Code and results for the article *Customers or Recruits? An Entrepreneurial Marketing Perspective on Retail Demand and Recruitment Dependence in an Agent-Based Model*.

All data are synthetic. They contain no personal data and are not empirical findings. Monetary values are normalized model units.

## Start here: `Article_25_M4/`

This folder is an unzipped, readable copy of everything used in the article. Nothing needs to be extracted.

| Folder | Content |
|---|---|
| `Article_25_M4/code/` | Model code, version `0.3.0-m3` (code hash `c877a6d87a39aed484d8e4b2cc896845bbf42dbd7a821620157b5ad429935766`), tests and configurations. The pilot configuration is `code/configs/pilot_m3.json`. |
| `Article_25_M4/results/` | Consolidated pilot results used for every table: `scenario_summary.csv`, `monthly_metrics.csv`, `run_diagnostics.csv`, `participant_summary.csv`, and the audit `audit.json`. |
| `Article_25_M4/pilot_v01/` | Pair-level effects (`paired_effects.csv`), run summaries and the run registry. |
| `Article_25_M4/pilot_registration/` | Seed registry, resolved design and manifest. |
| `Article_25_M4/analysis/` | Analysis scripts (`analyze_pilot.py`) and figure scripts. |
| `Article_25_M4/README.md` | Step-by-step instructions to rerun the model, the tests and the analysis. |

## Figures in the article

| Figure | Source |
|---|---|
| 1 | `analysis/figure1_conceptual.py` |
| 2–3 | Conceptual diagrams; no data. |
| 4, 5 | `pilot_v01/paired_effects.csv` (late window, months 109–120, outcome `external_units`) |
| 6 | `results/monthly_metrics.csv` (`external_units` by month, scenario and condition) |
| 7 | `results/monthly_metrics.csv` (`n_D` by month, scenario and condition) |
| 8 | `pilot_v01/paired_effects.csv` (`resilience_ratio`, late window) and `results/scenario_summary.csv` |
| 9 | `results/run_diagnostics.csv` (`final_D`, `all_ever_loss_share`) |
| 10 | `results/participant_summary.csv` (`cumulative_net_cash`, `enrollment_month`) |

`analysis/plot_pilot.py` produces the descriptive trajectory figure of the pilot report. The script that exported the final images for Figures 4–10 was not archived; all values plotted in those figures can be checked against the CSV files listed above.

## Archives kept for traceability

The ZIP files in the root are the original project archives:

| File | Content |
|---|---|
| `02_Modelo_y_ODD-20261016T205950Z-1-001.zip` | Model specification (`Article_25_Especificacion_minima_v0.1.md`) and M5 protocol and addendum. |
| `03_Parametros_y_escenarios-20261016T205936Z-1-001.zip` | Pilot design (`Article_25_M4_Piloto_diseno_v0.1.json`) and seeds (`Article_25_M4_Piloto_semillas_v0.1.csv`); M5 design. |
| `04_Codigo-20261016T205927Z-1-001.zip` | Code by milestone: `Article_25_M1_Python_v0.1.zip`, `Article_25_M2_Python_v0.2.zip`, `Article_25_M3_Python_v0.3.zip` (version used in the article) and `Article_25_M5_Python_v0.5.zip` (not used in the article). |
| `05_Pruebas_y_verificacion-20261016T205917Z-1-001.zip` | Verification reports for M1, M2, M3 and M5, and the pilot report for M4. |
| `06_Simulaciones.zip` | `00_Piloto/`: lightweight per-pair pilot outputs (`Article_25_M4_Resumenes_ligeros_v0.1.zip`) and checksums of the full traces. `01_Escenarios_principales/`: M5 benchmark, not used in the article. `02_Shock_y_control_pareados/`: M3 verification pair. |
| `07_Analisis-20261016T205858Z-1-001.zip` | Contains `07_Analisis/Article_25_M4_Analisis_y_codigo_v0.1.zip`, the same package already unzipped above as `Article_25_M4/`. |

M1–M3 are model development milestones, M4 is the pilot reported in the article, and M5 is a later confirmatory design whose outputs are not used in the article.

### Extracting the archives yourself

The folder `Article_25_M4/` makes this unnecessary, but the original route to the code and results is:

1. Extract `07_Analisis-20261016T205858Z-1-001.zip`. This creates `07_Analisis/`.
2. Extract `07_Analisis/Article_25_M4_Analisis_y_codigo_v0.1.zip`. This creates `Article_25_M4/`.
3. The code is in `Article_25_M4/code/` and the consolidated results in `Article_25_M4/results/`.
4. For the per-pair outputs, extract `06_Simulaciones.zip` and then `06_Simulaciones/00_Piloto/Article_25_M4_Resumenes_ligeros_v0.1.zip` into the same parent folder as `Article_25_M4/`; it adds `Article_25_M4/pilot_v01/pairs/`.

## Full simulation traces

The full traces (about 197 MB compressed, 1.9 GB unzipped) exceed GitHub's file-size limits and are available from the corresponding author on reasonable request (storresgu@unal.edu.co). Their SHA-256 checksums are in `06_Simulaciones.zip` → `00_Piloto/SHA256_trazas_completas.txt`.
