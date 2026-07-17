from dataclasses import dataclass, field
import numpy as np

import stats


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
@dataclass
class SignalEvent:
    ticker: str
    target_weight: float        # signed fraction of equity desired in this name
    i: int


@dataclass
class OrderEvent:
    ticker: str
    quantity: float             # signed shares (+ buy, - sell), filled at i+1 open
    i: int                      # bar the order was generated on


@dataclass
class FillEvent:
    ticker: str
    quantity: float
    price: float                # actual fill price incl. spread/slippage
    commission: float
    slippage_cost: float
    i: int                      # bar the fill executed on (i+1 relative to signal)


@dataclass
class Trade:
    """A realised round-trip leg (position reduced or closed)."""
    ticker: str
    entry_i: int
    exit_i: int
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float


# --------------------------------------------------------------------------- #
# Data handler
# --------------------------------------------------------------------------- #
class DataHandler:
    """Owns the aligned, split/dividend-adjusted price panel.
    """

    def __init__(self, dates, tickers, opens, highs, lows, closes, volumes):
        self.dates = list(dates)
        self.tickers = list(tickers)
        self.n = len(dates)
        self.open = opens        # dict ticker -> np.ndarray (adjusted)
        self.high = highs
        self.low = lows
        self.close = closes      # adjusted close
        self.volume = volumes

    @classmethod
    def from_panel(cls, panel, tickers=None, start=None, end=None):
        """Build from a ``DATA_PRICES``-shaped dict (JS object via toPy, or test).

        ``panel`` = {dates, tickers, data:{TICKER:{open,high,low,close,adj_close,
        volume}}}. ``start``/``end`` can optionally clip the date range (inclusive).
        """
        all_dates = list(panel["dates"])
        lo, hi = 0, len(all_dates)
        if start is not None:
            lo = next((k for k, d in enumerate(all_dates) if d >= start), len(all_dates))
        if end is not None:
            hi = next((k for k, d in enumerate(all_dates) if d > end), len(all_dates))
        dates = all_dates[lo:hi]

        if tickers is None:
            tickers = list(panel["tickers"])
        data = panel["data"]
        opens, highs, lows, closes, volumes = {}, {}, {}, {}, {}
        for tk in tickers:
            d = data[tk]
            close = np.asarray(d["close"], dtype=float)[lo:hi]
            adj = np.asarray(d["adj_close"], dtype=float)[lo:hi]
            factor = np.divide(adj, close, out=np.ones_like(close),
                               where=close > 0)
            opens[tk] = np.asarray(d["open"], dtype=float)[lo:hi] * factor
            highs[tk] = np.asarray(d["high"], dtype=float)[lo:hi] * factor
            lows[tk] = np.asarray(d["low"], dtype=float)[lo:hi] * factor
            closes[tk] = adj
            volumes[tk] = np.asarray(d["volume"], dtype=float)[lo:hi]
        return cls(dates, tickers, opens, highs, lows, closes, volumes)

    def history(self, ticker, upto, lookback):
        """Adjusted-close window ending at (and including) bar ``upto``."""
        start = max(0, upto - lookback + 1)
        return self.close[ticker][start:upto + 1]

    def __len__(self):
        return self.n


# --------------------------------------------------------------------------- #
# Broker / execution
# --------------------------------------------------------------------------- #
class Broker:
    """Executes orders at the next bar's open with costs.

    Costs: a commission in basis points of notional, half the bid-ask spread paid
    adversely on every trade.
     
    I started writing functionality for an optional square-root market-impact term
    ``impact_bps * sqrt(order_notional / ADV)`` but ended up deciding it would be
    a bit overwhelming to include for now, so I didn't add it to the frontend. 
    I might include it later, though.
    """

    def __init__(self, commission_bps=1.0, spread_bps=2.0,
                 slippage=True, impact_bps=0.0, adv_lookback=20):
        self.commission_bps = commission_bps
        self.spread_bps = spread_bps if slippage else 0.0
        self.impact_bps = impact_bps if slippage else 0.0
        self.adv_lookback = adv_lookback

    def execute(self, order, data, exec_i):
        """Fill ``order`` at bar ``exec_i`` (= signal bar + 1) open. Returns FillEvent."""
        tk = order.ticker
        ref = data.open[tk][exec_i]
        side = 1.0 if order.quantity > 0 else -1.0
        notional = abs(order.quantity) * ref

        # Adverse half-spread
        slip_bps = self.spread_bps / 2.0
        # Optional sqrt market impact relative to average dollar volume
        if self.impact_bps > 0:
            lo = max(0, exec_i - self.adv_lookback)
            adv = np.mean(data.volume[tk][lo:exec_i + 1]) * ref
            if adv > 0:
                slip_bps += self.impact_bps * np.sqrt(notional / adv)

        fill_price = ref * (1.0 + side * slip_bps / 1e4)
        slippage_cost = abs(order.quantity) * abs(fill_price - ref)
        commission = notional * self.commission_bps / 1e4
        return FillEvent(tk, order.quantity, fill_price, commission,
                         slippage_cost, exec_i)


# --------------------------------------------------------------------------- #
# Portfolio (cash, positions, cost-basis PnL, turnover)
# --------------------------------------------------------------------------- #
class Portfolio:
    def __init__(self, initial_cash=100_000.0, rebalance_eps=1e-9):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}  # ticker -> shares
        self.avg_price = {}  # ticker -> average entry price (signed cost basis)
        self.entry_i = {}  # ticker -> bar position was opened
        self.target_weights = {}  # last applied target weight per ticker
        self.rebalance_eps = rebalance_eps
        self.trades = []  # realised round-trip legs
        self.fills = []  # all fills (for trade markers)
        self.traded_notional = 0.0  # cumulative |notional| traded (for turnover)
        self.total_costs = 0.0

    # -- valuation --------------------------------------------------------- #
    def equity(self, data, i):
        val = self.cash
        for tk, sh in self.positions.items():
            if sh != 0.0:
                val += sh * data.close[tk][i]
        return val

    # -- order generation -------------------------------------------------- #
    def compute_orders(self, targets, data, i, equity_i):
        """Diff desired target weights against the last applied targets.

        Only names whose target weight changed produce orders, so turnover is
        driven by signal changes (entries/exits/rebalances), not by daily drift.
        Sizing uses current equity and the bar-i close as the reference price.
        """
        orders = []
        names = set(targets) | set(self.target_weights)
        for tk in names:
            nt = targets.get(tk, 0.0)
            ot = self.target_weights.get(tk, 0.0)
            if abs(nt - ot) <= self.rebalance_eps:
                continue
            px = data.close[tk][i]
            desired_shares = nt * equity_i / px if px > 0 else 0.0
            qty = desired_shares - self.positions.get(tk, 0.0)
            self.target_weights[tk] = nt
            if abs(qty) * px > 1e-6:
                orders.append(OrderEvent(tk, qty, i))
        return orders

    # -- fill application + realised-PnL accounting ------------------------ #
    def apply_fill(self, fill):
        tk = fill.ticker
        qty = fill.quantity
        price = fill.price
        self.cash -= qty * price + fill.commission
        self.total_costs += fill.commission + fill.slippage_cost
        self.traded_notional += abs(qty) * price
        self.fills.append(fill)

        cur = self.positions.get(tk, 0.0)
        avg = self.avg_price.get(tk, 0.0)
        new = cur + qty

        if cur == 0.0 or (cur > 0) == (qty > 0):
            # Opening or adding in the same direction -> blend the cost basis.
            if cur == 0.0:
                self.entry_i[tk] = fill.i
            self.avg_price[tk] = (avg * cur + price * qty) / new if new != 0 else 0.0
        else:
            # Reducing, closing, or flipping -> realise PnL on the closed portion.
            closed = min(abs(qty), abs(cur)) * (1.0 if cur > 0 else -1.0)
            pnl = (price - avg) * closed
            self.trades.append(Trade(tk, self.entry_i.get(tk, fill.i), fill.i,
                                     closed, avg, price, pnl))
            if (cur > 0) != (new > 0) and new != 0.0:
                # Position flipped through zero: remainder opens at fill price.
                self.avg_price[tk] = price
                self.entry_i[tk] = fill.i
            elif new == 0.0:
                self.avg_price[tk] = 0.0
        self.positions[tk] = new


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
class Strategy:
    """Base class. Subclasses precompute causal target weights in ``prepare``."""

    def warmup(self):
        raise NotImplementedError

    def prepare(self, data):
        """Vectorised, causal precompute. Populates self._targets (list per bar)."""
        raise NotImplementedError

    def targets(self, i):
        return self._targets[i]

    # Optional diagnostic series for the demo (spread, z-score, ...).
    extra_series = None


class MomentumStrategy(Strategy):
    """Cross-sectional momentum: long the top-N trailing performers, equal weight.

    Params: lookback, top_n, rebalance (bars between rebalances), long_short.
    """

    def __init__(self, params, universe):
        self.lookback = int(params.get("lookback", 126))
        self.top_n = int(params.get("top_n", 3))
        self.rebalance = int(params.get("rebalance", 21))
        self.long_short = bool(params.get("long_short", False))
        self.universe = list(universe)

    def warmup(self):
        return self.lookback + 1

    def prepare(self, data):
        n = len(data)
        L = self.lookback
        # Trailing return matrix (assets x bars), causal.
        mom = {tk: np.full(n, np.nan) for tk in self.universe}
        for tk in self.universe:
            c = data.close[tk]
            mom[tk][L:] = c[L:] / c[:-L] - 1.0
        targets = [dict() for _ in range(n)]
        current = {}
        w = self.warmup()
        for i in range(n):
            if i >= w and (i - w) % self.rebalance == 0:
                ranked = sorted(
                    (tk for tk in self.universe if not np.isnan(mom[tk][i])),
                    key=lambda tk: mom[tk][i], reverse=True)
                current = {}
                if ranked:
                    k = min(self.top_n, len(ranked))
                    longs = ranked[:k]
                    for tk in longs:
                        current[tk] = 1.0 / k
                    if self.long_short and len(ranked) >= 2 * k:
                        for tk in ranked[-k:]:
                            current[tk] = -1.0 / k
            targets[i] = dict(current)
        self._targets = targets


class MeanReversionStrategy(Strategy):
    """Single-asset z-score mean reversion (Bollinger style).

    Params: ticker, lookback, z_entry, z_exit. Enter long when z < -z_entry,
    short when z > z_entry, exit toward flat when |z| < z_exit.
    """

    def __init__(self, params):
        self.ticker = params["ticker"]
        self.lookback = int(params.get("lookback", 20))
        self.z_entry = float(params.get("z_entry", 1.0))
        self.z_exit = float(params.get("z_exit", 0.25))
        self.allow_short = bool(params.get("allow_short", True))

    def warmup(self):
        return self.lookback

    def prepare(self, data):
        n = len(data)
        tk = self.ticker
        z = stats.rolling_zscore(data.close[tk], self.lookback)
        targets = [dict() for _ in range(n)]
        pos = 0  # -1, 0, +1
        for i in range(n):  
            zi = z[i]
            if not np.isnan(zi):
                if pos == 0:
                    if zi < -self.z_entry:
                        pos = 1
                    elif zi > self.z_entry and self.allow_short:
                        pos = -1
                elif pos == 1 and zi >= -self.z_exit:
                    pos = 0
                elif pos == -1 and zi <= self.z_exit:
                    pos = 0
            targets[i] = {tk: float(pos)} if pos != 0 else {}
        self._targets = targets
        self.extra_series = {"zscore": _nan_to_none(z)}


class PairsStrategy(Strategy):
    """Cointegration-based pairs / stat-arb on a single pair (A, B).

    Rolling OLS hedge ratio over ``lookback`` (recomputed every ``recompute``
    bars), spread = A - beta*B, traded on the spread's rolling z-score. Optional
    ADF stationarity gate: only open when the trailing spread tests stationary.
    Dollar-neutral legs (+/-0.5 each).
    """

    def __init__(self, params):
        self.a, self.b = params["pair"]
        self.lookback = int(params.get("lookback", 60))
        self.z_entry = float(params.get("z_entry", 2.0))
        self.z_exit = float(params.get("z_exit", 0.5))
        self.recompute = int(params.get("recompute", 5))
        self.adf_gate = bool(params.get("adf_gate", False))
        self.adf_threshold = float(params.get("adf_threshold", 0.10))

    def warmup(self):
        return self.lookback + 1

    def prepare(self, data):
        n = len(data)
        A = data.close[self.a]
        B = data.close[self.b]
        L = self.lookback
        beta_series = np.full(n, np.nan)
        spread = np.full(n, np.nan)
        adf_p = np.full(n, np.nan)
        beta = np.nan
        for i in range(L, n):
            if np.isnan(beta) or (i - L) % self.recompute == 0:
                wa, wb = A[i - L + 1:i + 1], B[i - L + 1:i + 1]
                beta, alpha, resid = stats.hedge_ratio(wa, wb)
                if self.adf_gate:
                    stat, p, _ = stats.adf(resid)
                    adf_p[i] = p
            beta_series[i] = beta
            spread[i] = A[i] - beta * B[i]
        z = stats.rolling_zscore(spread, L)

        targets = [dict() for _ in range(n)]
        pos = 0  # +1 long spread (long A / short B), -1 short spread
        last_p = 1.0
        for i in range(n):
            zi = z[i]
            if not np.isnan(adf_p[i]):
                last_p = adf_p[i]
            gate_ok = (not self.adf_gate) or (last_p < self.adf_threshold)
            if not np.isnan(zi):
                if pos == 0 and gate_ok:
                    if zi < -self.z_entry:
                        pos = 1
                    elif zi > self.z_entry:
                        pos = -1
                elif pos == 1 and zi >= -self.z_exit:
                    pos = 0
                elif pos == -1 and zi <= self.z_exit:
                    pos = 0
            if pos == 1:
                targets[i] = {self.a: 0.5, self.b: -0.5}
            elif pos == -1:
                targets[i] = {self.a: -0.5, self.b: 0.5}
            else:
                targets[i] = {}
        self._targets = targets
        self.extra_series = {
            "spread": _nan_to_none(spread),
            "zscore": _nan_to_none(z),
            "beta": _nan_to_none(beta_series),
        }


def build_strategy(name, params, universe=None):
    if name == "momentum":
        return MomentumStrategy(params, universe or params.get("universe", []))
    if name == "mean_reversion":
        return MeanReversionStrategy(params)
    if name == "pairs":
        return PairsStrategy(params)
    raise ValueError(f"unknown strategy: {name}")


# --------------------------------------------------------------------------- #
# Event loop
# --------------------------------------------------------------------------- #
def run_backtest(data, strategy, portfolio, broker):
    """Run the bar-by-bar event loop. Returns per-bar arrays + trade log.

    Timing per bar i:
        1. apply fills scheduled for open[i] (from orders placed at i-1);
        2. mark equity at close[i];
        3. at close[i], strategy emits target weights -> orders for open[i+1].
    """
    n = len(data)
    strategy.prepare(data)
    warmup = strategy.warmup()
    equity = np.full(n, portfolio.initial_cash, dtype=float)
    pending = []  # orders to execute at the next bar's open

    for i in range(n):
        # 1. Execute fills queued for this bar's open.
        if pending:
            for order in pending:
                fill = broker.execute(order, data, i)
                portfolio.apply_fill(fill)
            pending = []

        # 2. Mark to market at this bar's close.
        equity[i] = portfolio.equity(data, i)

        # 3. Generate next orders (skip the last bar: no i+1 open to fill at).
        if warmup <= i < n - 1:
            targets = strategy.targets(i)
            orders = portfolio.compute_orders(targets, data, i, equity[i])
            if orders:
                pending = orders

    return {
        "equity": equity,
        "portfolio": portfolio,
        "warmup": warmup,
    }


# --------------------------------------------------------------------------- #
# Performance metrics (pure functions over an equity curve / returns)
# --------------------------------------------------------------------------- #
PPY = 252  # trading periods per year


def to_returns(equity):
    equity = np.asarray(equity, dtype=float)
    prev = equity[:-1]
    return np.divide(equity[1:] - prev, prev, out=np.zeros(len(prev)),
                     where=prev > 0)


def cagr(equity, ppy=PPY):
    equity = np.asarray(equity, dtype=float)
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    years = len(equity) / ppy
    growth = equity[-1] / equity[0]
    if growth <= 0 or years <= 0:
        return 0.0
    return growth ** (1.0 / years) - 1.0


def annual_vol(returns, ppy=PPY):
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(ppy))


def sharpe(returns, rf=0.0, ppy=PPY):
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / ppy
    sd = np.std(excess, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(excess) / sd * np.sqrt(ppy))


def sortino(returns, rf=0.0, ppy=PPY):
    returns = np.asarray(returns, dtype=float)
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / ppy
    downside = excess[excess < 0]
    if len(downside) == 0:
        return 0.0
    dd = np.sqrt(np.mean(downside ** 2))
    if dd == 0:
        return 0.0
    return float(np.mean(excess) / dd * np.sqrt(ppy))


def max_drawdown(equity):
    equity = np.asarray(equity, dtype=float)
    if len(equity) == 0:
        return 0.0, 0, 0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    trough = int(np.argmin(dd))
    peak_i = int(np.argmax(equity[:trough + 1])) if trough > 0 else 0
    return float(dd[trough]), peak_i, trough


def drawdown_series(equity):
    equity = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(equity)
    return (equity - peak) / peak


def calmar(equity, ppy=PPY):
    mdd, _, _ = max_drawdown(equity)
    if mdd == 0:
        return 0.0
    return cagr(equity, ppy) / abs(mdd)


def win_rate(trades):
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades)


def turnover(traded_notional, equity, ppy=PPY):
    equity = np.asarray(equity, dtype=float)
    mean_eq = np.mean(equity[equity > 0]) if np.any(equity > 0) else 0.0
    if mean_eq == 0 or len(equity) < 2:
        return 0.0
    years = len(equity) / ppy
    return float(traded_notional / mean_eq / years)


def compute_metrics(equity, portfolio=None, lo=0, hi=None):
    """Bundle all metrics over the slice [lo:hi] of an equity curve."""
    equity = np.asarray(equity, dtype=float)
    hi = len(equity) if hi is None else hi
    eq = equity[lo:hi]
    rets = to_returns(eq)
    mdd, peak_i, trough_i = max_drawdown(eq)
    m = {
        "cagr": cagr(eq),
        "vol": annual_vol(rets),
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
        "max_drawdown": mdd,
        "calmar": calmar(eq),
        "total_return": float(eq[-1] / eq[0] - 1.0) if len(eq) > 1 and eq[0] > 0 else 0.0,
    }
    if portfolio is not None:
        m["win_rate"] = win_rate(portfolio.trades)
        m["turnover"] = turnover(portfolio.traded_notional, eq)
        m["n_trades"] = len(portfolio.trades)
        m["total_costs"] = portfolio.total_costs
    return m


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _nan_to_none(arr):
    return [None if (x is None or np.isnan(x)) else float(x) for x in arr]


def buy_and_hold_equity(data, ticker, initial_cash):
    """Benchmark: buy ``ticker`` at bar 0 close, hold. Returns per-bar equity."""
    c = data.close[ticker]
    shares = initial_cash / c[0] if c[0] > 0 else 0.0
    return shares * c


# --------------------------------------------------------------------------- #
# Worker-facing orchestration (spec dicts in, JSON-friendly dicts out).
#
# The price panel is converted from JS once and held module-global so repeated
# runs (sweeps, walk-forward) never re-ship or re-parse it. DataHandler is
# read-only, so a single instance is reused across every parameter combination.
# --------------------------------------------------------------------------- #
_PANEL = None


def set_panel(panel):
    """Store the raw DATA_PRICES dict (called once by the worker at init)."""
    global _PANEL
    _PANEL = panel


def _broker_from_costs(costs):
    costs = costs or {}
    return Broker(
        commission_bps=float(costs.get("commission_bps", 1.0)),
        spread_bps=float(costs.get("spread_bps", 2.0)),
        slippage=bool(costs.get("slippage", True)),
        impact_bps=float(costs.get("impact_bps", 0.0)),
    )


def _default_universe(panel, spec):
    uni = spec.get("universe")
    if uni:
        return list(uni)
    bench = spec.get("benchmark", "SPY")
    return [tk for tk in panel["tickers"] if tk != bench]


def _run(data, name, params, universe, broker, initial_cash):
    strat = build_strategy(name, params, universe)
    pf = Portfolio(initial_cash=initial_cash)
    res = run_backtest(data, strat, pf, broker)
    return res["equity"], pf, strat


def _round(arr, nd):
    return [round(float(x), nd) for x in arr]


def backtest_from_spec(spec):
    """Single backtest. spec = {strategy, params, universe?, benchmark?, costs?,
    initial_cash?, dateRange?, compare_no_costs?}."""
    panel = _PANEL
    dr = spec.get("dateRange") or {}
    data = DataHandler.from_panel(panel, start=dr.get("start"), end=dr.get("end"))
    name = spec["strategy"]
    params = dict(spec.get("params", {}))
    universe = _default_universe(panel, spec)
    initial_cash = float(spec.get("initial_cash", 100_000.0))
    bench = spec.get("benchmark", "SPY")

    broker = _broker_from_costs(spec.get("costs"))
    equity, pf, strat = _run(data, name, params, universe, broker, initial_cash)
    metrics = compute_metrics(equity, pf)

    bench_eq = buy_and_hold_equity(data, bench, initial_cash)
    out = {
        "dates": data.dates,
        "equity": _round(equity, 2),
        "benchmark": _round(bench_eq, 2),
        "benchmark_ticker": bench,
        "drawdown": _round(drawdown_series(equity), 5),
        "metrics": _jsonify(metrics),
        "benchmark_metrics": _jsonify(compute_metrics(bench_eq)),
        "trades": [
            {"i": f.i, "date": data.dates[f.i], "ticker": f.ticker,
             "side": "buy" if f.quantity > 0 else "sell",
             "qty": round(float(f.quantity), 2), "price": round(float(f.price), 4)}
            for f in pf.fills
        ],
        "extra": strat.extra_series,
    }

    if spec.get("compare_no_costs"):
        free = _broker_from_costs({"commission_bps": 0, "spread_bps": 0,
                                   "slippage": False})
        eq_free, _, _ = _run(data, name, params, universe, free, initial_cash)
        out["no_cost_equity"] = _round(eq_free, 2)
        out["cost_drag"] = round(cagr(eq_free) - cagr(equity), 4)
    return out


def _fold_windows(n, n_folds, train_frac, anchored):
    """Yield (train_lo, train_hi, test_lo, test_hi) for each walk-forward fold."""
    seg = n // (n_folds + 1)
    windows = []
    for k in range(1, n_folds + 1):
        test_lo = k * seg
        test_hi = n if k == n_folds else (k + 1) * seg
        if anchored:
            train_lo = 0
        else:
            train_len = max(seg, int(train_frac / max(1e-9, 1 - train_frac) * seg))
            train_lo = max(0, test_lo - train_len)
        windows.append((train_lo, test_lo, test_lo, test_hi))
    return windows


def _grid_combos(grid):
    """Expand {paramName: [values]} into a list of override dicts (cartesian)."""
    names = list(grid)
    combos = [{}]
    for nm in names:
        combos = [dict(c, **{nm: v}) for c in combos for v in grid[nm]]
    return combos


def walkforward_from_spec(spec, progress=None):
    """Walk-forward optimisation. spec adds {paramGrid, nFolds, trainFrac,
    anchored, metric}. Optimises the metric on each fold's in-sample window and
    reports out-of-sample performance on the held-out window."""
    panel = _PANEL
    dr = spec.get("dateRange") or {}
    data = DataHandler.from_panel(panel, start=dr.get("start"), end=dr.get("end"))
    name = spec["strategy"]
    base = dict(spec.get("params", {}))
    universe = _default_universe(panel, spec)
    initial_cash = float(spec.get("initial_cash", 100_000.0))
    broker = _broker_from_costs(spec.get("costs"))
    metric = spec.get("metric", "sharpe")
    n_folds = int(spec.get("nFolds", 4))
    train_frac = float(spec.get("trainFrac", 0.5))
    anchored = bool(spec.get("anchored", True))

    combos = _grid_combos(spec.get("paramGrid", {}))
    n = len(data)

    # Run every parameter combo once over the full series (causal)
    equities = []
    for j, ov in enumerate(combos):
        eq, _, _ = _run(data, name, dict(base, **ov), universe, broker, initial_cash)
        equities.append(eq)
        if progress:
            progress(j + 1, len(combos), "walkforward")

    windows = _fold_windows(n, n_folds, train_frac, anchored)
    folds = []
    oos_returns = []
    is_metric_vals = []
    for (tr_lo, tr_hi, te_lo, te_hi) in windows:
        best_j, best_is = 0, -np.inf
        for j in range(len(combos)):
            is_val = compute_metrics(equities[j], lo=tr_lo, hi=tr_hi).get(metric, 0.0)
            if is_val > best_is:
                best_is, best_j = is_val, j
        is_m = compute_metrics(equities[best_j], lo=tr_lo, hi=tr_hi)
        oos_m = compute_metrics(equities[best_j], lo=te_lo, hi=te_hi)
        oos_returns.append(to_returns(equities[best_j][te_lo:te_hi]))
        is_metric_vals.append(is_m.get(metric, 0.0))
        folds.append({
            "train": [data.dates[tr_lo], data.dates[tr_hi - 1]],
            "test": [data.dates[te_lo], data.dates[te_hi - 1]],
            "best_params": _jsonify(combos[best_j]),
            "is_metric": round(float(is_m.get(metric, 0.0)), 3),
            "oos_metric": round(float(oos_m.get(metric, 0.0)), 3),
        })

    # Stitch out-of-sample returns into one continuous equity curve
    stitched = [initial_cash]
    for r in oos_returns:
        for ret in r:
            stitched.append(stitched[-1] * (1 + ret))
    stitched = np.array(stitched)

    oos_dates = [data.dates[windows[0][2]]] if windows else []
    for (tr_lo, tr_hi, te_lo, te_hi) in windows:
        oos_dates.extend(data.dates[te_lo + 1:te_hi])

    return {
        "metric": metric,
        "folds": folds,
        "oos_dates": oos_dates,
        "oos_equity": _round(stitched, 2),
        "oos_metrics": _jsonify(compute_metrics(stitched)),
        "is_metric_avg": round(float(np.mean(is_metric_vals)), 3),
        "oos_metric_overall": round(float(compute_metrics(stitched).get(metric, 0.0)), 3),
    }


def sweep_from_spec(spec, progress=None):
    """2-D parameter sweep for the overfitting heatmap. spec adds
    {axisX:{name,values}, axisY:{name,values}, metric, trainFrac}. Returns the
    in-sample and out-of-sample metric grids."""
    panel = _PANEL
    dr = spec.get("dateRange") or {}
    data = DataHandler.from_panel(panel, start=dr.get("start"), end=dr.get("end"))
    name = spec["strategy"]
    base = dict(spec.get("params", {}))
    universe = _default_universe(panel, spec)
    initial_cash = float(spec.get("initial_cash", 100_000.0))
    broker = _broker_from_costs(spec.get("costs"))
    metric = spec.get("metric", "sharpe")
    ax, ay = spec["axisX"], spec["axisY"]
    xs, ys = list(ax["values"]), list(ay["values"])
    train_frac = float(spec.get("trainFrac", 0.7))

    n = len(data)
    split = int(n * train_frac)
    is_grid, oos_grid = [], []
    total = len(xs) * len(ys)
    done = 0
    best = {"is_metric": -np.inf, "x": None, "y": None}
    for yv in ys:
        is_row, oos_row = [], []
        for xv in xs:
            params = dict(base)
            params[ax["name"]] = xv
            params[ay["name"]] = yv
            eq, _, _ = _run(data, name, params, universe, broker, initial_cash)
            is_val = compute_metrics(eq, lo=0, hi=split).get(metric, 0.0)
            oos_val = compute_metrics(eq, lo=split, hi=n).get(metric, 0.0)
            is_row.append(round(float(is_val), 3))
            oos_row.append(round(float(oos_val), 3))
            if is_val > best["is_metric"]:
                best = {"is_metric": round(float(is_val), 3), "x": xv, "y": yv}
            done += 1
            if progress:
                progress(done, total, "sweep")
        is_grid.append(is_row)
        oos_grid.append(oos_row)

    return {
        "metric": metric,
        "axisX": {"name": ax["name"], "values": xs},
        "axisY": {"name": ay["name"], "values": ys},
        "is_grid": is_grid,
        "oos_grid": oos_grid,
        "best": best,
        "split_date": data.dates[split] if split < n else data.dates[-1],
    }


def cointegration_from_spec(spec):
    """Engle-Granger analysis for the pairs tab. spec = {pairA, pairB, dateRange?,
    window?}."""
    panel = _PANEL
    dr = spec.get("dateRange") or {}
    a, b = spec["pairA"], spec["pairB"]
    data = DataHandler.from_panel(panel, tickers=[a, b],
                                  start=dr.get("start"), end=dr.get("end"))
    A, B = data.close[a], data.close[b]
    eg = stats.engle_granger(A, B)
    window = int(spec.get("window", 60))
    spread = np.array(eg["spread"])
    z = stats.rolling_zscore(spread, window)
    # Normalised price series for overlay (start at 100)
    return {
        "dates": data.dates,
        "pairA": a, "pairB": b,
        "priceA": _round(A / A[0] * 100, 3),
        "priceB": _round(B / B[0] * 100, 3),
        "spread": _round(spread, 4),
        "zscore": _nan_to_none(z),
        "beta": round(eg["beta"], 4),
        "alpha": round(eg["alpha"], 4),
        "adf_stat": round(eg["adf_stat"], 4),
        "adf_pvalue": round(eg["adf_pvalue"], 4),
        "adf_lag": eg["adf_lag"],
        "cointegrated": eg["cointegrated"],
    }


def _jsonify(obj):
    """Recursively coerce numpy scalars/arrays into plain Python for json.dumps."""
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj
