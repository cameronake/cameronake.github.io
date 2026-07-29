// Deterministic order-flow generator — a reproducible stand-in for a real
// market-data feed. Mostly resting limit adds clustered near the mid, with
// occasional aggressive orders that cross and trigger a match, plus cancels
// of earlier orders. The benchmark and the WASM demo both use this, so they
// drive the engine off identical, seed-stable flow.
//
// One wrinkle: this generator never calls modify, and add is the only op
// that assigns an id, so the k-th add is guaranteed to land engine id k.
// That lets a cancel just guess a plausible earlier id without the generator
// tracking real state. If that id already filled, the cancel is a no-op,
// same as it would be against a real venue.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "types.hpp"

namespace lob {

// Small, fast, portable xorshift64* — identical stream on every platform.
struct Rng {
    std::uint64_t s;
    explicit Rng(std::uint64_t seed) : s(seed ? seed : 0x9E3779B97F4A7C15ull) {}
    std::uint64_t next() {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        return s * 0x2545F4914F6CDD1Dull;
    }
    std::uint32_t bounded(std::uint32_t n) { return static_cast<std::uint32_t>(next() % n); }
    double unit() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
};

struct FeedParams {
    Price       mid       = 10000;   // starting mid, in ticks
    Price       max_price = 20000;   // ladder bound
    int         band      = 40;      // orders land within +/- band ticks of the mid
    double      p_add     = 0.72;    // P(event is an add); otherwise a cancel
    double      p_cross   = 0.10;    // of adds, P(it is aggressive / crosses the mid)
    Qty         max_qty   = 500;
    std::size_t n         = 200000;  // number of messages
};

inline std::vector<FeedMsg> generate_feed(const FeedParams& p, std::uint64_t seed) {
    Rng rng(seed);
    std::vector<FeedMsg> out;
    out.reserve(p.n);
    OrderId add_seq = 0;   // running count of adds == highest engine id assigned

    for (std::size_t i = 0; i < p.n; ++i) {
        FeedMsg m;
        if (rng.unit() < p.p_add) {
            m.kind = FeedMsg::Kind::Add;
            const Side side = (rng.unit() < 0.5) ? Side::Buy : Side::Sell;
            m.side = side;
            const int off = static_cast<int>(rng.bounded(static_cast<std::uint32_t>(p.band))) + 1;
            Price price;
            if (rng.unit() < p.p_cross) {
                // Aggressive: quote through the mid to lift/hit the other side.
                price = (side == Side::Buy) ? p.mid + off : p.mid - off;
            } else {
                // Passive: rest on your own side of the mid.
                price = (side == Side::Buy) ? p.mid - off : p.mid + off;
            }
            if (price < 1) price = 1;
            if (price >= p.max_price) price = p.max_price - 1;
            m.price = price;
            m.qty   = rng.bounded(p.max_qty) + 1;
            ++add_seq;
        } else {
            m.kind = FeedMsg::Kind::Cancel;
            m.id = (add_seq > 0) ? static_cast<OrderId>(rng.bounded(static_cast<std::uint32_t>(add_seq)) + 1) : 0;
        }
        out.push_back(m);
    }
    return out;
}

} // namespace lob
