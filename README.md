# RC CodePro

Reinforced-concrete member design to **ACI 318M-08**, MKS units
(cm · kgf · ksc · kgf·m · kgf/m²).  Thai-language desktop UI built with
Streamlit; CAD-style detail drawings (matplotlib) and one-page A4 PDF
calculation sheets (fpdf2 + THSarabunNew).

## Requirements

- Python 3.10+
- Packages in `requirements.txt`:
  `streamlit`, `numpy`, `fpdf2`, `uharfbuzz`, `pillow`, `matplotlib`,
  `plotly`, `pytest`
- `fonts/THSarabunNew.ttf` (bundled) — needed for Thai text in the PDF and
  in the CAD call-outs.

## Install

```
pip install -r requirements.txt
```

## Run

```
streamlit run main.py
```

The app opens with a sidebar navigation rail:

| Group | Pages |
|---|---|
| Overview | **Home** — Project Control Center (read-only status dashboard) |
| Project | **Project Information** — the single source of truth for project name / location / engineer / date |
| Member Design | **Beam**, **Column**, **Slab**, **Footing**, **Stair** |
| Model | **Building Model** — grid layout + tributary gravity load take-down + BOQ estimate |

Every member page follows the same layout: `MEMBER INPUT → DESIGN SUMMARY →
DESIGN CHECKS → DETAILED CALCULATION → DRAWING → OUTPUT / REPORT`.
The PDF report is generated only when you press **Generate PDF Report**
(not on every rerun) and is cached for re-download.

## Modules

| Module | Implemented | Under construction |
|---|---|---|
| **Beam** | Section design (flexure + shear), 3-critical-section beam, continuous-beam analysis (1-D matrix stiffness → SFD / BMD, governing +Mu / −Mu / Vu) | — |
| **Column** | Rectangular / circular, ρg, φPn,max, full P–M interaction, tie / spiral spacing | — |
| **Slab** | One-way / two-way (m = Lx/Ly), flexural + shrinkage-temperature steel, bar spacing | — |
| **Footing** | Isolated footing; pile cap F1–F9; eccentric pile cap F1E–F9E | Wall / 2C / Combined / Strap footings |
| **Stair** | Straight flight; U-shape (half-turn) | L-shape, slabless, free-standing, spiral |
| **Building Model** | Grid parsing, node/column generation, void panels, tributary Pu take-down, rule-based column grouping, BOQ estimate, 2-D plan + 3-D viewer | Structural analysis (the Building Model is a model + take-down + BOQ output, **not** a design check — its report status reads *MODEL GENERATED*, never a design *PASS*) |

Under-construction types are clearly marked in the UI and do not produce
results.

## Tests

Golden-value regression on every calculation helper (formulas, the
matrix-stiffness solver, and the BOQ estimator):

```
pytest -q
```

Expected: **73 passed**.  Engineering constants and expected values are
frozen — see `docs/REGRESSION_BASELINE.md`.

## Notes

- `docs/ENGINEERING_REVIEW.md` records engineering observations that are
  intentionally **not** changed by the UI work (layer boundaries, sampled
  governing moment, wording, etc.).
- CAD drawings are white on purpose — the same PNG is embedded in the
  print PDF.  Only the Plotly SFD/BMD and 3-D viewer follow the dark UI
  theme.
- Units are never converted for display beyond the report's existing
  SI → MKS helpers; the UI works in the same MKS units as the engine.
