"""EV-02 — Independent ACI 318M-08 primitive references.

Independent validation reference — NOT production calculation code.
No import of utils.aci_318m or any modules.* — every value here is
re-derived from the ACI 318M-08 equation text and explicit arithmetic.

Unit systems are stated per function. SI: MPa / N / mm. MKS: ksc / kgf / cm.
"""

import math

# ACI 318M-08 material constants (re-declared independently)
EPS_CU = 0.003            # 10.2.3  ultimate concrete compressive strain
ES_MPA = 200000.0         # 8.5.2   steel modulus, MPa
ES_KSC = 2040000.0        # 8.5.2   steel modulus, ksc  (~200 GPa)
EPS_TC = 0.005            # 10.3.4  tension-controlled net tensile strain
KSC_TO_MPA = 0.0980665    # exact:  1 kgf/cm^2 = 0.0980665 MPa
KGF_PER_KN = 1000.0 / 9.80665


# ---------------------------------------------------------------------------
# beta_1  — ACI 318M-08 10.2.7.3
# ---------------------------------------------------------------------------
def beta1_si(fc_mpa):
    """beta_1 for f'c in MPa (ACI 318M-08 10.2.7.3):
        fc' <= 28              -> 0.85
        28 < fc' < 55(ish)     -> 0.85 - 0.05*(fc'-28)/7   (>= 0.65)
        high strength          -> 0.65 floor
    """
    if fc_mpa <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_mpa - 28.0) / 7.0)


def beta1_mks(fc_ksc):
    """beta_1 for f'c in ksc, using the *MKS-literal* break point of 280 ksc
    and -0.05 per 70 ksc.  This mirrors how the engine's MKS helpers are
    written; see Finding VF-07 for the 28 MPa (= 285.5 ksc) vs 280 ksc
    inconsistency this introduces.
    """
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def beta1_mks_via_si(fc_ksc):
    """The *code-consistent* MKS beta_1: convert to MPa first, then apply the
    single ACI 10.2.7.3 definition.  Used to quantify the VF-07 gap.
    """
    return beta1_si(fc_ksc * KSC_TO_MPA)


# ---------------------------------------------------------------------------
# rho_min / rho_max flexure — ACI 318M-08 10.5.1 and 10.3.4
# ---------------------------------------------------------------------------
def rho_min_flexure_si(fc_mpa, fy_mpa):
    """ACI 10.5.1:  rho_min = max(0.25*sqrt(f'c)/fy, 1.4/fy)   (MPa)."""
    return max(0.25 * math.sqrt(fc_mpa) / fy_mpa, 1.4 / fy_mpa)


def rho_min_flexure_mks(fc_ksc, fy_ksc):
    """ACI 10.5.1 MKS form:  rho_min = max(0.8*sqrt(f'c)/fy, 14/fy)  (ksc).
    This is the conventional metric transcription of 0.25*sqrt / 1.4.
    """
    return max(0.8 * math.sqrt(fc_ksc) / fy_ksc, 14.0 / fy_ksc)


def rho_max_tc_si(fc_mpa, fy_mpa):
    """Tension-controlled maximum ratio (eps_t = 0.005, ACI 10.3.4):
        rho_max = 0.85 * beta1 * f'c / fy * eps_cu / (eps_cu + 0.005)
                = 0.85 * beta1 * f'c / fy * 0.375
    """
    return (0.85 * beta1_si(fc_mpa) * fc_mpa / fy_mpa
            * EPS_CU / (EPS_CU + EPS_TC))


def rho_max_tc_mks(fc_ksc, fy_ksc):
    """MKS mirror of rho_max_tc_si, using beta1_mks (280 ksc break)."""
    return (0.85 * beta1_mks(fc_ksc) * fc_ksc / fy_ksc
            * EPS_CU / (EPS_CU + EPS_TC))


# ---------------------------------------------------------------------------
# phi (flexure / axial) from net tensile strain — ACI 318M-08 9.3.2
# ---------------------------------------------------------------------------
def phi_from_strain(eps_t, spiral=False, eps_ty=0.002):
    """ACI 9.3.2:
        eps_t <= eps_ty            -> phi_c  (0.65 tied / 0.75 spiral)
        eps_t >= 0.005             -> 0.90
        between                    -> linear interpolation
    The engine uses a fixed eps_ty = 0.002 (EPSILON_TY) rather than fy/Es;
    that literal is reproduced here so the reference matches the intended
    definition (record any fy/Es discrepancy as a NOTE, not a fix).
    """
    phi_c = 0.75 if spiral else 0.65
    if eps_t <= eps_ty:
        return phi_c
    if eps_t >= EPS_TC:
        return 0.90
    return phi_c + (0.90 - phi_c) * (eps_t - eps_ty) / (EPS_TC - eps_ty)


# ---------------------------------------------------------------------------
# Concrete one-way shear Vc — ACI 318M-08 11.2.1.1 (Eq. 11-3)
# ---------------------------------------------------------------------------
def vc_oneway_si(fc_mpa, bw_mm, d_mm, lam=1.0):
    """Vc = 0.17 * lambda * sqrt(f'c) * bw * d   [N]   (ACI Eq. 11-3, SI)."""
    return 0.17 * lam * math.sqrt(fc_mpa) * bw_mm * d_mm


def vc_oneway_mks_053(fc_ksc, b_cm, d_cm):
    """Traditional ACI-MKS form:  Vc = 0.53 * sqrt(f'c) * b * d   [kgf].
    The 0.53 coefficient is the long-standing metric rounding of the SI
    0.17*sqrt(MPa) expression.
    """
    return 0.53 * math.sqrt(fc_ksc) * b_cm * d_cm


def vc_oneway_mks_from_si(fc_ksc, b_cm, d_cm):
    """The *exact* MKS-unit equivalent of the SI 0.17*sqrt(f'c)*bw*d, obtained
    by carrying the unit conversions through symbolically:

        0.17*sqrt(fc_ksc*0.0980665)*(b_cm*10)*(d_cm*10)  [N]  / 9.80665 -> kgf
        = 0.17*sqrt(0.0980665)*100/9.80665 * sqrt(fc_ksc)*b_cm*d_cm
        ~= 0.54288 * sqrt(f'c) * b * d   [kgf]

    Comparing 0.54288 (exact) vs 0.53 (engine literal) quantifies the
    ~2.4 % conservatism of the traditional metric coefficient.
    """
    k = 0.17 * math.sqrt(KSC_TO_MPA) * 100.0 / 9.80665
    return k * math.sqrt(fc_ksc) * b_cm * d_cm


def vc_oneway_mks_053_coeff():
    """Return (engine_coeff, exact_coeff) for the MKS one-way shear."""
    return 0.53, 0.17 * math.sqrt(KSC_TO_MPA) * 100.0 / 9.80665


# ---------------------------------------------------------------------------
# Two-way (punching) shear vc — ACI 318M-08 11.11.2.1 (Eqs 11-31..11-33)
# ---------------------------------------------------------------------------
def vc_twoway_si(fc_mpa, beta_c, bo_mm, d_mm, alpha_s=40.0, lam=1.0):
    """Return (vc1, vc2, vc3, vc_governing) in MPa for a rectangular
    interior column (alpha_s = 40), ACI 318M-08 11.11.2.1:

        vc1 = 0.17 * (1 + 2/beta_c) * lambda * sqrt(f'c)          (Eq. 11-31)
        vc2 = 0.083 * (alpha_s*d/bo + 2) * lambda * sqrt(f'c)     (Eq. 11-32)
        vc3 = 0.33 * lambda * sqrt(f'c)                           (Eq. 11-33)
        vc  = min(vc1, vc2, vc3)

    beta_c = long side / short side of the loaded (column) area.
    bo     = perimeter of the critical section at d/2 from the column face.
    """
    s = math.sqrt(fc_mpa)
    vc1 = 0.17 * (1.0 + 2.0 / beta_c) * lam * s
    vc2 = 0.083 * (alpha_s * d_mm / bo_mm + 2.0) * lam * s
    vc3 = 0.33 * lam * s
    return vc1, vc2, vc3, min(vc1, vc2, vc3)


def punching_perimeter_rect(cx_mm, cy_mm, d_mm):
    """Critical perimeter b0 at d/2 outside a rectangular column
    (ACI 318M-08 11.11.1.2):  b0 = 2*(cx + d) + 2*(cy + d)."""
    return 2.0 * (cx_mm + d_mm) + 2.0 * (cy_mm + d_mm)


def punching_perimeter_circle_code(Dp_mm, d_mm):
    """Code-consistent critical perimeter for a *circular* loaded area at
    d/2 (ACI 318M-08 11.11.1.2, R11.11):  b0 = pi * (Dp + d).
    Compare with the engine's literal `3.464*Dp + pi*d` (Finding VF-09)."""
    return math.pi * (Dp_mm + d_mm)


def punching_perimeter_circle_engine_literal(Dp_mm, d_mm):
    """The literal the engine uses for a circular pile head:
        b0 = 3.464 * Dp + pi * d
    Reproduced here ONLY to quantify the difference vs the code form.
    3.464 ~= 2*sqrt(3); its derivation is unclear -> CODE REFERENCE TO VERIFY.
    """
    return 3.464 * Dp_mm + math.pi * d_mm


# ---------------------------------------------------------------------------
# Tie (transverse reinforcement) maximum spacing — ACI 318M-08 7.10.5.2
# ---------------------------------------------------------------------------
def tie_spacing_max(db_long, db_tie, least_dim):
    """ACI 318M-08 7.10.5.2 — tie spacing shall not exceed the least of:
        16 * (longitudinal bar diameter)
        48 * (tie bar diameter)
        the least cross-sectional dimension of the column
    All three arguments must be in the same length unit; the result is in
    that unit.  This is the *maximum permitted spacing*; the engine checks
    only that this maximum is itself >= 5 cm (constructability floor), it
    does NOT compare a user-supplied provided spacing to it (Finding VF-10).
    """
    return min(16.0 * db_long, 48.0 * db_tie, least_dim)


# ---------------------------------------------------------------------------
# Column axial anchors — ACI 318M-08 10.3.6
# ---------------------------------------------------------------------------
def column_Po_mks(fc_ksc, fy_ksc, Ag_cm2, Ast_cm2):
    """Nominal axial strength at zero eccentricity (ACI 10.3.6.1/10.3.6.2):
        Po = 0.85 f'c (Ag - Ast) + fy Ast     [kgf]   (MKS)
    """
    return 0.85 * fc_ksc * (Ag_cm2 - Ast_cm2) + fy_ksc * Ast_cm2


def column_phiPn_max_mks(fc_ksc, fy_ksc, Ag_cm2, Ast_cm2, tied=True):
    """Maximum design axial load (ACI 318M-08 10.3.6):
        tied   : phi*Pn,max = 0.80 * 0.65 * Po
        spiral : phi*Pn,max = 0.85 * 0.75 * Po
    """
    alpha, phi_c = (0.80, 0.65) if tied else (0.85, 0.75)
    return alpha * phi_c * column_Po_mks(fc_ksc, fy_ksc, Ag_cm2, Ast_cm2)


def column_Pnt_mks(fy_ksc, Ast_cm2):
    """Nominal pure-tension capacity:  Pnt = -fy * Ast  [kgf] (tension -ve).
    Design value phi*Pnt uses phi = 0.90 (tension-controlled)."""
    return -fy_ksc * Ast_cm2
