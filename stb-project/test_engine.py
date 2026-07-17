import numpy as np

import stats
import backtester as bt


def make_panel(n=600, seed=0):
    """Synthetic DATA_PRICES-shaped panel: trender, mean-reverter, and
    cointegrated pair (PEPSI/COLA)."""
    rng = np.random.default_rng(seed)
    dates = [f"D{idx:04d}" for idx in range(n)]

    def ohlcv(close):
        close = np.asarray(close, dtype=float)
        openp = np.concatenate([[close[0]], close[:-1]])  # open = prev close
        high = np.maximum(openp, close) * 1.005
        low = np.minimum(openp, close) * 0.995
        vol = np.full(n, 1e6)
        return dict(open=openp.tolist(), high=high.tolist(), low=low.tolist(),
                    close=close.tolist(), adj_close=close.tolist(),
                    volume=vol.tolist())

    trend = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))  # drifts up
    revert = 100 + np.cumsum(rng.normal(0, 1, n))  # random walk
    common = np.cumsum(rng.normal(0, 1, n))
    cola = 50 + common + rng.normal(0, 0.5, n)
    pepsi = 30 + 0.8 * common + rng.normal(0, 0.5, n)  # coint w/ cola

    data = {"TREND": ohlcv(trend), "REV": ohlcv(revert),
            "COLA": ohlcv(cola), "PEPSI": ohlcv(pepsi)}
    return {"dates": dates, "tickers": list(data), "data": data,
            "pairs": [["COLA", "PEPSI"]]}


def run(name, params, panel, universe=None):
    data = bt.DataHandler.from_panel(panel)
    strat = bt.build_strategy(name, params, universe)
    pf = bt.Portfolio(initial_cash=100_000.0)
    broker = bt.Broker(commission_bps=1.0, spread_bps=2.0, slippage=True)
    res = bt.run_backtest(data, strat, pf, broker)
    m = bt.compute_metrics(res["equity"], pf)
    return res, m, data


def test_cointegration():
    panel = make_panel()
    A = np.array(panel["data"]["COLA"]["close"])
    B = np.array(panel["data"]["PEPSI"]["close"])
    eg = stats.engle_granger(A, B)
    assert eg["cointegrated"], f"expected cointegration, p={eg['adf_pvalue']:.3f}"
    # Two independent random walks shouldn't be cointegrated
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.normal(0, 1, 600))
    y = np.cumsum(rng.normal(0, 1, 600))
    assert not stats.engle_granger(x, y)["cointegrated"]
    print(f"[ok] cointegration: COLA/PEPSI p={eg['adf_pvalue']:.4f} beta={eg['beta']:.3f}")


def test_metrics_buy_and_hold():
    panel = make_panel()
    data = bt.DataHandler.from_panel(panel)
    eq = bt.buy_and_hold_equity(data, "TREND", 100_000.0)
    m = bt.compute_metrics(eq)
    # Drawdown must be non-positive
    # CAGR must be positive for a drifting up asset
    assert m["max_drawdown"] <= 0
    assert np.isfinite(m["sharpe"])
    assert m["cagr"] > 0
    print(f"[ok] buy&hold TREND: CAGR={m['cagr']:.2%} Sharpe={m['sharpe']:.2f} "
          f"MDD={m['max_drawdown']:.2%}")


def test_no_lookahead():
    """Results over the first T bars must not depend on data that arrives after bar T. 
    """
    panel = make_panel()
    full = bt.DataHandler.from_panel(panel)
    T = 400

    sub_panel = {"dates": panel["dates"][:T], "tickers": panel["tickers"],
                 "pairs": panel["pairs"],
                 "data": {tk: {k: v[:T] for k, v in d.items()}
                          for tk, d in panel["data"].items()}}
    sub = bt.DataHandler.from_panel(sub_panel)

    for name, params, uni in [
        ("momentum", {"lookback": 60, "top_n": 1, "rebalance": 10},
         ["TREND", "REV", "COLA", "PEPSI"]),
        ("mean_reversion", {"ticker": "REV", "lookback": 20, "z_entry": 1.0,
                            "z_exit": 0.25}, None),
        ("pairs", {"pair": ("COLA", "PEPSI"), "lookback": 60, "z_entry": 2.0,
                   "z_exit": 0.5, "recompute": 5}, None),
    ]:
        ef = bt.run_backtest(full, bt.build_strategy(name, params, uni),
                             bt.Portfolio(), bt.Broker())["equity"]
        es = bt.run_backtest(sub, bt.build_strategy(name, params, uni),
                             bt.Portfolio(), bt.Broker())["equity"]
        diff = np.max(np.abs(ef[:T] - es[:T]))
        assert diff < 1e-6, f"{name}: lookahead leak, max equity diff={diff:.6g}"
        print(f"[ok] no-lookahead {name}: max abs equity diff over first {T} bars = {diff:.2e}")


def test_costs_reduce_performance():
    panel = make_panel()
    data = bt.DataHandler.from_panel(panel)
    params = {"ticker": "REV", "lookback": 15, "z_entry": 0.75, "z_exit": 0.1}

    gross = bt.run_backtest(data, bt.build_strategy("mean_reversion", params),
                            bt.Portfolio(), bt.Broker(0, 0, slippage=False))["equity"]
    net = bt.run_backtest(data, bt.build_strategy("mean_reversion", params),
                          bt.Portfolio(), bt.Broker(1.0, 3.0, slippage=True))["equity"]
    assert net[-1] < gross[-1], "costs should reduce terminal equity"
    drag = bt.cagr(gross) - bt.cagr(net)
    print(f"[ok] cost drag (mean-reversion, high turnover): "
          f"gross CAGR={bt.cagr(gross):.2%} net={bt.cagr(net):.2%} drag={drag:.2%}")


if __name__ == "__main__":
    test_cointegration()
    test_metrics_buy_and_hold()
    test_no_lookahead()
    test_costs_reduce_performance()
    print("\nAll tests passed.")
