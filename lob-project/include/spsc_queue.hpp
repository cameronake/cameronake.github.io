// Lock-free single-producer/single-consumer ring buffer.
//
// This sits between the feed handler and the matching engine: one thread
// decodes messages and pushes, exactly one other thread pops and applies
// them. Restricting to one writer and one reader means no mutex and no CAS
// loop are needed at all — two atomic counters with acquire/release ordering
// are enough to hand data safely across the core boundary.
//
// Two things matter here beyond plain correctness:
//   - head_ and tail_ each get their own 64-byte line via alignas, so a
//     producer write to tail_ never evicts the consumer's cached copy of
//     head_ (and vice versa). Skip this and every push/pop pays for a
//     coherence miss it doesn't need.
//   - each side also keeps a private, ordinary (non-atomic) copy of the
//     other side's counter, and only pays for a real atomic load when that
//     cached copy suggests the ring might be full or empty. In steady state
//     neither thread ever touches the other's atomic.
//
// Indices only ever go up — tail minus head is the live count, and `& mask_`
// turns an index into a slot. Capacity has to be a power of two.
#pragma once

#include <atomic>
#include <cstddef>
#include <new>
#include <vector>

namespace lob {

#if defined(__cpp_lib_hardware_interference_size)
inline constexpr std::size_t kCacheLine = std::hardware_destructive_interference_size;
#else
inline constexpr std::size_t kCacheLine = 64;
#endif

template <class T>
class SpscQueue {
public:
    explicit SpscQueue(std::size_t capacity_pow2) {
        std::size_t cap = 1;
        while (cap < capacity_pow2) cap <<= 1;
        buf_.resize(cap);
        mask_ = cap - 1;
    }

    // Producer side only. Returns false if the queue is full (caller decides
    // whether to spin, drop, or apply backpressure).
    bool try_push(const T& v) {
        const std::size_t t = tail_.load(std::memory_order_relaxed);
        if (t - cached_head_ >= buf_.size()) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if (t - cached_head_ >= buf_.size()) return false;  // genuinely full
        }
        buf_[t & mask_] = v;
        tail_.store(t + 1, std::memory_order_release);  // publish the slot
        return true;
    }

    // Consumer side only. Returns false if the queue is empty.
    bool try_pop(T& out) {
        const std::size_t h = head_.load(std::memory_order_relaxed);
        if (h == cached_tail_) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if (h == cached_tail_) return false;  // genuinely empty
        }
        out = buf_[h & mask_];
        head_.store(h + 1, std::memory_order_release);  // free the slot
        return true;
    }

    std::size_t capacity() const noexcept { return buf_.size(); }

private:
    std::vector<T> buf_;
    std::size_t    mask_ = 0;

    // Producer-owned line: the tail counter and the consumer's cached head.
    alignas(kCacheLine) std::atomic<std::size_t> tail_{0};
    std::size_t cached_head_ = 0;

    // Consumer-owned line: the head counter and the producer's cached tail.
    alignas(kCacheLine) std::atomic<std::size_t> head_{0};
    std::size_t cached_tail_ = 0;
};

} // namespace lob
