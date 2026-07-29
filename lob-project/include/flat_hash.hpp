// Open-addressing hash map from OrderId to a value (in practice, Order*).
//
// Cancels and modifies come in by id, so the engine needs a fast id -> node
// lookup. std::unordered_map chains: each entry is its own heap node reached
// by pointer, so a lookup is a hash plus a walk through scattered memory —
// at least one cache miss, often more.
//
// Here keys and values just live in one flat array. A collision moves to the
// next slot (linear probing), which is usually still in the same cache line,
// and nothing gets individually allocated. For small integer keys under the
// kind of churn an order book sees, this ends up quite a bit faster.
//
// Two sentinels make it work: key 0 means the slot is empty, key ~0 means
// tombstone (erased, but a probe still has to step over it rather than treat
// it as empty — otherwise chains behind it would break). Engine-assigned
// OrderIds live strictly between those two values, so there's no ambiguity.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "types.hpp"

namespace lob {

template <class V>
class FlatHash {
public:
    explicit FlatHash(std::size_t initial_pow2 = 1024) {
        std::size_t cap = 1;
        while (cap < initial_pow2) cap <<= 1;
        slots_.assign(cap, Slot{});
        mask_ = cap - 1;
    }

    void insert(OrderId key, V val) {
        if ((size_ + 1) * 10 >= slots_.size() * 7) grow();  // keep load factor < 0.7
        std::size_t i = index(key);
        std::size_t first_tomb = kNoSlot;
        while (true) {
            Slot& s = slots_[i];
            if (s.key == kEmpty) {
                Slot& dst = (first_tomb == kNoSlot) ? s : slots_[first_tomb];
                dst.key = key;
                dst.val = val;
                ++size_;
                return;
            }
            if (s.key == kTomb) {
                if (first_tomb == kNoSlot) first_tomb = i;
            } else if (s.key == key) {
                s.val = val;  // update in place
                return;
            }
            i = (i + 1) & mask_;
        }
    }

    // Returns V{} (nullptr for pointer values) when the key is absent.
    V find(OrderId key) const {
        std::size_t i = index(key);
        while (true) {
            const Slot& s = slots_[i];
            if (s.key == kEmpty) return V{};
            if (s.key == key)    return s.val;
            i = (i + 1) & mask_;
        }
    }

    bool erase(OrderId key) {
        std::size_t i = index(key);
        while (true) {
            Slot& s = slots_[i];
            if (s.key == kEmpty) return false;
            if (s.key == key) {
                s.key = kTomb;   // leave a tombstone so probe chains stay intact
                s.val = V{};
                --size_;
                return true;
            }
            i = (i + 1) & mask_;
        }
    }

    std::size_t size() const noexcept { return size_; }

private:
    struct Slot {
        OrderId key = kEmpty;
        V       val = V{};
    };

    static constexpr OrderId     kEmpty  = 0;
    static constexpr OrderId     kTomb   = ~OrderId{0};
    static constexpr std::size_t kNoSlot = ~std::size_t{0};

    std::size_t index(OrderId key) const noexcept {
        // Fibonacci hashing: multiply by 2^64/phi and take the high bits via
        // the mask. Cheap, and spreads sequential ids across the table well.
        return (key * 0x9E3779B97F4A7C15ull >> 32) & mask_;
    }

    void grow() {
        std::vector<Slot> old = std::move(slots_);
        slots_.assign(old.size() * 2, Slot{});
        mask_ = slots_.size() - 1;
        size_ = 0;
        for (const Slot& s : old) {
            if (s.key != kEmpty && s.key != kTomb) insert(s.key, s.val);
        }
    }

    std::vector<Slot> slots_;
    std::size_t       mask_ = 0;
    std::size_t       size_ = 0;
};

} // namespace lob
