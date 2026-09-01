"""Continuous-beam analysis — 1D matrix-stiffness (Euler-Bernoulli).

MKS units throughout:
    span lengths      -> m
    uniform load Wu    -> kgf/m
    reactions          -> kgf   (positive = upward)
    shear   V(x)       -> kgf
    moment  M(x)       -> kgf-m (positive = sagging / tension at the bottom)

A constant flexural rigidity ``EI = 1`` is assumed.  For a beam on
non-settling pin/roller supports EI cancels out of the reactions and the
internal forces, so the results depend only on the span lengths and the
applied load — exactly what the design tab needs for ``+Mu``, ``-Mu`` and
``Vu``.
"""

import numpy as np


def _beam_element_k(L):
    """4x4 Euler-Bernoulli beam-element stiffness (EI = 1).

    Local DOF order: [v_i, theta_i, v_j, theta_j]  (v = deflection, +y up).
    """
    L = float(L)
    return (1.0 / L ** 3) * np.array([
        [ 12.0,      6.0 * L,   -12.0,       6.0 * L],
        [ 6.0 * L,   4.0 * L * L, -6.0 * L,  2.0 * L * L],
        [-12.0,     -6.0 * L,    12.0,      -6.0 * L],
        [ 6.0 * L,   2.0 * L * L, -6.0 * L,  4.0 * L * L],
    ])


def solve_continuous_beam(spans_m, w_kgf_per_m, n_points=80):
    """Solve a continuous beam of ``len(spans_m)`` spans carrying a uniform
    factored load ``w_kgf_per_m`` on every span, on pin/roller supports.

    Returns a dict with the support reactions, the plotting arrays
    ``x`` / ``V`` / ``M`` and the governing ``Mu_pos_kgfm`` / ``Mu_neg_kgfm``
    / ``Vu_kgf``.
    """
    spans = [float(s) for s in spans_m if float(s) > 0.0]
    if not spans:
        raise ValueError("ต้องมีช่วงคานอย่างน้อย 1 ช่วง")
    w = float(w_kgf_per_m)
    n_span = len(spans)
    n_node = n_span + 1
    ndof = 2 * n_node

    # ---- assemble the global stiffness matrix & load vector ------------
    K = np.zeros((ndof, ndof))
    F = np.zeros(ndof)
    for e, L in enumerate(spans):
        ke = _beam_element_k(L)
        # work-equivalent nodal loads for a DOWNWARD udl w  (q = -w, +y up)
        fe = -w * np.array([L / 2.0, L * L / 12.0, L / 2.0, -L * L / 12.0])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += ke
        F[idx] += fe

    # ---- boundary conditions: v = 0 at every support, rotations free ---
    fixed = [2 * k for k in range(n_node)]
    free = [2 * k + 1 for k in range(n_node)]
    d = np.zeros(ndof)
    d[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])

    R = (K @ d - F)[fixed]                       # support reactions, kgf (+up)

    # ---- internal forces by integration from the reactions ------------
    xs = np.concatenate(([0.0], np.cumsum(spans)))     # support x-coords
    Ltot = float(xs[-1])

    base = np.linspace(0.0, Ltot, max(int(n_points) * n_span, 200))
    eps = max(Ltot * 1.0e-7, 1.0e-9)
    around = np.concatenate([[xk - eps, xk, xk + eps] for xk in xs])
    x = np.unique(np.clip(np.concatenate([base, around]), 0.0, Ltot))

    left = (xs[None, :] <= x[:, None])                 # (nx, n_node) mask
    V = (R[None, :] * left).sum(axis=1) - w * x                       # kgf
    M = (R[None, :] * left * (x[:, None] - xs[None, :])).sum(axis=1) \
        - w * x ** 2 / 2.0                                            # kgf-m

    return {
        "spans_m": spans,
        "w_kgf_per_m": w,
        "reactions_kgf": [float(r) for r in R],
        "x_supports_m": [float(v) for v in xs],
        "L_total_m": Ltot,
        "x": x, "V": V, "M": M,
        "Mu_pos_kgfm": float(max(M.max(), 0.0)),
        "Mu_neg_kgfm": float(max(-M.min(), 0.0)),
        "Vu_kgf": float(np.abs(V).max()),
    }
