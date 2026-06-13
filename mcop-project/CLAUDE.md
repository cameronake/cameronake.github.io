# mcop-project — CLAUDE.md

Monte Carlo Options Pricing implementation for the portfolio demo at `mcop-demo.html`.

---

## Architecture

No Pyodide — everything is pure vanilla JS arithmetic. The worker starts instantly (no 3–5s load delay). This is the key UX difference from `bo-demo.html`.

```
mcop-demo.html          — self-contained demo page, embedded styles
mcop-worker.js          — Web Worker; importScripts('./mcop-project/mcop.js')
mcop-project/mcop.js    — core math; no DOM dependencies
```

---

## Math

### Black-Scholes (European, no dividends)
```
d1 = [ln(S/K) + (r + σ²/2)·T] / (σ·√T)
d2 = d1 − σ·√T

Call: C = S·N(d1) − K·e^(−rT)·N(d2)
Put:  P = K·e^(−rT)·N(−d2) − S·N(−d1)
```

Normal CDF `N(·)`: Abramowitz & Stegun rational approximation (algo 26.2.17), ±7.5e-8 accuracy.

Put-call parity (invariant): `C − P = S − K·e^(−rT)` — used as a correctness assertion.

### Monte Carlo (single-step GBM, exact for European)
```
S_T = S · exp((r − σ²/2)T + σ·√T·Z),   Z ~ N(0,1)
Payoff = max(S_T − K, 0)   [call]   or   max(K − S_T, 0)   [put]
Price  = e^(−rT) · mean(payoffs)
SE     = e^(−rT) · std(payoffs) / √N
```

Box-Muller: `Z = √(−2·ln U₁)·cos(2π·U₂)`, avoids `log(0)` with `U₁ = 1 − Math.random()`.

### GBM paths (Paths tab visualization only)
Multi-step discretization: `S_{t+dt} = S_t · exp((r−σ²/2)dt + σ√dt·Z_t)`.
Only first `min(50, N)` paths are stored, each with 51 time steps.

### Convergence checkpoints
~30 log-spaced indices from 1 to N: `n_k = round(N^(k/29))` for k=0…29.
Avoids storing O(N) intermediate values while giving a smooth convergence curve.

---

## Sanity checks (run in browser console)

```js
// Normal CDF
normal_cdf(0)     // → 0.5
normal_cdf(1.96)  // → ~0.975
normal_cdf(-1.645) // → ~0.05

// ATM call (canonical check)
bs_price(100, 100, 1, 0.20, 0.05, 'call').price  // → ~10.45

// Put-call parity (should be ~0)
bs_price(100,100,1,0.20,0.05,'call').price
  - bs_price(100,100,1,0.20,0.05,'put').price
  - (100 - 100 * Math.exp(-0.05))  // → ~0 to machine precision
```

---

## Default parameters

S=100, K=100, T=1.0, σ=0.20, r=0.05, N=10000, type=call.
This is the standard ATM (at-the-money) call test case used in all textbooks.

---

## Design decisions

- **Float64Array for payoffs**: ~2–3× faster than plain Array for large N; avoids GC pressure.
- **Running SE approximation**: `SE_k ≈ final_SE · √(N/n_k)` — avoids recomputing variance at each checkpoint; accurate enough for visualization.
- **Single-step for pricing, multi-step for visualization**: the single-step GBM formula is the exact terminal distribution; multi-step paths are only needed for the Paths tab spaghetti chart.
- **Auto-run debounced at 300ms**: 10k paths runs in ~50ms in modern browsers; no need for an explicit Run button.
