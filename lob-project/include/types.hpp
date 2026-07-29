// Core value types shared by the book, the pool, the hash map and the feed.
//
// Prices are plain integer ticks rather than floats. Real venues quote on a
// discrete grid anyway, so ticks are exact and let the ladder index straight
// into an array. One tick == one cent in the demo; the engine itself never
// cares what a tick is worth.
#pragma once

#include <cstdint>

namespace lob {

using Price   = std::int32_t;   // price in ticks; [0, max_price) index into the ladder
using Qty     = std::uint32_t;  // share/contract quantity
using OrderId = std::uint64_t;  // monotonic, engine-assigned; 0 == "no order"

enum class Side : std::uint8_t { Buy = 0, Sell = 1 };

inline Side opposite(Side s) noexcept {
    return s == Side::Buy ? Side::Sell : Side::Buy;
}

enum class OrderType : std::uint8_t {
    Limit  = 0,   // rest on the book if not fully filled
    Market = 1,   // sweep the book at any price; never rests
    Ioc    = 2,   // immediate-or-cancel: match what you can, drop the rest
};

// Orders resting at a price level sit in an intrusive doubly-linked FIFO —
// prev/next live on the order itself, so there's no separate list node to
// allocate. The order just *is* the node.
struct Order {
    OrderId id    = 0;
    Side    side  = Side::Buy;
    Price   price = 0;
    Qty     qty   = 0;      // remaining (unfilled) quantity
    Order*  prev  = nullptr;
    Order*  next  = nullptr;
};

// A single match. `price` is always the resting (maker) order's price, since
// the taker trades at whatever price is already on the book — that's the
// "price improvement" part of price-time priority.
struct Trade {
    OrderId taker_id = 0;
    OrderId maker_id = 0;
    Price   price    = 0;
    Qty     qty      = 0;
    Side    taker_side = Side::Buy;
};

// One inbound message on the market-data / order-entry feed. The feed handler
// decodes a raw wire message into one of these and hands it to the engine
// thread over the SPSC queue.
struct FeedMsg {
    enum class Kind : std::uint8_t { Add, Cancel, Modify } kind = Kind::Add;
    OrderId id        = 0;   // client-side id for cancel/modify targeting (Add: ignored)
    Side    side      = Side::Buy;
    Price   price     = 0;
    Qty     qty       = 0;
};

} // namespace lob
