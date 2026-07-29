// Fixed-capacity object pool / free-list allocator.
//
// Every add-order on the hot path allocates a node; every fill or cancel
// frees one. Doing that through malloc/operator new costs hundreds of
// nanoseconds, can take a lock under contention, and leaves orders scattered
// across the heap in whatever order the allocator felt like — bad for
// locality when a price level gets walked later.
//
// Instead we grab one contiguous slab up front and hand out slots from a
// LIFO free list. allocate()/deallocate() are just an index push/pop: O(1),
// no branches worth mentioning, no malloc ever touched after construction.
#pragma once

#include <cstddef>
#include <vector>

namespace lob {

template <class T>
class Pool {
public:
    explicit Pool(std::size_t capacity) : slab_(capacity) {
        free_.reserve(capacity);
        // Push in reverse so the first allocate() hands back slab_[0]; as the
        // book fills up, allocations march forward through the slab instead
        // of bouncing around it.
        for (std::size_t i = capacity; i-- > 0;) {
            free_.push_back(&slab_[i]);
        }
    }

    // O(1). Returns nullptr when the pool is exhausted (caller rejects the
    // order rather than growing — a real engine sizes the pool for its book).
    T* allocate() noexcept {
        if (free_.empty()) return nullptr;
        T* p = free_.back();
        free_.pop_back();
        ++in_use_;
        return p;
    }

    // O(1). The slot returns to the free list for immediate reuse.
    void deallocate(T* p) noexcept {
        free_.push_back(p);
        --in_use_;
    }

    std::size_t capacity() const noexcept { return slab_.size(); }
    std::size_t in_use()   const noexcept { return in_use_; }

private:
    std::vector<T>   slab_;    // owns the storage; never resized => pointers stay stable
    std::vector<T*>  free_;    // LIFO stack of available slots
    std::size_t      in_use_ = 0;
};

} // namespace lob
