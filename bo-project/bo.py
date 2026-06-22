import numpy as np
from math import erfc, sqrt, exp, pi
from typing import Callable, TypedDict


class BOResult(TypedDict):
    mu: list[float]
    sigma: list[float]
    acq: list[float]
    next_x: float


# ── Kernel ──────────────────────────────────────────────────────────────────
def rbf_kernel(X1: np.ndarray, X2: np.ndarray,
               length_scale: float, signal_var: float) -> np.ndarray:
    """
    RBF (squared exponential) kernel matrix.

    k(x, x') = signal_var * exp(-||x - x'||^2 / (2 * length_scale^2))

    X1: array of shape (n,)
    X2: array of shape (m,)
    Returns kernel matrix of shape (n, m).
    """

    X1 = np.atleast_1d(X1).ravel()
    X2 = np.atleast_1d(X2).ravel()
    sq_dists = (X1[:, None] - X2[None, :]) ** 2
    return signal_var * np.exp(-sq_dists / (2.0 * length_scale ** 2))


# ── GP Posterior ─────────────────────────────────────────────────────────────

def gp_posterior(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray,
                 length_scale: float, signal_var: float,
                 noise_var: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute GP posterior mean and variance at X_test given training data.

    Inverts via Cholesky decomposition.

    Returns mu and sigma as (m,) vectors.
    """

    X_train = np.atleast_1d(X_train)
    y_train = np.atleast_1d(y_train)
    X_test = np.atleast_1d(X_test)

    # K = kernel(X, X) + σ²_n · I
    K = rbf_kernel(X_train, X_train, length_scale, signal_var)
    K += noise_var * np.eye(len(X_train))

    # K* = kernel(X, X*);  K** diagonal = signal_var for RBF
    k_star = rbf_kernel(X_train, X_test, length_scale, signal_var)  # (n, m)
    k_starstar_diag = signal_var * np.ones(len(X_test))  # (m,)

    L = np.linalg.cholesky(K)  # L @ L.T = K
    alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_train))
    # posterior mean = k*ᵀ K⁻¹ y
    mu = k_star.T @ alpha  # (m,)

    v = np.linalg.solve(L, k_star)  # (n, m)
    # posterior variance = k** − k*ᵀ K⁻¹ k*
    var = k_starstar_diag - np.sum(v ** 2, axis=0)  # (m,)
    # clip numerical negatives
    var = np.maximum(var, 0.0)
    sigma = np.sqrt(var)

    return mu, sigma


# ── Acquisition Functions ────────────────────────────────────────────────────

def acquisition_ucb(mu: np.ndarray, sigma: np.ndarray, kappa: float) -> np.ndarray:
    """
    Upper Confidence Bound acquisition.

    a(x) = mu(x) + kappa * sigma(x)

    kappa: exploration weight; higher → more exploration (typical range 1–5)
    Returns (m,) acquisition values.
    """
    return mu + kappa * sigma


def _standard_normal_cdf(z: float) -> float:
    """Phi(z)."""
    return 0.5 * erfc(-z / sqrt(2.0))


def _standard_normal_pdf(z: float) -> float:
    """phi(z)."""
    return exp(-0.5 * z * z) / sqrt(2.0 * pi)


def acquisition_ei(mu: np.ndarray, sigma: np.ndarray,
                   y_best: float, xi: float = 0.01) -> np.ndarray:
    """
    Expected Improvement acquisition.

    a(x) = (mu(x) - y_best - xi) * Phi(Z) + sigma(x) * phi(Z)
    where Z = (mu(x) - y_best - xi) / sigma(x)

    Set a(x) = 0 where sigma(x) == 0 (no uncertainty).

    y_best: best observed value so far
    xi: jitter / exploration bonus (default 0.01)
    Returns (m,) acquisition values.
    """
    mu = np.asarray(mu)
    sigma = np.asarray(sigma)
    a = np.zeros_like(mu)

    mask = sigma > 0.0
    if not np.any(mask):
        # No uncertainty at any point
        return a

    imp = mu[mask] - y_best - xi
    Z = imp / sigma[mask]

    cdf_vals = np.array([_standard_normal_cdf(z) for z in Z])
    pdf_vals = np.array([_standard_normal_pdf(z) for z in Z])

    a[mask] = imp * cdf_vals + sigma[mask] * pdf_vals
    a[mask] = np.maximum(a[mask], 0.0)
    return a


# ── Acquisition Maximization ─────────────────────────────────────────────────

def maximize_acquisition(X_grid: np.ndarray, mu: np.ndarray, sigma: np.ndarray,
                         acq_type: str, kappa: float, xi: float,
                         y_best: float) -> tuple[float, np.ndarray]:
    """
    Return the maximizing x value and full acquisition curve.

    X_grid: (m,) grid of candidate x values
    acq_type: 'ucb' or 'ei'
    Returns (next_x, acq_values) where acq_values is the (m,) acquisition curve.
    """
    if acq_type == 'ucb':
        acq = acquisition_ucb(mu, sigma, kappa)
    elif acq_type == 'ei':
        acq = acquisition_ei(mu, sigma, y_best, xi)
    else:
        raise ValueError(f"Unknown acquisition type: {acq_type!r}")

    idx = int(np.argmax(acq))
    next_x = float(X_grid[idx])
    return next_x, acq


# ── Target Functions ─────────────────────────────────────────────────────────

def target_sine(x: float) -> float:
    """sin(6*pi*x) — simple oscillating function on [0, 1]."""
    return float(np.sin(6.0 * pi * x))


def target_bumpy(x: float) -> float:
    """sin(6*pi*x) + 0.5*sin(14*pi*x) — higher-frequency bumps."""
    return float(np.sin(6.0 * pi * x) + 0.5 * np.sin(14.0 * pi * x))


def target_multimodal(x: float) -> float:
    """Sum of three Gaussian bumps — multiple local optima."""
    centers = [0.2, 0.55, 0.85]
    heights = [1.0, 0.8, 1.2]
    widths = [0.08, 0.10, 0.07]
    return float(sum(h * np.exp(-0.5 * ((x - c) / w) ** 2)
                     for c, h, w in zip(centers, heights, widths)))


def target_easy(x: float) -> float:
    """Single wide Gaussian peak — BO converges in a few steps."""
    return float(np.exp(-0.5 * ((x - 0.6) / 0.2) ** 2))


TARGET_FUNCTIONS: dict[str, Callable[[float], float]] = {
    'sine': target_sine,
    'bumpy': target_bumpy,
    'multimodal': target_multimodal,
    'easy': target_easy,
}


# ── Full BO Step ─────────────────────────────────────────────────────────────

def bo_step(X_train: np.ndarray, y_train: np.ndarray, X_grid: np.ndarray,
            length_scale: float, signal_var: float, noise_var: float,
            acq_type: str, kappa: float, xi: float) -> BOResult:
    """
    Run one full BO step: compute GP posterior on X_grid, maximize acquisition.

    X_train: (n,) observed x locations
    y_train: (n,) observed y values (may include noise)
    X_grid: (m,) evaluation grid for GP posterior and acquisition
    length_scale, signal_var, noise_var: GP hyperparameters
    acq_type: 'ucb' or 'ei'
    kappa: UCB exploration weight
    xi: EI jitter
    """
    mu, sigma = gp_posterior(X_train, y_train, X_grid,
                              length_scale, signal_var, noise_var)

    y_best = float(np.max(y_train)) if len(y_train) > 0 else 0.0
    next_x, acq = maximize_acquisition(X_grid, mu, sigma,
                                        acq_type, kappa, xi, y_best)

    return {
        'mu':     mu.tolist(),
        'sigma':  sigma.tolist(),
        'acq':    acq.tolist(),
        'next_x': next_x,
    }
