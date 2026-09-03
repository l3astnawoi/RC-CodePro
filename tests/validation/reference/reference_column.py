"""EV-02 — Independent column axial/P-M anchor references.

Independent validation reference — NOT production calculation code.
No import of modules.column.

EV-02 scope for the column P-M interaction:

* The two exact ANCHOR points of the interaction diagram are derived here
  by hand (pure compression Po / design cap; pure tension Pt):
      - ACI 318M-08 10.3.6 for Po and the tied/spiral axial cap
      - Pnt = -fy*Ast  for pure tension
* The INTERIOR of the curve (balanced point, intermediate eccentricities,
  points near the design boundary) requires an independent
  strain-compatibility solver whose own correctness would itself need
  establishing.  Per the EV-02 brief that is marked BLOCKED here rather
  than fabricated — see cases COLUMN-PM-003/004/005.

MKS units: ksc / cm / kgf.
"""


def axial_anchors_mks(fc_ksc, fy_ksc, Ag_cm2, n_bars, Ab_cm2, tied=True):
    """Return the exact axial anchors of the P-M diagram.

        Ast = n_bars * Ab
        Po  = 0.85 f'c (Ag - Ast) + fy Ast            (ACI 10.3.6.1)  [kgf]
        design cap  phi*Pn,max :
            tied   : 0.80 * 0.65 * Po                 (ACI 10.3.6.2)
            spiral : 0.85 * 0.75 * Po
        Pnt = -fy Ast   (pure tension, tension negative)
        phi*Pnt = 0.90 * Pnt   (tension-controlled)
    """
    Ast = n_bars * Ab_cm2
    Po = 0.85 * fc_ksc * (Ag_cm2 - Ast) + fy_ksc * Ast
    alpha, phi_c = (0.80, 0.65) if tied else (0.85, 0.75)
    Pnt = -fy_ksc * Ast
    return {
        "Ast_cm2": Ast,
        "Po_kgf": Po,
        "phiPn_max_kgf": alpha * phi_c * Po,
        "Pnt_kgf": Pnt,
        "phiPnt_kgf": 0.90 * Pnt,
        "alpha": alpha,
        "phi_c": phi_c,
    }


def gross_area_rect_cm2(b_cm, h_cm):
    return b_cm * h_cm


def bar_area_cm2(designation):
    """Nominal deformed-bar area in cm^2 from the designation (DBnn, nn mm).
    Independent of utils.aci_318m: area = pi * d^2 / 4, d in mm -> /100 cm^2.
    """
    import math
    d_mm = float(designation[2:])
    return math.pi * d_mm ** 2 / 4.0 / 100.0
