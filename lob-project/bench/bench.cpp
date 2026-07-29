// OFFLINE native benchmark + replay recorder.
//
// Build first (see CMakeLists.txt), then run this from the build folder. It
// writes two committed JS data files that the browser demo reads:
//
//   ../data/lob_bench.js   -> DATA_LOB_BENCH  (latency + throughput + A/B)
//   ../data/lob_replay.js  -> DATA_LOB_REPLAY (a short recorded book trace)
//
// None of this runs in the browser. WASM is single-threaded and its timing
// wouldn't mean much, so every performance number in the demo traces back to
// a native run of this file; the live WASM build just has to work.
//
// Usage: ./lob_bench            writes into ../data relative to the cwd
//        ./lob_bench <out_dir>  or pass an explicit output directory

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#include "feed_handler.hpp"
#include "flat_hash.hpp"
#include "order_book.hpp"
#include "pool.hpp"
#include "synthetic_feed.hpp"

using namespace lob;
using Clock = std::chrono::steady_clock;

static double ns_since(Clock::time_point t0) {
    return std::chrono::duration<double, std::nano>(Clock::now() - t0).count();
}

static double percentile(std::vector<double>& v, double q) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    const std::size_t idx = static_cast<std::size_t>(q * (v.size() - 1) + 0.5);
    return v[std::min(idx, v.size() - 1)];
}

// Per-message latency, single thread.
struct LatencyResult {
    double p50 = 0, p90 = 0, p99 = 0, p999 = 0;
    std::vector<double> hist_edges;   // upper edges, ns
    std::vector<long>   hist_counts;
};

static LatencyResult measure_engine_latency(std::uint64_t seed) {
    FeedParams fp;
    fp.n = 300000;
    const auto feed = generate_feed(fp, seed);

    OrderBook book(fp.max_price, 400000);
    std::vector<Trade> trades;
    trades.reserve(fp.n);

    // Estimate timer overhead so we can subtract it from each sample.
    double overhead = 1e9;
    for (int i = 0; i < 1000; ++i) {
        auto t0 = Clock::now();
        overhead = std::min(overhead, ns_since(t0));
    }

    std::vector<double> lat;
    lat.reserve(fp.n);
    for (const FeedMsg& m : feed) {
        auto t0 = Clock::now();
        apply_msg(book, m, trades);
        double ns = ns_since(t0) - overhead;
        if (ns < 0) ns = 0;
        lat.push_back(ns);
    }

    LatencyResult r;
    r.p50  = percentile(lat, 0.50);
    r.p90  = percentile(lat, 0.90);
    r.p99  = percentile(lat, 0.99);
    r.p999 = percentile(lat, 0.999);

    const double edges[] = {25, 50, 75, 100, 150, 200, 300, 500, 1000, 1e18};
    r.hist_edges.assign(std::begin(edges), std::end(edges));
    r.hist_counts.assign(r.hist_edges.size(), 0);
    for (double ns : lat) {
        for (std::size_t b = 0; b < r.hist_edges.size(); ++b) {
            if (ns <= r.hist_edges[b]) { ++r.hist_counts[b]; break; }
        }
    }
    return r;
}

// A/B: pool vs new/delete.
static void bench_alloc(double& pool_ns, double& malloc_ns) {
    const int N = 2'000'000;
    {
        Pool<Order> pool(4096);
        std::vector<Order*> live;
        live.reserve(4096);
        auto t0 = Clock::now();
        for (int i = 0; i < N; ++i) {
            if (live.size() < 4000) live.push_back(pool.allocate());
            else { pool.deallocate(live.back()); live.pop_back(); }
        }
        pool_ns = ns_since(t0) / N;
        for (Order* o : live) pool.deallocate(o);
    }
    {
        std::vector<Order*> live;
        live.reserve(4096);
        auto t0 = Clock::now();
        for (int i = 0; i < N; ++i) {
            if (live.size() < 4000) live.push_back(new Order());
            else { delete live.back(); live.pop_back(); }
        }
        malloc_ns = ns_since(t0) / N;
        for (Order* o : live) delete o;
    }
}

// A/B: flat price-ladder access vs std::map.
static void bench_ladder(std::uint64_t seed, double& flat_ns, double& map_ns) {
    const int LEVELS = 4096, M = 4'000'000;
    Rng rng(seed);
    {
        std::vector<Qty> ladder(LEVELS, 0);
        for (int i = 0; i < LEVELS; ++i) ladder[i] = i + 1;
        volatile std::uint64_t sink = 0;
        auto t0 = Clock::now();
        for (int i = 0; i < M; ++i) sink += ladder[rng.bounded(LEVELS)];
        flat_ns = ns_since(t0) / M;
        (void)sink;
    }
    {
        std::map<int, Qty> tree;
        for (int i = 0; i < LEVELS; ++i) tree[i] = i + 1;
        volatile std::uint64_t sink = 0;
        auto t0 = Clock::now();
        for (int i = 0; i < M; ++i) sink += tree[static_cast<int>(rng.bounded(LEVELS))];
        map_ns = ns_since(t0) / M;
        (void)sink;
    }
}

// A/B: flat_hash vs std::unordered_map, under cancel/modify-style churn.
//
// A plain bulk-insert-then-lookup benchmark wouldn't really test FlatHash,
// since it's designed for the churn of live cancels and modifies, where
// every message both removes an id and admits a new one. So instead this
// keeps a working set of N resting orders and, per iteration, mimics one
// cancel-and-replace cycle the way the engine actually does it: find the
// resting id (as OrderBook::cancel does before unlinking), erase it, insert
// the next order's id. The ns/op reported is that whole find+erase+insert
// cycle, not a single lookup.
static void bench_hash(std::uint64_t seed, double& flat_ns, double& umap_ns) {
    const int N = 200000, M = 4'000'000;
    {
        FlatHash<Order*> h(1 << 19);
        std::vector<OrderId> live(N);
        OrderId next_id = 1;
        for (int i = 0; i < N; ++i, ++next_id) {
            live[i] = next_id;
            h.insert(next_id, reinterpret_cast<Order*>(static_cast<std::uintptr_t>(next_id)));
        }
        Rng rng(seed);
        volatile std::uint64_t sink = 0;
        auto t0 = Clock::now();
        for (int i = 0; i < M; ++i) {
            const std::size_t slot = rng.bounded(N);
            const OrderId cancel_id = live[slot];
            sink += reinterpret_cast<std::uintptr_t>(h.find(cancel_id));  // locate, as cancel() does
            h.erase(cancel_id);
            live[slot] = ++next_id;
            h.insert(next_id, reinterpret_cast<Order*>(static_cast<std::uintptr_t>(next_id)));
        }
        flat_ns = ns_since(t0) / M;
        (void)sink;
    }
    {
        std::unordered_map<OrderId, Order*> h;
        h.reserve(N * 2);
        std::vector<OrderId> live(N);
        OrderId next_id = 1;
        for (int i = 0; i < N; ++i, ++next_id) {
            live[i] = next_id;
            h[next_id] = reinterpret_cast<Order*>(static_cast<std::uintptr_t>(next_id));
        }
        Rng rng(seed);
        volatile std::uint64_t sink = 0;
        auto t0 = Clock::now();
        for (int i = 0; i < M; ++i) {
            const std::size_t slot = rng.bounded(N);
            const OrderId cancel_id = live[slot];
            auto it = h.find(cancel_id);
            if (it != h.end()) sink += reinterpret_cast<std::uintptr_t>(it->second);
            h.erase(cancel_id);
            live[slot] = ++next_id;
            h[next_id] = reinterpret_cast<Order*>(static_cast<std::uintptr_t>(next_id));
        }
        umap_ns = ns_since(t0) / M;
        (void)sink;
    }
}

// A/B: lock-free SPSC vs mutex queue, feed throughput in M msg/s.
static void bench_feed(std::uint64_t seed, double& spsc_mops, double& mutex_mops) {
    FeedParams fp;
    fp.n = 500000;
    const auto feed = generate_feed(fp, seed);
    {
        OrderBook book(fp.max_price, 700000);
        auto t0 = Clock::now();
        run_feed_spsc(book, feed);
        spsc_mops = fp.n / (ns_since(t0) / 1e3);   // msgs per microsecond == M msg/s
    }
    {
        OrderBook book(fp.max_price, 700000);
        auto t0 = Clock::now();
        run_feed_mutex(book, feed);
        mutex_mops = fp.n / (ns_since(t0) / 1e3);
    }
}

// Records a short book trace for the demo animation / WASM-load fallback.
static std::string record_replay(std::uint64_t seed) {
    FeedParams fp;
    fp.mid = 10000; fp.max_price = 20000; fp.band = 25; fp.n = 600; fp.p_cross = 0.16;
    const auto feed = generate_feed(fp, seed);

    OrderBook book(fp.max_price, 4096);
    std::vector<Trade> trades;

    std::string s = "{\"meta\":{\"generated\":\"native bench\",\"tick_size\":0.01,";
    s += "\"levels_shown\":8,\"mid\":" + std::to_string(fp.mid) + "},\"frames\":[";

    std::size_t prev_trades = 0;
    bool first = true;
    for (const FeedMsg& m : feed) {
        apply_msg(book, m, trades);
        if (!first) s += ",";
        first = false;
        s += "{\"a\":\"" + std::string(m.kind == FeedMsg::Kind::Add ? "add" : "cxl") + "\",";
        s += "\"bids\":[";
        auto bids = book.top_bids(8);
        for (std::size_t i = 0; i < bids.size(); ++i)
            s += (i ? "," : "") + std::string("[") + std::to_string(bids[i].price) + "," + std::to_string(bids[i].qty) + "]";
        s += "],\"asks\":[";
        auto asks = book.top_asks(8);
        for (std::size_t i = 0; i < asks.size(); ++i)
            s += (i ? "," : "") + std::string("[") + std::to_string(asks[i].price) + "," + std::to_string(asks[i].qty) + "]";
        s += "],\"trades\":[";
        for (std::size_t i = prev_trades; i < trades.size(); ++i) {
            const Trade& t = trades[i];
            s += (i > prev_trades ? "," : "") + std::string("[") + std::to_string(t.price) + "," +
                 std::to_string(t.qty) + "," + std::to_string(static_cast<int>(t.taker_side)) + "]";
        }
        prev_trades = trades.size();
        s += "]}";
    }
    s += "]}";
    return s;
}

static void write_file(const std::string& path, const std::string& contents) {
    std::ofstream f(path, std::ios::binary);
    f << contents;
    if (!f) {
        std::fprintf(stderr, "error: failed to write %s (bad path or missing directory?)\n", path.c_str());
        std::exit(1);
    }
    std::printf("wrote %s (%zu bytes)\n", path.c_str(), contents.size());
}

int main(int argc, char** argv) {
    const std::string out_dir = (argc > 1) ? argv[1] : "../data";
    const std::uint64_t seed = 0xC0FFEE;

    std::printf("measuring engine latency...\n");
    LatencyResult lat = measure_engine_latency(seed);

    std::printf("measuring A/B: pool vs new/delete...\n");
    double pool_ns, malloc_ns;      bench_alloc(pool_ns, malloc_ns);
    std::printf("measuring A/B: ladder vs std::map...\n");
    double flat_ns, map_ns;         bench_ladder(seed, flat_ns, map_ns);
    std::printf("measuring A/B: flat_hash vs unordered_map...\n");
    double fh_ns, umap_ns;          bench_hash(seed, fh_ns, umap_ns);
    std::printf("measuring A/B: SPSC vs mutex feed...\n");
    double spsc_mops, mutex_mops;   bench_feed(seed, spsc_mops, mutex_mops);

    const double engine_mops = 1000.0 / std::max(lat.p50, 1e-9);  // rough, from median

    auto num = [](double d) { char b[64]; std::snprintf(b, sizeof b, "%.2f", d); return std::string(b); };
    auto arr = [](const std::vector<double>& v) {
        std::string s = "[";
        for (std::size_t i = 0; i < v.size(); ++i) { char b[64]; std::snprintf(b, sizeof b, "%.6g", v[i]); s += (i?",":"") + std::string(b); }
        return s + "]";
    };
    auto larr = [](const std::vector<long>& v) {
        std::string s = "[";
        for (std::size_t i = 0; i < v.size(); ++i) s += (i?",":"") + std::to_string(v[i]);
        return s + "]";
    };

    std::string js = "// Auto-generated by lob-project/bench/bench.cpp -- do not edit by hand.\n";
    js += "// Native single-thread latency + threaded throughput; regenerate by re-running the bench.\n";
    js += "const DATA_LOB_BENCH = {";
    js += "\"meta\":{\"seed\":\"0xC0FFEE\",\"clock\":\"steady_clock\",\"note\":\"native build; latencies include ~timer overhead subtracted at median\"},";
    js += "\"latency\":{\"p50\":" + num(lat.p50) + ",\"p90\":" + num(lat.p90) +
          ",\"p99\":" + num(lat.p99) + ",\"p999\":" + num(lat.p999) +
          ",\"hist_edges\":" + arr(lat.hist_edges) + ",\"hist_counts\":" + larr(lat.hist_counts) + "},";
    js += "\"throughput\":{\"engine_mops\":" + num(engine_mops) +
          ",\"feed_spsc_mops\":" + num(spsc_mops) + ",\"feed_mutex_mops\":" + num(mutex_mops) + "},";
    js += "\"ab\":{";
    js += "\"pool_vs_malloc\":{\"labels\":[\"Pool allocator\",\"new / delete\"],\"ns\":[" + num(pool_ns) + "," + num(malloc_ns) + "]},";
    js += "\"ladder_vs_map\":{\"labels\":[\"Flat ladder\",\"std::map\"],\"ns\":[" + num(flat_ns) + "," + num(map_ns) + "]},";
    js += "\"flathash_vs_umap\":{\"labels\":[\"FlatHash\",\"std::unordered_map\"],\"ns\":[" + num(fh_ns) + "," + num(umap_ns) + "]},";
    js += "\"spsc_vs_mutex\":{\"labels\":[\"Lock-free SPSC\",\"std::mutex queue\"],\"mops\":[" + num(spsc_mops) + "," + num(mutex_mops) + "]}";
    js += "}};\n";
    write_file(out_dir + "/lob_bench.js", js);

    std::printf("recording replay trace...\n");
    std::string replay = "// Auto-generated by lob-project/bench/bench.cpp -- do not edit by hand.\n";
    replay += "// A short recorded book trace: seeds the live demo and is the fallback if WASM fails to load.\n";
    replay += "const DATA_LOB_REPLAY = " + record_replay(seed ^ 0x1234) + ";\n";
    write_file(out_dir + "/lob_replay.js", replay);

    std::printf("done.\n");
    return 0;
}
