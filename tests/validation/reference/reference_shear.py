"""EV-02 — Independent beam one-way shear reference (ACI 318M-08 11.x).

Independent validation reference — NOT production calculation code.
No import of modules.beam or utils.aci_318m.

SI units throughout: forces N, stresses MPa, lengths mm.
"""

import math


def beam_shear_capacity_si(Vu_N, bw_mm, d_mm, fc_mpa, fyt_mpa,
                           Av_mm2, s_mm, lam=1.0, phi_v=0.75):
    """Reproduce, from the ACI equations, the quantities the engine's
    ``_shear_check`` returns.

        Vc     = 0.17 * lambda * sqrt(f'c) * bw * d               (11.2.1.1)
        Vs     = Av * fyt * d / s                                 (11.4.7.2)
        Vs_max = 0.66 * sqrt(f'c) * bw * d                        (11.4.7.9)
        phi*Vn = phi*Vc + phi*min(Vs, Vs_max)
        s_max  = min(d/2, 600 mm)  ; if Vs > 0.33 sqrt(f'c) bw d :
                 s_max = min(d/4, 300 mm)                         (11.4.5)
        ok     = (phi*Vn >= Vu) and (Vs <= Vs_max) and (s <= s_max)

    Returns a dict of every intermediate value + the boolean verdict.
    Note: the engine's ``Av`` is fixed at 2 * (stirrup bar area) — a
    two-leg closed stirrup is assumed.
    """
    s = math.sqrt(fc_mpa)
    Vc = 0.17 * lam * s * bw_mm * d_mm
    phiVc = phi_v * Vc
    Vs = (Av_mm2 * fyt_mpa * d_mm / s_mm) if s_mm > 0 else 0.0
    Vs_max = 0.66 * s * bw_mm * d_mm
    phiVs = phi_v * min(Vs, Vs_max)
    phiVn = phiVc + phiVs

    s_max = min(d_mm / 2.0, 600.0)
    if Vs > 0.33 * s * bw_mm * d_mm:
        s_max = min(d_mm / 4.0, 300.0)

    ok = (phiVn >= Vu_N) and (Vs <= Vs_max) and (s_mm <= s_max)
    return {
        "Vc_N": Vc,
        "phiVc_N": phiVc,
        "Vs_N": Vs,
        "Vs_max_N": Vs_max,
        "phiVs_N": phiVs,
        "phiVn_N": phiVn,
        "s_max_mm": s_max,
        "half_d_rule": Vs > 0.33 * s * bw_mm * d_mm,
        "ok": bool(ok),
    }
