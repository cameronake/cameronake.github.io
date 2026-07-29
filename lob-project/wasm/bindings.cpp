// Emscripten C API for the browser live demo.
//
// This exposes the single-threaded engine to JavaScript. The lock-free feed
// handler stays out of the WASM build entirely — browser WASM doesn't get
// real OS threads the way native code does, and its timing wouldn't mean
// much anyway, so this file only pulls in order_book and the feed generator.
//
// Snapshot strings come back through one reused std::string; its c_str() is
// valid until the next snapshot call, which is fine since the JS side copies
// it out immediately with UTF8ToString. No per-call malloc/free to manage.
#include <string>
#include <vector>

#include "order_book.hpp"
#include "synthetic_feed.hpp"

#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#else
#define EMSCRIPTEN_KEEPALIVE
#endif

using namespace lob;

namespace {
OrderBook*           g_book   = nullptr;
std::vector<FeedMsg> g_feed;         // pre-generated flow for "replay feed"
std::size_t          g_cursor = 0;
std::vector<Trade>   g_trades;       // sink for fills (tape lives in the book)
std::string          g_snap;         // reused snapshot buffer
Price                g_max_price = 20000;
unsigned long        g_ops = 0;

inline Side to_side(int s) { return s == 0 ? Side::Buy : Side::Sell; }

void append_levels(std::string& s, const std::vector<LevelView>& lv) {
    s += "[";
    for (std::size_t i = 0; i < lv.size(); ++i) {
        if (i) s += ",";
        s += "[" + std::to_string(lv[i].price) + "," + std::to_string(lv[i].qty) + "]";
    }
    s += "]";
}
} // namespace

extern "C" {

EMSCRIPTEN_KEEPALIVE
void lob_reset(int max_price, int pool_cap) {
    delete g_book;
    g_max_price = max_price;
    g_book = new OrderBook(max_price, static_cast<std::size_t>(pool_cap));

    FeedParams fp;
    fp.mid       = max_price / 2;
    fp.max_price = max_price;
    fp.band      = 25;
    fp.p_cross   = 0.14;
    fp.n         = 100000;
    g_feed  = generate_feed(fp, 0xBEEFu);
    g_cursor = 0;
    g_ops    = 0;
    g_trades.clear();
}

EMSCRIPTEN_KEEPALIVE
unsigned lob_submit_limit(int side, int price, unsigned qty) {
    if (!g_book) return 0;
    OrderId id = g_book->add_limit(to_side(side), price, qty, g_trades);
    ++g_ops;
    return static_cast<unsigned>(id);
}

EMSCRIPTEN_KEEPALIVE
void lob_market(int side, unsigned qty) {
    if (!g_book) return;
    g_book->add_market(to_side(side), qty, g_trades);
    ++g_ops;
}

EMSCRIPTEN_KEEPALIVE
void lob_cancel(unsigned id) {
    if (!g_book) return;
    g_book->cancel(id);
    ++g_ops;
}

// Apply up to n pre-generated feed messages; returns how many were applied
// (fewer than n once the pre-generated flow is exhausted).
EMSCRIPTEN_KEEPALIVE
int lob_step_feed(int n) {
    if (!g_book) return 0;
    int applied = 0;
    for (int i = 0; i < n && g_cursor < g_feed.size(); ++i, ++g_cursor) {
        const FeedMsg& m = g_feed[g_cursor];
        if (m.kind == FeedMsg::Kind::Add)      g_book->add_limit(m.side, m.price, m.qty, g_trades);
        else if (m.kind == FeedMsg::Kind::Cancel) g_book->cancel(m.id);
        ++g_ops;
        ++applied;
    }
    return applied;
}

// JSON snapshot: top `depth` levels per side, the recent trade tape, best
// prices, and running counters. Shape matches DATA_LOB_REPLAY frames so the
// page renders live snapshots and recorded frames with the same code.
EMSCRIPTEN_KEEPALIVE
const char* lob_snapshot(int depth) {
    g_snap.clear();
    if (!g_book) { g_snap = "{}"; return g_snap.c_str(); }

    g_snap += "{\"bids\":";
    append_levels(g_snap, g_book->top_bids(depth));
    g_snap += ",\"asks\":";
    append_levels(g_snap, g_book->top_asks(depth));

    g_snap += ",\"trades\":[";
    const auto& tape = g_book->tape();
    for (std::size_t i = 0; i < tape.size(); ++i) {
        if (i) g_snap += ",";
        g_snap += "[" + std::to_string(tape[i].price) + "," + std::to_string(tape[i].qty) +
                  "," + std::to_string(static_cast<int>(tape[i].taker_side)) + "]";
    }
    g_snap += "]";

    g_snap += ",\"best_bid\":" + std::to_string(g_book->best_bid());
    g_snap += ",\"best_ask\":" + std::to_string(g_book->best_ask());
    g_snap += ",\"ops\":" + std::to_string(g_ops);
    g_snap += ",\"resting\":" + std::to_string(g_book->resting_orders());
    g_snap += "}";
    return g_snap.c_str();
}

} // extern "C"
