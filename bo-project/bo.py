import numpy as np
from math import erfc, sqrt, exp


# ── Kernel ──────────────────────────────────────────────────────────────────
# Using the popular RBF kernel as our metric of how close two points are
# Using NumPy for ease and efficiency
def rbf_kernel(X1, X2, length_scale, signal_var):
    """
    RBF (squared exponential) kernel matrix.

    k(x, x') = signal_var * exp(-||x - x'||^2 / (2 * length_scale^2))

    X1 : array of shape (n, 1) or (n,)
    X2 : array of shape (m, 1) or (m,)
    Returns kernel matrix of shape (n, m).
    """

    # Convert X1 and X2 to column vectors
    X1 = np.atleast_1d(X1).reshape(-1, 1)  # shape (n, 1)
    X2 = np.atleast_1d(X2).reshape(-1, 1)  # shape (m, 1)

    # Use broadcasting to set up difference matrix 
    #   for each pair (i, j) from X1 and X2
    expanded_X1 = X1[:, None, :]  # shape (n, 1, 1)
    expanded_X2 = X2[None, :, :]  # shape (1, m, 1)
    diff_mat = expanded_X1 - expanded_X2  # shape (n, m, 1)

    # Due to broadcasting, at location (i, j, 1) of diff_mat, 
    #   X1[i] - X2[j] is stored. Now calculate the matrix of squared distances
    #   Summing over axis=-1 sums across (removes) third dimension
    sq_dists = np.sum(diff_mat ** 2, axis=-1)

    # We've done the hard part, so now plug into final RBF formula
    return signal_var * np.exp(-sq_dists / (2.0 * length_scale ** 2))


# ── GP Posterior ─────────────────────────────────────────────────────────────

def gp_posterior(X_train, y_train, X_test, length_scale, signal_var, noise_var):
    """
    Compute GP posterior mean and variance at X_test given training data.

    Uses Cholesky decomposition for numerical stability (never inverts K directly).

    Returns
    -------
    mu    : (m,) posterior mean at each test point
    sigma : (m,) posterior standard deviation at each test point
    """

    # Ensure correct NumPy conversion
    X_train = np.atleast_1d(X_train)
    y_train = np.atleast_1d(y_train)
    X_test  = np.atleast_1d(X_test)

    # Given array of training x-values, X:
    # K = kernel(X, X) + σ²_n · I
    # Covariance matrix of X points with each other, plus noise 
    K      = rbf_kernel(X_train, X_train, length_scale, signal_var)
    K     += noise_var * np.eye(len(X_train))

    # Given array of testing x-values, X*:
    # K* = kernel(X, X*), covariance between the points X and the points X*
    # K** = kernel(X*, X*), prior variance at each X* — for the RBF kernel,
    #   k(x*, x*) = signal_var * e^0 = signal_var, so the diagonal is constant
    k_star          = rbf_kernel(X_train, X_test, length_scale, signal_var)  # (n, m)
    k_starstar_diag = signal_var * np.ones(len(X_test))                      # (m,)

    # Cholesky decomposition: L such that L @ L.T = K
    L     = np.linalg.cholesky(K)
    # Compute K⁻¹ y most efficiently, using Cholesky decomposition (most efficient)
    alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_train))                # K⁻¹ y
    # mu (posterior mean) = k*ᵀ K⁻¹ y
    mu    = k_star.T @ alpha                                                 # (m,)

    v   = np.linalg.solve(L, k_star)                                         # (n, m)
    # σ² (posterior variance) = k** − k*ᵀ K⁻¹ k* 
    var = k_starstar_diag - np.sum(v ** 2, axis=0)                           # (m,)
    var    = np.maximum(var, 0.0)                                            # clip numerical negatives
    sigma  = np.sqrt(var)

    return mu, sigma


# ── Acquisition Functions ────────────────────────────────────────────────────

def acquisition_ucb(mu, sigma, kappa):
    """
    Upper Confidence Bound acquisition.

    a(x) = mu(x) + kappa * sigma(x)

    kappa : exploration weight; higher → more exploration (typical range 1–5)
    Returns (m,) acquisition values.
    """
    return mu + kappa * sigma


def _standard_normal_cdf(z):
    """Phi(z) using math.erfc — avoids scipy dependency."""
    return 0.5 * erfc(-z / sqrt(2.0))


def _standard_normal_pdf(z):
    """phi(z)."""
    return exp(-0.5 * z * z) / sqrt(2.0 * np.pi)


def acquisition_ei(mu, sigma, y_best, xi=0.01):
    """
    Expected Improvement acquisition.

    a(x) = (mu(x) - y_best - xi) * Phi(Z) + sigma(x) * phi(Z)
    where Z = (mu(x) - y_best - xi) / sigma(x)

    Set a(x) = 0 where sigma(x) == 0 (no uncertainty).

    y_best : best observed value so far
    xi     : jitter / exploration bonus (default 0.01)
    Returns (m,) acquisition values.
    """
    mu    = np.asarray(mu)
    sigma = np.asarray(sigma)
    a     = np.zeros_like(mu)

    # Test which points have nonzero uncertainty and apply the formula
    mask = sigma > 0.0
    if not np.any(mask):
        # We have no uncertainty at any point
        return a

    # Find Z
    imp  = mu[mask] - y_best - xi
    Z    = imp / sigma[mask]

    # Compute Phi(Z) and phi(z), respectively
    cdf_vals = np.array([_standard_normal_cdf(z) for z in Z])
    pdf_vals = np.array([_standard_normal_pdf(z) for z in Z])

    # Calculate EI acquisition values
    a[mask] = imp * cdf_vals + sigma[mask] * pdf_vals
    a[mask] = np.maximum(a[mask], 0.0)
    return a


# ── Acquisition Maximization ─────────────────────────────────────────────────

def maximize_acquisition(X_grid, mu, sigma, acq_type, kappa, xi, y_best):
    """
    Return the index of the grid point that maximizes the acquisition function.

    X_grid   : (m,) grid of candidate x values
    acq_type : 'ucb' or 'ei'
    Returns (next_x, acq_values) where acq_values is the (m,) acquisition curve.
    """
    if acq_type == 'ucb':
        acq = acquisition_ucb(mu, sigma, kappa)
    elif acq_type == 'ei':
        acq = acquisition_ei(mu, sigma, y_best, xi)
    else:
        raise ValueError(f"Unknown acquisition type: {acq_type!r}")

    idx    = int(np.argmax(acq))
    next_x = float(X_grid[idx])
    return next_x, acq


# ── Target Functions ─────────────────────────────────────────────────────────

def target_sine(x):
    """sin(6*pi*x) — simple oscillating function on [0, 1]."""
    return float(np.sin(6.0 * np.pi * x))


def target_bumpy(x):
    """sin(6*pi*x) + 0.5*sin(14*pi*x) — higher-frequency bumps."""
    return float(np.sin(6.0 * np.pi * x) + 0.5 * np.sin(14.0 * np.pi * x))


def target_multimodal(x):
    """Sum of three Gaussian bumps — multiple local optima."""
    centers  = [0.2, 0.55, 0.85]
    heights  = [1.0, 0.8, 1.2]
    widths   = [0.08, 0.10, 0.07]
    return float(sum(h * np.exp(-0.5 * ((x - c) / w) ** 2)
                     for c, h, w in zip(centers, heights, widths)))


def target_easy(x):
    """Single wide Gaussian peak — BO converges in a few steps."""
    return float(np.exp(-0.5 * ((x - 0.6) / 0.2) ** 2))


TARGET_FUNCTIONS = {
    'sine':       target_sine,
    'bumpy':      target_bumpy,
    'multimodal': target_multimodal,
    'easy':       target_easy,
}


# ── Full BO Step ─────────────────────────────────────────────────────────────

def bo_step(X_train, y_train, X_grid,
            length_scale, signal_var, noise_var,
            acq_type, kappa, xi):
    """
    Run one full BO step: compute GP posterior on X_grid, maximize acquisition.

    Parameters
    ----------
    X_train     : (n,) observed x locations
    y_train     : (n,) observed y values (may include noise)
    X_grid      : (m,) evaluation grid for GP posterior and acquisition
    length_scale, signal_var, noise_var : GP hyperparameters
    acq_type    : 'ucb' or 'ei'
    kappa       : UCB exploration weight
    xi          : EI jitter

    Returns dict with keys: mu, sigma, acq, next_x
    """
    mu, sigma = gp_posterior(X_train, y_train, X_grid,
                              length_scale, signal_var, noise_var)

    y_best    = float(np.max(y_train)) if len(y_train) > 0 else 0.0
    next_x, acq = maximize_acquisition(X_grid, mu, sigma,
                                        acq_type, kappa, xi, y_best)

    return {
        'mu':     mu.tolist(),
        'sigma':  sigma.tolist(),
        'acq':    acq.tolist(),
        'next_x': next_x,
    }
