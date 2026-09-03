"""EV-02 — Independent continuous-beam reference (three-moment method).

Independent validation reference — NOT production calculation code.
It does NOT import utils.analysis and NEVER calls solve_continuous_beam().

Method: Clapeyron's Three-Moment Theorem + statics.  This is a different
formulation from the engine's direct-stiffness (Euler-Bernoulli element)
solver, so agreement is a genuine cross-check, not a tautology.

Sign convention: span moments sagging-positive; interior-support moments
come out negative (hogging).  A uniform load w is applied on every span.

Units (matching the engine): span lengths m, load kgf/m, reactions kgf,
shear kgf, moment kgf-m.
"""

import numpy as np


def _support_moments_udl(spans, w):
    """Solve the interior support moments for a continuous beam on simple
    end supports carrying a full-span UDL ``w`` on every span.

    Three-moment equation at interior support i (between spans L_a, L_b):
        M_{i-1} L_a + 2 M_i (L_a + L_b) + M_{i+1} L_b
            = -( w L_a^3 / 4  +  w L_b^3 / 4 )
    (the RHS term  6 A xbar / L  equals  w L^3 / 4  for a full-span UDL).
    End support moments are zero (simple supports).
    """
    n_span = len(spans)
    n_sup = n_span + 1
    M = np.zeros(n_sup)
    n_int = n_sup - 2
    if n_int <= 0:
        return M  # single span -> all support moments zero

    A = np.zeros((n_int, n_int))
    rhs = np.zeros(n_int)
    for k in range(n_int):       # k -> interior support index i = k + 1
        La = spans[k]
        Lb = spans[k + 1]
        A[k, k] = 2.0 * (La + Lb)
        if k - 1 >= 0:
            A[k, k - 1] = La
        if k + 1 < n_int:
            A[k, k + 1] = Lb
        rhs[k] = -(w * La ** 3 / 4.0 + w * Lb ** 3 / 4.0)

    M[1:-1] = np.linalg.solve(A, rhs)
    return M


def solve_continuous_beam_reference(spans_m, w_kgf_per_m, n_grid=200):
    """Independent solution.  Returns a dict comparable to the engine's
    output keys, plus analytic per-span positive-moment peaks.

        reactions_kgf     : support reactions (kgf, +up)
        support_moments    : bending moment at each support (kgf-m)
        Mu_pos_analytic    : governing +M from the exact per-span parabola
        Mu_neg_analytic    : governing -M (max hogging magnitude)
        Vu_analytic        : governing |shear|
        Mu_pos_on_grid     : max of the EXACT M(x) sampled on a uniform grid
                             of n_grid points (for the VF-04 sampled-peak
                             comparison — this is analytic M, sampled, NOT
                             the engine's solver output)
        x, M               : the sampling grid and exact M(x) on it
    """
    spans = [float(s) for s in spans_m if float(s) > 0.0]
    if not spans:
        raise ValueError("need at least one positive span")
    w = float(w_kgf_per_m)
    n_span = len(spans)

    Msup = _support_moments_udl(spans, w)
    xs = np.concatenate(([0.0], np.cumsum(spans)))
    Ltot = float(xs[-1])

    # --- reactions: sum of each adjacent span's end reaction --------------
    R = np.zeros(n_span + 1)
    span_endR = []           # (R_left, R_right) per span
    for e, L in enumerate(spans):
        Ml, Mr = Msup[e], Msup[e + 1]
        # simple-beam UDL reaction (wL/2) + moment-couple correction.
        # Verified sign: 2 equal spans -> R_end = 3wL/8, R_mid = 5wL/4.
        Rl = w * L / 2.0 + (Mr - Ml) / L
        Rr = w * L / 2.0 + (Ml - Mr) / L
        span_endR.append((Rl, Rr))
        R[e] += Rl
        R[e + 1] += Rr

    # --- exact M(x) and V(x) span by span --------------------------------
    x_grid = np.linspace(0.0, Ltot, int(n_grid))
    M_grid = np.zeros_like(x_grid)
    pos_peaks = []
    neg_peaks = []
    shear_extrema = []
    for e, L in enumerate(spans):
        x0 = xs[e]
        Rl = span_endR[e][0]
        Ml = Msup[e]
        # local coordinate xi in [0, L]
        mask = (x_grid >= x0 - 1e-12) & (x_grid <= x0 + L + 1e-12)
        xi = x_grid[mask] - x0
        M_local = Ml + Rl * xi - w * xi ** 2 / 2.0
        M_grid[mask] = M_local
        # analytic positive peak: dM/dxi = Rl - w xi = 0 -> xi* = Rl/w
        if w != 0.0:
            xi_star = Rl / w
            if 0.0 <= xi_star <= L:
                pos_peaks.append(Ml + Rl * xi_star - w * xi_star ** 2 / 2.0)
        pos_peaks.append(M_local.max())
        neg_peaks.append(M_local.min())
        # shear at the two ends of the span
        shear_extrema.append(abs(Rl))
        shear_extrema.append(abs(Rl - w * L))

    Mu_pos = max(0.0, max(pos_peaks))
    Mu_neg = max(0.0, -min(neg_peaks + list(Msup)))
    Vu = max(shear_extrema)

    return {
        "spans_m": spans,
        "w_kgf_per_m": w,
        "reactions_kgf": [float(v) for v in R],
        "support_moments_kgfm": [float(v) for v in Msup],
        "Mu_pos_analytic_kgfm": float(Mu_pos),
        "Mu_neg_analytic_kgfm": float(Mu_neg),
        "Vu_analytic_kgf": float(Vu),
        "Mu_pos_on_grid_kgfm": float(np.max(M_grid)),
        "x": x_grid,
        "M": M_grid,
    }


def sampled_peak_analysis(span_m, w_kgf_per_m):
    """VF-04 helper for a SINGLE simply-supported span.

    Exact:  M(x) = w x (L - x) / 2 ,  peak w L^2 / 8 at x = L/2.
    The engine samples M on  np.linspace(0, L, max(80*1, 200)) = 200 pts
    (plus 3 points clustered at each support, none near mid-span), so its
    reported ``Mu_pos_kgfm`` is the largest of those samples.

    Returns exact peak, the peak of the EXACT parabola evaluated on that
    same 200-point grid, their difference, and a suggested tolerance.
    """
    L = float(span_m)
    w = float(w_kgf_per_m)
    M_exact = w * L ** 2 / 8.0

    n = max(80 * 1, 200)                       # engine: max(n_points*n_span, 200)
    xg = np.linspace(0.0, L, n)
    Mg = w * xg * (L - xg) / 2.0
    M_grid_peak = float(Mg.max())

    # worst-case parabola sampling error near the vertex for step h:
    #   a node at h/2 from the vertex misses by  (w/2)*(h/2)^2
    h = L / (n - 1)
    err_bound = (w / 2.0) * (h / 2.0) ** 2

    return {
        "L_m": L, "w_kgf_per_m": w,
        "M_exact_kgfm": M_exact,
        "M_sampled_grid_peak_kgfm": M_grid_peak,
        "abs_diff_kgfm": M_exact - M_grid_peak,
        "rel_diff": (M_exact - M_grid_peak) / M_exact if M_exact else 0.0,
        "sampling_error_bound_kgfm": err_bound,
        "direction": "sampling UNDER-estimates the true peak",
    }
