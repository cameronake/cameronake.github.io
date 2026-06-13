# Bayesian Optimization Project — Implementation Notes

See the root `CLAUDE.md` for portfolio-wide context.

---

## Project Overview

An interactive in-browser demo of Bayesian Optimization (BO) implemented from scratch. The user watches BO sequentially propose sample points to find the optimum of a black-box function, guided by a Gaussian Process surrogate and an acquisition function.

**What makes this impressive:**
- GP regression implemented from scratch in Python/NumPy (posterior math, kernel, Cholesky solve)
- Acquisition function logic from scratch
- Clear, beautiful visualization of the algorithm's reasoning at each step

Demo page: `bo-demo.html` (portfolio root) — **created**

---

## Mathematical Components

### Gaussian Process Regression

A GP defines a prior over functions. Given observations `(X, y)` (sampled x-locations and noisy function values), the GP posterior gives a mean and variance estimate at any new point `x*`.

**RBF (Squared Exponential) kernel:**
```
k(x, x') = σ²_f · exp(−‖x − x'‖² / (2 l²))
```
- `l` — length scale: how quickly correlation falls off with distance
- `σ²_f` — signal variance: overall scale of the function

**Posterior equations:**
```
K     = kernel(X, X) + σ²_n · I    # n×n, covariance of training points + noise
k*    = kernel(X, x*)               # n×1, covariance between training points and x*
k**   = kernel(x*, x*)              # scalar, prior variance at x*

μ(x*) = k*ᵀ K⁻¹ y                  # posterior mean
σ²(x*) = k** − k*ᵀ K⁻¹ k*          # posterior variance
```
- `σ²_n` — noise variance: assumed observation noise

**Numerical implementation:** never invert K directly. Use Cholesky decomposition:
```python
L = np.linalg.cholesky(K)          # K = L Lᵀ
alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))   # K⁻¹ y
mu    = k_star.T @ alpha
v     = np.linalg.solve(L, k_star)
sigma2 = k_starstar - v.T @ v
```

### Acquisition Functions

Acquisition functions trade off **exploitation** (sample where the mean is high) and **exploration** (sample where uncertainty is high).

**Upper Confidence Bound (UCB):**
```
a(x) = μ(x) + κ · σ(x)
```
- `κ` — exploration parameter; higher → more exploration. Typical range: 1–5.

**Expected Improvement (EI):**
```
Z    = (μ(x) − f(x⁺) − ξ) / σ(x)
a(x) = (μ(x) − f(x⁺) − ξ) · Φ(Z) + σ(x) · φ(Z)
```
- `f(x⁺)` — best observed value so far
- `ξ` — jitter / exploration bonus (typically 0.01)
- `Φ`, `φ` — standard normal CDF and PDF, implemented from scratch using `math.erfc` (no scipy)
- Set `a(x) = 0` when `σ(x) = 0`

### Optimization of the Acquisition Function

For 1D: evaluate `a(x)` on a 500-point grid and take the argmax. Exact enough for the demo.

---

## Demo Page Structure

### Visual layout (1D optimization)

One 1D function at a time — clearest way to visualize GP uncertainty. True function is shown by default (toggle available).

**Main chart (Chart.js):**
- True function curve (shown/hidden via checkbox)
- GP posterior mean line
- GP posterior uncertainty band (mean ± 2σ, 95% credible interval)
- Scatter points for all collected samples
- Marker (crosshair) at the next proposed point

**Acquisition chart (Chart.js, below main chart):**
- Acquisition function curve across the domain
- Filled area under curve

**Controls:**
- Target function selector (sine, bumpy, multimodal, easy)
- Seed samples slider (1–8 initial random points)
- Kernel length scale `l` and signal variance `σ²_f` (sliders)
- Noise variance `σ²_n` (slider)
- Acquisition function toggle: UCB / EI (pill buttons)
- `κ` slider for UCB, `ξ` slider for EI (conditionally shown)
- "seed random" button — place N random initial samples
- "next step" button — run one BO iteration
- "run 10 steps" button — auto-advance
- "reset" button

**Stats strip:** samples count, best y, best x, next proposal x, step counter.

**Tabs:** "live demo" and "how it works" (explainer with math).

### Target functions (pre-defined, 1D, domain [0, 1])

All defined in both JS (`bo-demo.html`) and Python (`bo.py`). Noise is added on evaluation in JS via Box-Muller.

- `sine`: `sin(6πx)`
- `bumpy`: `sin(6πx) + 0.5·sin(14πx)`
- `multimodal`: three Gaussian bumps at x = 0.2, 0.55, 0.85 with heights 1.0, 0.8, 1.2
- `easy`: single Gaussian peak centered at 0.6, width 0.2

---

## Technical Approach

**Python (NumPy) in Pyodide**, consistent with the TTR demo. No scipy — `Φ` and `φ` implemented from `math.erfc`.

**Worker message types:**
- `init` → `ready` / `error`: load Pyodide + NumPy, fetch and write `bo.py` to Pyodide VFS, import `bo`
- `bo_step` → `bo_result` / `bo_error`: given samples (X_train, y_train), hyperparameters, and X_grid, return `{mu, sigma, acq, next_x}`

**JS side:**
- Maintains `samples = [{x, y}]`
- On each BO step: samples the proposed `next_x` (evaluates true function + noise in JS), appends to `samples`, sends updated samples + hyperparams to worker, receives GP posterior grid + next proposal, re-renders charts

---

## File Structure

```
Portfolio/
├── bo-demo.html            # Demo page (created)
├── bo-worker.js            # Pyodide Web Worker (created)
└── bo-project/
    ├── CLAUDE.md           # This file
    └── bo.py               # Python GP + acquisition module (created)
```

### bo.py — function inventory

| Function | Purpose |
|----------|---------|
| `rbf_kernel(X1, X2, length_scale, signal_var)` | (n,m) RBF kernel matrix |
| `gp_posterior(X_train, y_train, X_test, length_scale, signal_var, noise_var)` | Cholesky-based posterior mean + std, returns `(mu, sigma)` |
| `acquisition_ucb(mu, sigma, kappa)` | UCB acquisition values |
| `acquisition_ei(mu, sigma, y_best, xi)` | EI acquisition values (no scipy) |
| `maximize_acquisition(X_grid, mu, sigma, acq_type, kappa, xi, y_best)` | Grid argmax, returns `(next_x, acq_values)` |
| `target_sine/bumpy/multimodal/easy(x)` | Four target functions |
| `bo_step(X_train, y_train, X_grid, ...)` | Full BO iteration, returns `{mu, sigma, acq, next_x}` |

---

## Resolved Design Decisions

- **True function shown by default** — more instructive for a demo; toggle available
- **Initial seed count** — slider from 1–8, default 3; user controls before BO starts
- **Both UCB and EI implemented** at launch, toggled via pill buttons
- **2D demo** — not planned; stretch goal only
- **Kernel hyperparameter optimization** — not implemented; user-controlled sliders only
