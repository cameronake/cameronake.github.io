// Correctness tests for the matching engine. No framework — just a CHECK
// macro that records failures, and a main() that returns non-zero if any
// fired. Covers price-time priority, partial fills, cancel, modify (both
// in-place and cancel/replace), market/IOC orders, and the never-crossed-book
// invariant.
#include <cstdio>
#include <vector>

#include "flat_hash.hpp"
#include "order_book.hpp"
#include "pool.hpp"
#include "spsc_queue.hpp"
#include "types.hpp"

using namespace lob;

static int g_failures = 0;
#define CHECK(cond)                                                            \
    do {                                                                       \
        if (!(cond)) {                                                         \
            std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);        \
            ++g_failures;                                                      \
        }                                                                      \
    } while (0)

static OrderBook make_book() { return OrderBook(/*max_price=*/1000, /*pool=*/4096); }

static void test_rest_no_cross() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Buy, 100, 10, tr);
    b.add_limit(Side::Sell, 105, 8, tr);
    CHECK(tr.empty());                       // no crossing prices -> no trades
    CHECK(b.best_bid() == 100);
    CHECK(b.best_ask() == 105);
    CHECK(b.resting_orders() == 2);
}

static void test_full_and_partial_fill() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Sell, 100, 10, tr);    // resting ask
    b.add_limit(Side::Buy, 100, 4, tr);      // crosses: fills 4
    CHECK(tr.size() == 1);
    CHECK(tr[0].qty == 4);
    CHECK(tr[0].price == 100);
    CHECK(b.best_ask() == 100);              // 6 remain on the ask
    CHECK(b.best_bid() == -1);               // buyer fully filled, nothing rests

    b.add_limit(Side::Buy, 100, 6, tr);      // takes the rest
    CHECK(tr.size() == 2);
    CHECK(b.best_ask() == -1);               // ask level now empty
    CHECK(b.resting_orders() == 0);
}

static void test_time_priority() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    OrderId first  = b.add_limit(Side::Buy, 100, 5, tr);   // rests first
    OrderId second = b.add_limit(Side::Buy, 100, 5, tr);   // same price, later
    b.add_limit(Side::Sell, 100, 5, tr);                   // should hit `first`
    CHECK(tr.size() == 1);
    CHECK(tr[0].maker_id == first);          // FIFO: oldest filled first
    CHECK(tr[0].maker_id != second);
    CHECK(b.best_bid() == 100);              // `second` still rests
}

static void test_price_priority_sweep() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Sell, 102, 5, tr);
    b.add_limit(Side::Sell, 100, 5, tr);     // better ask
    b.add_limit(Side::Sell, 101, 5, tr);
    b.add_limit(Side::Buy, 102, 12, tr);     // sweeps 100, 101, then 2 @ 102
    CHECK(tr.size() == 3);
    CHECK(tr[0].price == 100);               // best price first
    CHECK(tr[1].price == 101);
    CHECK(tr[2].price == 102);
    CHECK(tr[2].qty == 2);
    CHECK(b.best_ask() == 102);              // 3 remain @ 102
}

static void test_cancel() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    OrderId id = b.add_limit(Side::Buy, 100, 10, tr);
    CHECK(b.best_bid() == 100);
    CHECK(b.cancel(id));
    CHECK(b.best_bid() == -1);
    CHECK(b.resting_orders() == 0);
    CHECK(!b.cancel(id));                     // second cancel is a no-op
    CHECK(!b.cancel(9999));                    // unknown id
}

static void test_modify_inplace_keeps_priority() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    OrderId first  = b.add_limit(Side::Buy, 100, 10, tr);
    OrderId second = b.add_limit(Side::Buy, 100, 10, tr);
    b.modify(first, 100, 6, tr);             // pure size-down: keeps its spot
    b.add_limit(Side::Sell, 100, 6, tr);     // must still hit `first`
    CHECK(tr.size() == 1);
    CHECK(tr[0].maker_id == first);
    CHECK(tr[0].qty == 6);
    (void)second;
}

static void test_modify_reprice_loses_priority() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    OrderId first  = b.add_limit(Side::Buy, 100, 5, tr);
    OrderId second = b.add_limit(Side::Buy, 100, 5, tr);
    b.modify(first, 101, 5, tr);             // reprice up: cancel/replace, new tail
    CHECK(b.best_bid() == 101);
    b.add_limit(Side::Sell, 100, 5, tr);     // hits 101 first (better price)
    CHECK(!tr.empty());
    CHECK(tr.back().price == 101);
    (void)second;
}

static void test_market_order() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Sell, 100, 5, tr);
    b.add_limit(Side::Sell, 101, 5, tr);
    b.add_market(Side::Buy, 7, tr);          // sweeps 5 @100 + 2 @101, never rests
    CHECK(tr.size() == 2);
    CHECK(b.best_ask() == 101);
    CHECK(b.best_bid() == -1);               // market residual (if any) never rests
}

static void test_ioc_order() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Sell, 100, 3, tr);
    b.add_ioc(Side::Buy, 100, 10, tr);       // fills 3, drops the remaining 7
    CHECK(tr.size() == 1);
    CHECK(tr[0].qty == 3);
    CHECK(b.best_bid() == -1);               // IOC never rests
    CHECK(b.resting_orders() == 0);
}

static void test_no_crossed_book() {
    OrderBook b = make_book();
    std::vector<Trade> tr;
    b.add_limit(Side::Buy, 100, 5, tr);
    b.add_limit(Side::Sell, 99, 5, tr);      // aggressive sell crosses -> must match
    CHECK(!tr.empty());
    // After any op the book is never crossed: best_bid < best_ask (or a side empty).
    if (b.best_bid() != -1 && b.best_ask() != -1) CHECK(b.best_bid() < b.best_ask());
}

// Structural sanity for the building blocks the engine relies on.
static void test_pool() {
    Pool<Order> p(3);
    Order* a = p.allocate();
    Order* b = p.allocate();
    Order* c = p.allocate();
    CHECK(a && b && c);
    CHECK(p.allocate() == nullptr);          // exhausted
    p.deallocate(b);
    CHECK(p.allocate() == b);                // reused
    CHECK(p.in_use() == 3);
}

static void test_flat_hash() {
    FlatHash<Order*> h(16);
    Order dummy;
    h.insert(42, &dummy);
    h.insert(7, &dummy);
    CHECK(h.find(42) == &dummy);
    CHECK(h.find(7) == &dummy);
    CHECK(h.find(1) == nullptr);
    CHECK(h.erase(42));
    CHECK(h.find(42) == nullptr);
    CHECK(h.find(7) == &dummy);               // probe chain survived the tombstone
    CHECK(!h.erase(42));
}

static void test_spsc() {
    SpscQueue<int> q(4);
    int out = 0;
    CHECK(!q.try_pop(out));                    // empty
    for (int i = 0; i < 4; ++i) CHECK(q.try_push(i));
    CHECK(!q.try_push(99));                     // full
    for (int i = 0; i < 4; ++i) { CHECK(q.try_pop(out)); CHECK(out == i); }
    CHECK(!q.try_pop(out));                    // empty again
}

int main() {
    test_rest_no_cross();
    test_full_and_partial_fill();
    test_time_priority();
    test_price_priority_sweep();
    test_cancel();
    test_modify_inplace_keeps_priority();
    test_modify_reprice_loses_priority();
    test_market_order();
    test_ioc_order();
    test_no_crossed_book();
    test_pool();
    test_flat_hash();
    test_spsc();

    if (g_failures == 0) {
        std::printf("all tests passed\n");
        return 0;
    }
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
}
