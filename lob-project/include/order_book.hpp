// Price-time-priority limit order book and matching engine.
//
// The book itself is a flat price ladder — one array indexed directly by
// price tick, each slot holding a FIFO of the orders resting there. That
// gets us O(1), cache-resident lookups for the best price or any level,
// versus a std::map<Price, Level> where every level is a separate heap node
// reached through a pointer chase down a red-black tree.
//
// Time priority falls out of the FIFO within each level (Order in types.hpp
// carries its own prev/next: new orders append at the tail, fills come off
// the head). Order nodes come from a Pool so there's no hot-path malloc, and
// id -> node lookups for cancel/modify go through a FlatHash instead of a
// chained map.
//
// best_bid_/best_ask_ are just cursors, nudged by a short linear scan
// whenever a level empties out — a real venue would use a bitset or SIMD
// scan instead, but since order flow clusters near the mid these scans stay
// short in practice. What this file is actually demonstrating is the flat
// ladder layout, not a fancy best-price index.
#pragma once

#include <cstddef>
#include <vector>

#include "flat_hash.hpp"
#include "pool.hpp"
#include "types.hpp"

namespace lob {

// One rung of the ladder: an intrusive FIFO of resting orders plus aggregates
// so depth queries don't have to walk the list.
struct Level {
    Order*        head  = nullptr;
    Order*        tail  = nullptr;
    Qty           total = 0;   // sum of resting qty at this price
    std::uint32_t count = 0;   // number of resting orders
};

// A flattened level for snapshots / depth-of-book display.
struct LevelView {
    Price         price = 0;
    Qty           qty   = 0;
    std::uint32_t count = 0;
};

class OrderBook {
public:
    // max_price bounds the ladder (ticks in [0, max_price)); pool_capacity is
    // the maximum number of simultaneously resting orders.
    OrderBook(Price max_price, std::size_t pool_capacity);

    // Submit an order. Any resulting fills are appended to `out_trades` (not
    // cleared — the caller owns it). Returns the engine-assigned id, or 0 if
    // the order was rejected (bad price, or pool exhausted).
    OrderId add_limit (Side side, Price price, Qty qty, std::vector<Trade>& out_trades);
    OrderId add_market(Side side, Qty qty,             std::vector<Trade>& out_trades);
    OrderId add_ioc   (Side side, Price price, Qty qty, std::vector<Trade>& out_trades);

    // Remove a resting order. Returns false if the id is unknown (already
    // filled or never rested).
    bool cancel(OrderId id);

    // Change price and/or quantity. A price change or quantity *increase* loses
    // time priority (re-queued at the tail of the new level); a pure quantity
    // *decrease* keeps priority (edited in place). Returns false if unknown.
    bool modify(OrderId id, Price new_price, Qty new_qty, std::vector<Trade>& out_trades);

    // -1 means "no resting order on that side".
    Price best_bid() const noexcept { return best_bid_; }
    Price best_ask() const noexcept { return best_ask_ >= max_price_ ? -1 : best_ask_; }

    // Top `n` levels per side, best first. For depth-of-book rendering.
    std::vector<LevelView> top_bids(int n) const;
    std::vector<LevelView> top_asks(int n) const;

    // Rolling tape of the most recent trades (capped), newest last.
    const std::vector<Trade>& tape() const noexcept { return tape_; }

    std::size_t resting_orders() const noexcept { return pool_.in_use(); }

private:
    OrderId submit(Side side, OrderType type, Price price, Qty qty,
                   std::vector<Trade>& out_trades);
    // Match `incoming` against the opposite side as far as price allows,
    // emitting trades. Returns remaining unfilled qty.
    Qty match(Side side, Price limit, Qty qty, OrderId taker_id, OrderType type,
              std::vector<Trade>& out_trades);
    void rest(Order* o);        // append to its price level's FIFO
    void unlink(Order* o);      // remove from its level (does not free)
    void push_tape(const Trade& t);
    void raise_best_ask();      // scan up to the next non-empty ask level
    void lower_best_bid();      // scan down to the next non-empty bid level

    Price                max_price_;
    Pool<Order>          pool_;
    FlatHash<Order*>     index_;
    std::vector<Level>   levels_;      // size == max_price_; indexed by price
    Price                best_bid_ = -1;
    Price                best_ask_;    // == max_price_ means "none"
    OrderId              next_id_  = 1;
    std::vector<Trade>   tape_;
    std::size_t          tape_cap_ = 64;
};

} // namespace lob
