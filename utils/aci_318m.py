"""ACI 318M-08 (metric) constants and helper functions.

All quantities are in SI / metric units:
    - stresses / strengths : MPa  (N/mm^2)
    - forces               : N
    - moments              : N-mm
    - lengths / dimensions : mm
    - areas                : mm^2
"""

import math

# ---------------------------------------------------------------------------
# Material / code constants
# ---------------------------------------------------------------------------

# Ultimate concrete compressive strain (ACI 318M-08 10.2.3)
EPSILON_CU = 0.003

# Modulus of elasticity of reinforcement (ACI 318M-08 8.5.2), MPa
ES = 200000.0

# Steel strain limits for section classification (ACI 318M-08 10.3.3 / 10.3.4)
EPSILON_TY = 0.002          # approx. yield strain for Grade 420 (fy / Es)
EPSILON_TENSION_CONTROLLED = 0.005

# ---------------------------------------------------------------------------
# Strength reduction factors, phi (ACI 318M-08 9.3.2)
# ---------------------------------------------------------------------------

PHI_TENSION_CONTROLLED = 0.90
PHI_COMPRESSION_CONTROLLED_TIED = 0.65
PHI_COMPRESSION_CONTROLLED_SPIRAL = 0.75
PHI_SHEAR = 0.75
PHI_TORSION = 0.75
PHI_BEARING = 0.65

PHI = {
    "tension_controlled": PHI_TENSION_CONTROLLED,
    "compression_controlled_tied": PHI_COMPRESSION_CONTROLLED_TIED,
    "compression_controlled_spiral": PHI_COMPRESSION_CONTROLLED_SPIRAL,
    "shear": PHI_SHEAR,
    "torsion": PHI_TORSION,
    "bearing": PHI_BEARING,
}

# ---------------------------------------------------------------------------
# Standard metric deformed rebar (DBxx) - nominal areas in mm^2
# Key = bar designation, value = (nominal diameter [mm], nominal area [mm^2])
# ---------------------------------------------------------------------------


def _bar_area(diameter_mm):
    """Nominal cross-sectional area of a round bar, mm^2."""
    return math.pi * diameter_mm ** 2 / 4.0


_REBAR_DIAMETERS_MM = [10, 12, 16, 20, 25, 28, 32, 36, 40]

REBAR = {
    f"DB{d}": {"diameter": float(d), "area": round(_bar_area(d), 2)}
    for d in _REBAR_DIAMETERS_MM
}

# Plain round bars (RB) — common in Thailand for stirrups / temperature steel
REBAR["RB6"] = {"diameter": 6.0, "area": 28.27}
REBAR["RB9"] = {"diameter": 9.0, "area": 63.62}

# Convenience: designation -> nominal area (mm^2)
REBAR_AREAS = {name: props["area"] for name, props in REBAR.items()}


def bar_area(designation):
    """Return the nominal area (mm^2) for a bar designation such as 'DB20'."""
    key = designation.upper()
    if key not in REBAR:
        raise KeyError(
            f"Unknown rebar designation {designation!r}. "
            f"Available: {', '.join(sorted(REBAR))}"
        )
    return REBAR[key]["area"]


def bars_area(designation, n):
    """Total steel area (mm^2) of ``n`` bars of the given designation."""
    return n * bar_area(designation)


# ---------------------------------------------------------------------------
# Flexure helpers
# ---------------------------------------------------------------------------


def beta1(fc):
    """Equivalent stress block factor beta1 (ACI 318M-08 10.2.7.3).

    fc : specified concrete compressive strength, MPa
    """
    if fc <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)


def rho_min_flexure(fc, fy):
    """Minimum flexural reinforcement ratio (ACI 318M-08 10.5.1).

        rho_min = max( 0.25 * sqrt(fc) / fy ,  1.4 / fy )

    fc, fy : MPa. Returns a dimensionless ratio (As_min / (b * d)).
    """
    return max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)


def as_min_flexure(fc, fy, b, d):
    """Minimum flexural steel area As_min (mm^2) for a section b x d.

    fc, fy : MPa
    b      : section width (mm)
    d      : effective depth (mm)
    """
    return rho_min_flexure(fc, fy) * b * d


def rho_balanced(fc, fy):
    """Balanced reinforcement ratio (ACI 318M-08 10.3.2)."""
    return (
        0.85 * beta1(fc) * fc / fy
        * (EPSILON_CU * ES) / (EPSILON_CU * ES + fy)
    )


def rho_max_flexure(fc, fy):
    """Maximum flexural ratio for a tension-controlled section.

    Corresponds to a net tensile strain of 0.005 (ACI 318M-08 10.3.4),
    i.e. c/d = 3/8.
    """
    return (
        0.85 * beta1(fc) * fc / fy
        * EPSILON_CU / (EPSILON_CU + EPSILON_TENSION_CONTROLLED)
    )


def phi_flexure(epsilon_t, spiral=False):
    """Strength reduction factor for a flexural / axial section
    from the net tensile strain in the extreme steel (ACI 318M-08 9.3.2).

    epsilon_t : net tensile strain at nominal strength
    spiral    : True for spiral-confined members, False for tied
    """
    phi_c = PHI_COMPRESSION_CONTROLLED_SPIRAL if spiral else PHI_COMPRESSION_CONTROLLED_TIED

    if epsilon_t <= EPSILON_TY:
        return phi_c
    if epsilon_t >= EPSILON_TENSION_CONTROLLED:
        return PHI_TENSION_CONTROLLED
    # Linear interpolation in the transition region
    return phi_c + (PHI_TENSION_CONTROLLED - phi_c) * (
        (epsilon_t - EPSILON_TY) / (EPSILON_TENSION_CONTROLLED - EPSILON_TY)
    )


# ---------------------------------------------------------------------------
# Shear helpers
# ---------------------------------------------------------------------------


def vc_beam(fc, bw, d, lam=1.0):
    """Nominal shear strength provided by concrete for non-prestressed
    members without axial force (ACI 318M-08 11.2.1.1, Eq. 11-3):

        Vc = 0.17 * lambda * sqrt(fc) * bw * d      [N]

    fc      : MPa
    bw, d   : mm
    lam     : lightweight-concrete modification factor lambda
    """
    return 0.17 * lam * math.sqrt(fc) * bw * d


# ===========================================================================
# Short convenience API
# ---------------------------------------------------------------------------
# Compact aliases with the plain names used elsewhere in the app. These sit
# on top of the fuller API above; both stay in sync.
# ===========================================================================

# 1. Strength reduction factors (ACI 318M-08 9.3.2)
phi = {
    "flexure": PHI_TENSION_CONTROLLED,          # 0.90
    "shear": PHI_SHEAR,                         # 0.75
    "compression_tied": PHI_COMPRESSION_CONTROLLED_TIED,     # 0.65
    "compression_spiral": PHI_COMPRESSION_CONTROLLED_SPIRAL,  # 0.75
}

# 2. Standard bar menu -> nominal area (mm^2).  Round bars RB6 / RB9 first
#    (stirrups / temperature steel), then the deformed-bar range.
rebars = {
    name: REBAR[name]["area"]
    for name in ("RB6", "RB9",
                 "DB12", "DB16", "DB20", "DB25", "DB28", "DB32")
}


def get_beta1(fc):
    """beta1 stress-block factor for concrete strength fc' (MPa).

        fc <= 28          : 0.85
        28 < fc < 56      : 0.85 - 0.05 * (fc - 28) / 7
        fc >= 56          : 0.65
    (ACI 318M-08 10.2.7.3)
    """
    return beta1(fc)


def calc_As_min(fc, fy, b, d):
    """Minimum flexural reinforcement area (mm^2), ACI 318M-08 10.5.1.

        As_min = max(0.25*sqrt(fc)/fy, 1.4/fy) * b * d

    fc, fy : MPa      b, d : mm
    """
    return as_min_flexure(fc, fy, b, d)
