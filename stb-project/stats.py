"""Cointegration statistics for the systematic trading backtester.

Public API:
    ols(y, X, add_const=True) -> (beta, resid)
    ols_with_se(y, X, add_const=True) -> (beta, resid, se, ssr, dof)
    hedge_ratio(a, b) -> (beta, alpha, spread)
    adf(series, max_lag=None, ...) -> (stat, pvalue, used_lag)
    engle_granger(a, b) -> dict
    rolling_zscore(series, window) -> np.ndarray
"""

import math
import numpy as np

def norm_cdf(x):
    """Standard-normal CDF via complementary error function."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def ols(y, X, add_const=True):
    """Solve y = X beta + e. Returns (beta, residuals).

    ``X`` may be 1-D (single regressor) or 2-D (n, k). A leading column of ones
    is prepended when ``add_const`` is True, so beta[0] is then the intercept.
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    if add_const:
        X = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return beta, resid


def ols_with_se(y, X, add_const=True):
    """OLS returning coefficient standard errors as well.

    Returns (beta, resid, se, ssr, dof). ``se`` are the classical
    (homoskedastic) standard errors: cov(beta) = s2 * inv(X'X), s2 = SSR / dof.
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    if add_const:
        X = np.column_stack([np.ones(len(X)), X])
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ssr = float(resid @ resid)
    dof = max(n - k, 1)
    s2 = ssr / dof
    # Robust to near-singular X'X via pseudo-inverse
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.maximum(np.diag(s2 * xtx_inv), 0.0))
    return beta, resid, se, ssr, dof


def hedge_ratio(a, b):
    """OLS of A on B with a constant: A = alpha + beta*B + spread.

    ``beta`` is the hedge ratio, ``alpha`` the intercept, and ``spread`` 
    the residual series used for the stationarity test and the trading signal.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    coef, resid = ols(a, b, add_const=True)
    alpha, beta = coef[0], coef[1]
    return beta, alpha, resid


# --------------------------------------------------------------------------- #
# MacKinnon (1994/2010) approximate p-values for the ADF tau statistic.
# Allows for lighter computation. Coefficients lifted from the published 
# response surfaces. ``N`` is the number of integrated series in a cointegrating 
# regression (1 for a plain unit-root test). Only N=1 is exercised here.
# --------------------------------------------------------------------------- #
_TAU_MAX = {"nc": np.inf, "c": 2.74, "ct": 0.7, "ctt": 0.54}
_TAU_MIN = {"nc": -19.04, "c": -18.83, "ct": -16.18, "ctt": -17.17}
_TAU_STAR = {"nc": -1.04, "c": -1.61, "ct": -2.89, "ctt": -3.21}
# Polynomial coefficients in increasing degree order [c0, c1, c2, (c3)]
_TAU_SMALLP = {
    "nc": [0.6344, 1.2378, 3.2496e-2],
    "c": [2.1659, 1.4412, 3.8269e-2],
    "ct": [3.2512, 1.6047, 4.9588e-2],
    "ctt": [4.0003, 1.6580, 4.8288e-2],
}
_TAU_LARGEP = {
    "nc": [0.4797, 9.3557e-2, -6.0090e-3, 1.5210e-4],
    "c": [1.7339, 9.3202e-2, -1.2745e-2, -1.0368e-3],
    "ct": [2.5261, 6.1654e-2, -3.7956e-2, -1.7253e-3],
    "ctt": [3.0778, 4.9529e-2, -4.1477e-2, -2.4575e-3],
}


def mackinnon_pvalue(stat, regression="c"):
    """Approximate p-value given ADF tau statistic (MacKinnon surface)."""
    if stat > _TAU_MAX[regression]:
        return 1.0
    if stat < _TAU_MIN[regression]:
        return 0.0
    if stat <= _TAU_STAR[regression]:
        coef = _TAU_SMALLP[regression]
    else:
        coef = _TAU_LARGEP[regression]
    # np.polyval wants highest-degree first
    val = np.polyval(coef[::-1], stat)
    return float(norm_cdf(val))


# --------------------------------------------------------------------------- #
# Augmented Dickey-Fuller test.
# --------------------------------------------------------------------------- #
def _adf_design(y, dy, ylag, p, common_start, regression):
    """Build (Y, X) for an ADF regression with ``p`` lagged differences.

    All candidate lag orders share the same observation window
    [common_start : len(dy)] so their information criteria are comparable.
    ``add_const`` is handled by the caller via the regression spec.
    """
    m = len(dy)
    Y = dy[common_start:]
    cols = [ylag[common_start:]]  # level term y_{t-1}
    for j in range(1, p + 1):
        cols.append(dy[common_start - j: m - j])  # lagged difference dy_{t-j}
    X = np.column_stack(cols)
    if regression in ("ct", "ctt"):
        trend = np.arange(common_start, m, dtype=float)
        X = np.column_stack([X, trend])
        if regression == "ctt":
            X = np.column_stack([X, trend ** 2])
    return Y, X


def adf(series, max_lag=None, regression="c", autolag="AIC"):
    """Augmented Dickey-Fuller unit-root test.

    Regress Δy_t on [const, y_{t-1}, Δy_{t-1}, ..., Δy_{t-p}] and form the
    t-statistic on the level coefficient y_{t-1}. A more negative statistic is
    stronger evidence against a unit root (i.e. for stationarity).

    Lag order is chosen by minimising ``autolag`` ("AIC" or "BIC") over a common
    sample, or fixed when ``autolag`` is None. Returns (stat, pvalue, used_lag).
    """
    y = np.asarray(series, dtype=float).ravel()
    n = len(y)
    dy = np.diff(y)
    ylag = y[:-1]
    m = len(dy)

    if max_lag is None:
        # Schwert rule of thumb, capped so regression stays well-determined
        max_lag = int(np.ceil(12.0 * (n / 100.0) ** 0.25))
    max_lag = int(min(max_lag, (m // 2) - 3))
    max_lag = max(max_lag, 0)

    common_start = max_lag  # every candidate model uses observations [max_lag:]

    def _fit(p):
        Y, X = _adf_design(y, dy, ylag, p, common_start, regression)
        beta, resid, se, ssr, dof = ols_with_se(Y, X, add_const=True)
        # Column layout after the prepended const: [const, level, lag diffs...]
        level_idx = 1
        stat = beta[level_idx] / se[level_idx] if se[level_idx] > 0 else 0.0
        nobs = len(Y)
        k = X.shape[1] + 1  # + const
        # Gaussian log-likelihood based information criteria.
        llf = -0.5 * nobs * (np.log(2 * np.pi) + np.log(ssr / nobs) + 1)
        if autolag == "BIC":
            ic = -2 * llf + k * np.log(nobs)
        else:  # AIC (default)
            ic = -2 * llf + 2 * k
        return stat, ic

    if autolag in ("AIC", "BIC"):
        best_p, best_stat, best_ic = 0, None, np.inf
        for p in range(0, max_lag + 1):
            stat, ic = _fit(p)
            if ic < best_ic:
                best_ic, best_stat, best_p = ic, stat, p
        used_lag, stat = best_p, best_stat
    else:
        used_lag = max_lag
        stat, _ = _fit(max_lag)

    pvalue = mackinnon_pvalue(stat, regression=regression)
    return float(stat), float(pvalue), int(used_lag)


def engle_granger(a, b, regression="c", pvalue_threshold=0.05):
    """Two-step Engle-Granger cointegration test for series A and B.

    1. OLS hedge ratio of A on B gives the spread (residuals).
    2. ADF test on the spread.

    The pair is flagged cointegrated when the spread's ADF p-value falls below
    ``pvalue_threshold``. Returns a JSON-serialisable dict.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    beta, alpha, spread = hedge_ratio(a, b)
    stat, pvalue, used_lag = adf(spread, regression=regression)
    return {
        "beta": float(beta),
        "alpha": float(alpha),
        "spread": spread.tolist(),
        "adf_stat": float(stat),
        "adf_pvalue": float(pvalue),
        "adf_lag": int(used_lag),
        "cointegrated": bool(pvalue < pvalue_threshold),
    }


def rolling_zscore(series, window):
    """Rolling z-score: (x - rolling_mean) / rolling_std.

    Uses only trailing data (inclusive of the current point). 
    Leading ``window-1`` entries are NaN.
    """
    x = np.asarray(series, dtype=float).ravel()
    n = len(x)
    out = np.full(n, np.nan)
    if window < 2 or n < window:
        return out
    # Skip any leading NaN region (e.g. a spread that warms up after a hedge-ratio
    # window) so the cumulative sums are not poisoned. Interior NaNs are not
    # expected for the series this is used on.
    finite = np.where(np.isfinite(x))[0]
    if len(finite) == 0:
        return out
    f = finite[0]
    xv = x[f:]
    m = len(xv)
    if m < window:
        return out
    # Cumulative sums for an O(n) trailing mean/std
    csum = np.concatenate([[0.0], np.cumsum(xv)])
    csum2 = np.concatenate([[0.0], np.cumsum(xv * xv)])
    for i in range(window - 1, m):
        s = csum[i + 1] - csum[i + 1 - window]
        s2 = csum2[i + 1] - csum2[i + 1 - window]
        mean = s / window
        var = max(s2 / window - mean * mean, 0.0)
        std = math.sqrt(var)
        out[f + i] = (xv[i] - mean) / std if std > 0 else 0.0
    return out
