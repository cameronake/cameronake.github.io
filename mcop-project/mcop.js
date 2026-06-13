// mcop.js — Monte Carlo Options Pricing core math
// Runs in a Web Worker via importScripts. No DOM, no external deps.

// Abramowitz & Stegun rational approximation for Φ(x), accurate to ±7.5e-8
function normal_cdf(x) {
  const t = 1.0 / (1.0 + 0.2316419 * Math.abs(x));
  const poly = t * (0.319381530
             + t * (-0.356563782
             + t * (1.781477937
             + t * (-1.821255978
             + t *  1.330274429))));
  const pdf_x = Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
  const cdf = 1.0 - pdf_x * poly;
  return x >= 0 ? cdf : 1.0 - cdf;
}

// Box-Muller transform: returns one standard normal sample
function box_muller() {
  const u = 1 - Math.random(); // avoid log(0)
  const v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

// Black-Scholes price for a European call or put
// Returns {price, d1, d2} — d1/d2 exposed for the explainer tab
function bs_price(S, K, T, sigma, r, type) {
  if (T <= 0 || sigma <= 0) {
    const intrinsic = type === 'call' ? Math.max(S - K, 0) : Math.max(K - S, 0);
    return { price: intrinsic, d1: 0, d2: 0 };
  }
  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;
  let price;
  if (type === 'call') {
    price = S * normal_cdf(d1) - K * Math.exp(-r * T) * normal_cdf(d2);
  } else {
    price = K * Math.exp(-r * T) * normal_cdf(-d2) - S * normal_cdf(-d1);
  }
  return { price, d1, d2 };
}

// Build ~30 log-spaced checkpoint indices from 1 to N (inclusive)
function logCheckpoints(N, count) {
  const pts = new Set();
  for (let k = 0; k < count; k++) {
    const n = Math.round(Math.pow(N, k / (count - 1)));
    if (n >= 1) pts.add(n);
  }
  pts.add(N);
  return Array.from(pts).sort((a, b) => a - b);
}

// Monte Carlo simulation for a European option
// Returns {mc_price, std_error, terminal_prices, running_means, paths}
function mc_simulate(S, K, T, sigma, r, N, type) {
  const discount = Math.exp(-r * T);
  const drift    = (r - 0.5 * sigma * sigma) * T;
  const vol      = sigma * Math.sqrt(T);

  const payoffs         = new Float64Array(N);
  const terminal_prices = new Float64Array(N);
  const checkpoints     = new Set(logCheckpoints(N, 30));
  const running_means   = [];

  // Store multi-step paths for first STORE_PATHS simulations (Paths tab)
  const STORE_PATHS = Math.min(50, N);
  const TIME_STEPS  = 50;
  const dt          = T / TIME_STEPS;
  const paths       = [];
  for (let i = 0; i < STORE_PATHS; i++) {
    paths.push(new Float32Array(TIME_STEPS + 1));
  }

  let payoffSum = 0;

  for (let i = 0; i < N; i++) {
    // Single-step GBM — exact terminal price
    const Z   = box_muller();
    const S_T = S * Math.exp(drift + vol * Z);
    const payoff = type === 'call' ? Math.max(S_T - K, 0) : Math.max(K - S_T, 0);
    payoffs[i]         = payoff;
    terminal_prices[i] = S_T;
    payoffSum += payoff;

    if (checkpoints.has(i + 1)) {
      running_means.push({ n: i + 1, price: discount * payoffSum / (i + 1) });
    }

    // Multi-step path for the Paths tab visualization
    if (i < STORE_PATHS) {
      paths[i][0] = S;
      for (let t = 1; t <= TIME_STEPS; t++) {
        const Zt = box_muller();
        paths[i][t] = paths[i][t - 1] * Math.exp(
          (r - 0.5 * sigma * sigma) * dt + sigma * Math.sqrt(dt) * Zt
        );
      }
    }
  }

  const mc_price = discount * payoffSum / N;

  // Sample variance of discounted payoffs
  let sumSq = 0;
  for (let i = 0; i < N; i++) {
    const dp = discount * payoffs[i] - mc_price;
    sumSq += dp * dp;
  }
  const std_error = Math.sqrt(sumSq / (N * (N - 1)));

  // Running SE estimates at each checkpoint (for convergence band)
  // Approximate: SE_k ≈ final_std_error * sqrt(N / n_k)
  const running_se = running_means.map(({ n, price }) => ({
    n,
    price,
    se: std_error * Math.sqrt(N / n)
  }));

  return {
    mc_price,
    std_error,
    terminal_prices: Array.from(terminal_prices),
    running_means: running_se,
    paths: paths.map(p => Array.from(p)),
    dt,
    TIME_STEPS
  };
}

// Entry point called by mcop-worker.js
function runSimulation({ S, K, T, sigma, r, N, type }) {
  const bs = bs_price(S, K, T, sigma, r, type);
  const mc = mc_simulate(S, K, T, sigma, r, N, type);
  return {
    bs_price:        bs.price,
    bs_d1:           bs.d1,
    bs_d2:           bs.d2,
    mc_price:        mc.mc_price,
    std_error:       mc.std_error,
    terminal_prices: mc.terminal_prices,
    running_means:   mc.running_means,
    paths:           mc.paths,
    dt:              mc.dt,
    TIME_STEPS:      mc.TIME_STEPS,
    N,
    params: { S, K, T, sigma, r, type }
  };
}
