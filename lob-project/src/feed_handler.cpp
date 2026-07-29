// See feed_handler.hpp for what this is modeling.
#include "feed_handler.hpp"

#include <deque>
#include <mutex>
#include <thread>

#include "spsc_queue.hpp"

namespace lob {

void apply_msg(OrderBook& book, const FeedMsg& m, std::vector<Trade>& trades) {
    switch (m.kind) {
        case FeedMsg::Kind::Add:
            book.add_limit(m.side, m.price, m.qty, trades);
            break;
        case FeedMsg::Kind::Cancel:
            book.cancel(m.id);
            break;
        case FeedMsg::Kind::Modify:
            book.modify(m.id, m.price, m.qty, trades);
            break;
    }
}

std::size_t run_feed_spsc(OrderBook& book, const std::vector<FeedMsg>& msgs,
                          std::size_t queue_pow2) {
    SpscQueue<FeedMsg> queue(queue_pow2);
    const std::size_t total = msgs.size();

    // Producer: decode + enqueue. Spins when the ring is momentarily full,
    // which is exactly the backpressure a real handler would apply.
    std::thread producer([&] {
        for (const FeedMsg& m : msgs) {
            while (!queue.try_push(m)) { /* spin */ }
        }
    });

    // Consumer (this thread) is the matching engine: pop and apply.
    std::vector<Trade> trades;
    trades.reserve(total / 4);
    std::size_t applied = 0;
    FeedMsg m;
    while (applied < total) {
        if (queue.try_pop(m)) {
            apply_msg(book, m, trades);
            ++applied;
        }
    }

    producer.join();
    return trades.size();
}

std::size_t run_feed_mutex(OrderBook& book, const std::vector<FeedMsg>& msgs) {
    std::mutex           mtx;
    std::deque<FeedMsg>  queue;
    const std::size_t    total = msgs.size();

    std::thread producer([&] {
        for (const FeedMsg& m : msgs) {
            std::lock_guard<std::mutex> lk(mtx);
            queue.push_back(m);
        }
    });

    std::vector<Trade> trades;
    trades.reserve(total / 4);
    std::size_t applied = 0;
    while (applied < total) {
        FeedMsg m;
        bool got = false;
        {
            std::lock_guard<std::mutex> lk(mtx);
            if (!queue.empty()) {
                m = queue.front();
                queue.pop_front();
                got = true;
            }
        }
        if (got) {
            apply_msg(book, m, trades);
            ++applied;
        }
    }

    producer.join();
    return trades.size();
}

} // namespace lob
