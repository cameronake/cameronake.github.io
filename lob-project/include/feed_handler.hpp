// Threaded feed ingest on top of the matching engine.
//
// Models the ingress half of a trading system: a producer thread decodes
// inbound messages and hands them off to a single engine thread, which
// applies them to the book. The lock-free SPSC queue (spsc_queue.hpp) carries
// messages between them; run_feed_mutex swaps that for a std::mutex-guarded
// queue purely so the benchmark has something to compare against.
//
// Both entry points spawn std::thread, so this header is native-only — none
// of it is part of the WASM build.
#pragma once

#include <cstddef>
#include <vector>

#include "order_book.hpp"
#include "types.hpp"

namespace lob {

// Apply one decoded message to the book. A cancel/modify that references an
// unknown id is a harmless no-op (the order already filled or never existed).
void apply_msg(OrderBook& book, const FeedMsg& m, std::vector<Trade>& trades);

// Lock-free path: a producer thread pushes every message onto an SPSC ring;
// the calling thread is the consumer/engine and applies them. Returns the
// number of trades generated.
std::size_t run_feed_spsc(OrderBook& book, const std::vector<FeedMsg>& msgs,
                          std::size_t queue_pow2 = std::size_t{1} << 16);

// Same workload over a std::mutex + std::deque queue — the baseline the
// lock-free ring is measured against.
std::size_t run_feed_mutex(OrderBook& book, const std::vector<FeedMsg>& msgs);

} // namespace lob
