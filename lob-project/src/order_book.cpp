// Matching engine implementation. See order_book.hpp for the design notes.
#include "order_book.hpp"

#include <algorithm>

namespace lob {

OrderBook::OrderBook(Price max_price, std::size_t pool_capacity)
    : max_price_(max_price),
      pool_(pool_capacity),
      index_(pool_capacity ? pool_capacity * 2 : 1024),
      levels_(static_cast<std::size_t>(max_price)),
      best_ask_(max_price) {   // best_ask_ == max_price_ encodes "no asks"
    tape_.reserve(tape_cap_ + 1);
}

OrderId OrderBook::add_limit(Side side, Price price, Qty qty, std::vector<Trade>& out) {
    if (price < 0 || price >= max_price_ || qty == 0) return 0;
    return submit(side, OrderType::Limit, price, qty, out);
}

OrderId OrderBook::add_ioc(Side side, Price price, Qty qty, std::vector<Trade>& out) {
    if (price < 0 || price >= max_price_ || qty == 0) return 0;
    return submit(side, OrderType::Ioc, price, qty, out);
}

OrderId OrderBook::add_market(Side side, Qty qty, std::vector<Trade>& out) {
    if (qty == 0) return 0;
    return submit(side, OrderType::Market, 0, qty, out);
}

bool OrderBook::cancel(OrderId id) {
    Order* o = index_.find(id);
    if (!o) return false;
    unlink(o);
    index_.erase(id);
    pool_.deallocate(o);
    return true;
}

bool OrderBook::modify(OrderId id, Price new_price, Qty new_qty, std::vector<Trade>& out) {
    if (new_price < 0 || new_price >= max_price_) return false;
    Order* o = index_.find(id);
    if (!o) return false;
    if (new_qty == 0) return cancel(id);

    // Pure size reduction at the same price keeps time priority: just shrink
    // the resting quantity in place.
    if (new_price == o->price && new_qty <= o->qty) {
        levels_[o->price].total -= (o->qty - new_qty);
        o->qty = new_qty;
        return true;
    }

    // Price change or size increase == cancel/replace: the order goes to the
    // back of the new level (and may cross the book on the way in).
    Side side = o->side;
    cancel(id);
    submit(side, OrderType::Limit, new_price, new_qty, out);
    return true;
}

OrderId OrderBook::submit(Side side, OrderType type, Price price, Qty qty,
                          std::vector<Trade>& out) {
    const OrderId id = next_id_++;

    if (type == OrderType::Market) {
        // Sweep at any price: cap the limit at the far end of the ladder.
        const Price limit = (side == Side::Buy) ? (max_price_ - 1) : 0;
        match(side, limit, qty, id, type, out);
        return id;                       // market orders never rest
    }

    const Qty remaining = match(side, price, qty, id, type, out);
    if (remaining > 0 && type == OrderType::Limit) {
        Order* o = pool_.allocate();
        if (!o) return id;               // pool exhausted: residual rejected
        *o = Order{id, side, price, remaining, nullptr, nullptr};
        index_.insert(id, o);
        rest(o);
    }
    // Ioc: anything unfilled is discarded.
    return id;
}

Qty OrderBook::match(Side side, Price limit, Qty qty, OrderId taker_id, OrderType,
                     std::vector<Trade>& out) {
    if (side == Side::Buy) {
        // A buy lifts asks from the lowest price up, as long as it's <= limit.
        while (qty > 0 && best_ask_ < max_price_ && best_ask_ <= limit) {
            Level& lvl = levels_[best_ask_];
            Order* maker = lvl.head;                 // oldest resting order (time priority)
            const Qty fill = std::min(qty, maker->qty);

            out.push_back(Trade{taker_id, maker->id, best_ask_, fill, side});
            push_tape(out.back());

            qty        -= fill;
            maker->qty -= fill;
            lvl.total  -= fill;

            if (maker->qty == 0) {                   // maker fully filled: pop head
                lvl.head = maker->next;
                if (lvl.head) lvl.head->prev = nullptr; else lvl.tail = nullptr;
                --lvl.count;
                index_.erase(maker->id);
                pool_.deallocate(maker);
                if (lvl.count == 0) raise_best_ask();
            }
            // If the maker survived, the taker's qty is now 0 and the loop ends.
        }
    } else {
        // A sell hits bids from the highest price down, as long as it's >= limit.
        while (qty > 0 && best_bid_ >= 0 && best_bid_ >= limit) {
            Level& lvl = levels_[best_bid_];
            Order* maker = lvl.head;
            const Qty fill = std::min(qty, maker->qty);

            out.push_back(Trade{taker_id, maker->id, best_bid_, fill, side});
            push_tape(out.back());

            qty        -= fill;
            maker->qty -= fill;
            lvl.total  -= fill;

            if (maker->qty == 0) {
                lvl.head = maker->next;
                if (lvl.head) lvl.head->prev = nullptr; else lvl.tail = nullptr;
                --lvl.count;
                index_.erase(maker->id);
                pool_.deallocate(maker);
                if (lvl.count == 0) lower_best_bid();
            }
        }
    }
    return qty;
}

// Level bookkeeping below: linking/unlinking orders and nudging best bid/ask.

void OrderBook::rest(Order* o) {
    Level& lvl = levels_[o->price];
    o->prev = lvl.tail;
    o->next = nullptr;
    if (lvl.tail) lvl.tail->next = o; else lvl.head = o;
    lvl.tail = o;
    ++lvl.count;
    lvl.total += o->qty;

    if (o->side == Side::Buy) {
        if (o->price > best_bid_) best_bid_ = o->price;
    } else {
        if (o->price < best_ask_) best_ask_ = o->price;
    }
}

void OrderBook::unlink(Order* o) {
    Level& lvl = levels_[o->price];
    if (o->prev) o->prev->next = o->next; else lvl.head = o->next;
    if (o->next) o->next->prev = o->prev; else lvl.tail = o->prev;
    --lvl.count;
    lvl.total -= o->qty;
    if (lvl.count == 0) {
        if (o->side == Side::Buy && o->price == best_bid_)  lower_best_bid();
        else if (o->side == Side::Sell && o->price == best_ask_) raise_best_ask();
    }
}

void OrderBook::raise_best_ask() {
    Price p = best_ask_ + 1;
    while (p < max_price_ && levels_[p].count == 0) ++p;
    best_ask_ = p;                       // == max_price_ if no asks remain
}

void OrderBook::lower_best_bid() {
    Price p = best_bid_ - 1;
    while (p >= 0 && levels_[p].count == 0) --p;
    best_bid_ = p;                       // == -1 if no bids remain
}

void OrderBook::push_tape(const Trade& t) {
    tape_.push_back(t);
    if (tape_.size() > tape_cap_) tape_.erase(tape_.begin());
}

std::vector<LevelView> OrderBook::top_bids(int n) const {
    std::vector<LevelView> out;
    for (Price p = best_bid_; p >= 0 && static_cast<int>(out.size()) < n; --p) {
        const Level& lvl = levels_[p];
        if (lvl.count > 0) out.push_back(LevelView{p, lvl.total, lvl.count});
    }
    return out;
}

std::vector<LevelView> OrderBook::top_asks(int n) const {
    std::vector<LevelView> out;
    for (Price p = best_ask_; p < max_price_ && static_cast<int>(out.size()) < n; ++p) {
        const Level& lvl = levels_[p];
        if (lvl.count > 0) out.push_back(LevelView{p, lvl.total, lvl.count});
    }
    return out;
}

} // namespace lob
