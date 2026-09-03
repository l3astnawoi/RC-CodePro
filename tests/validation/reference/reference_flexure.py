"""EV-02 — Independent singly-reinforced flexure references.

Independent validation reference — NOT production calculation code.
No import of modules.* or utils.* — the equations below are the standard
ACI 318M-08 rectangular-stress-block relations, written out explicitly.

Two entry points:

* ``singly_reinforced_capacity_mks`` — given As, return a, c, eps_t, phi,
  Mn, phi*Mn (used to validate beam ``_flex_ksc`` and, by inspection, the
  MKS slab/stair helpers).
* ``required_As_singly_reinforced`` — given a factored moment, return the
  required tension-steel area (used to validate beam ``_required_as``,
  slab/stair ``_required_as_flexure`` / ``_as_flexure_ksc`` and footing
  ``_flexure_as``).  Unit-system agnostic: pass a consistent set.
"""

import math


def singly_reinforced_capacity_mks(As_cm2, fy_ksc, fc_ksc, b_cm, d_cm,
                                   eps_cu=0.003):
    """Nominal + design flexural capacity of one tension layer, MKS units.

    Whitney rectangular stress block (ACI 318M-08 10.2.7):
        a  = As*fy / (0.85 f'c b)
        c  = a / beta1
        eps_t = eps_cu * (d - c) / c
        Mn = As*fy*(d - a/2)            [kgf-cm]  ->  /100 -> kgf-m
        phi from eps_t (ACI 9.3.2), tied

    Returns a dict with every intermediate value so the comparison is
    fully traceable.
    """
    if fc_ksc <= 280.0:
        beta1 = 0.85
    else:
        beta1 = max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)

    a = As_cm2 * fy_ksc / (0.85 * fc_ksc * b_cm)          # cm
    c = a / beta1                                         # cm
    eps_t = eps_cu * (d_cm - c) / c if c > 0 else float("inf")

    # ACI 9.3.2 phi, tied, eps_ty = 0.002 literal
    if eps_t <= 0.002:
        phi = 0.65
    elif eps_t >= 0.005:
        phi = 0.90
    else:
        phi = 0.65 + 0.25 * (eps_t - 0.002) / 0.003

    Mn_kgfm = As_cm2 * fy_ksc * (d_cm - a / 2.0) / 100.0  # kgf-m
    return {
        "beta1": beta1,
        "a_cm": a,
        "c_cm": c,
        "eps_t": eps_t,
        "tension_controlled": eps_t >= 0.005,
        "phi_code": phi,
        "phi_engine_assumed": 0.90,   # _flex_ksc hardcodes phi['flexure']
        "Mn_kgfm": Mn_kgfm,
        "phiMn_kgfm_code": phi * Mn_kgfm,
        "phiMn_kgfm_engine": 0.90 * Mn_kgfm,
    }


def required_As_singly_reinforced(Mu, phi_f, b, d, fc, fy):
    """Required tension steel for a singly-reinforced tension-controlled
    rectangular section (ACI 318M-08 10.2), unit-system agnostic.

    Caller supplies a *consistent* set:
        SI  : Mu [N-mm],  b,d [mm],   fc,fy [MPa]   -> As [mm^2]
        MKS : Mu [kgf-cm], b,d [cm],  fc,fy [ksc]   -> As [cm^2]

    Solve  Mu/phi = Rn * b * d^2  with
        Rn = rho*fy*(1 - 0.5*rho*fy/(0.85 f'c))
    inverted as
        rho = (0.85 f'c / fy) * (1 - sqrt(1 - 2 Rn / (0.85 f'c)))

    Returns (As, Rn, rho, feasible).  feasible is False when the section
    cannot develop Mu (the sqrt argument goes negative).
    """
    Rn = Mu / (phi_f * b * d ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    if disc < 0.0:
        return None, Rn, None, False
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
    return rho * b * d, Rn, rho, True


def as_min_temp_ratio(fy_mpa):
    """Shrinkage & temperature steel ratio (ACI 318M-08 7.12.2.1), fy in MPa:
        fy <= 350 (Grade 300)      -> 0.0020
        350 < fy <= 420 (Gr. 420)  -> 0.0018
        fy > 420                    -> max(0.0018*420/fy, 0.0014)
    """
    if fy_mpa <= 350.0:
        return 0.0020
    if fy_mpa <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy_mpa, 0.0014)


def as_min_flexure_ksc(fc_ksc, fy_ksc, b_cm, d_cm):
    """ACI 318M-08 10.5.1, MKS:  As_min = max(0.8 sqrt(f'c)/fy, 14/fy) b d."""
    rho = max(0.8 * math.sqrt(fc_ksc) / fy_ksc, 14.0 / fy_ksc)
    return rho * b_cm * d_cm


def bar_spacing_for(As_bar_cm2, As_req_cm2, s_max_cm):
    """Independent reproduction of the modules' bar-spacing rule, for a
    1 m (100 cm) design strip:
        S_req = As_bar * 100 / As_req
        S     = clamp( floor(S_req / 2.5) * 2.5 , 2.5 , s_max )
        As_provided = As_bar * 100 / S
    Returns (S_cm, As_prov_cm2_per_m).  (Discrete rounding rule — validate
    with exact equality.)
    """
    if As_req_cm2 <= 1.0e-9:
        S = s_max_cm
    else:
        S_req = As_bar_cm2 * 100.0 / As_req_cm2
        S = min(math.floor(S_req / 2.5) * 2.5, s_max_cm)
        S = max(S, 2.5)
    return S, As_bar_cm2 * 100.0 / S
