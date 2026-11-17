"""Dip-scale mean-reversion bot for make.fun btc-race-24h-20261117-0603.

Strategy (long only, one symbol CBBTC, $1,000 paper USDC):
  - Short-horizon dislocation: enter when the close is at least 100 bps
    below where it was 60 minutes ago. This dev window is a tight
    sideways range (64.5k -> 64.8k, hourly ranges mostly 40-120 bps);
    the 4-hour drops the previous race's bot waited for never happen
    here (min 240-min return is only -150 bps), so the lookback is
    shortened to 60 minutes. On this window a 60-minute drop of 100+
    bps is followed by a positive 60-minute forward return in every
    observed case (mean +40 bps), i.e. the dips mean-revert.
  - Scale in: buy in three equal tranches of one third of starting
    equity as the drop deepens past 100 / 130 / 160 bps vs 60 minutes
    ago, so the average cost sits near the middle of the decline
    instead of at its top. Entry confirmed by a 14-bar RSI under 45.
  - Exit: take profit at +150 bps over the position's average cost, or
    a trailing stop 100 bps below the highest close seen since entry
    (the stop also cuts a position that keeps falling, freeing cash to
    re-enter lower), or after 1,440 bars. 30-bar cooldown after an exit.
  - Nothing else: no shorts, no leverage, no wall clock, no network, no
    randomness. Every decision is a pure function of the bars seen so
    far, so two runs on the same window produce identical replies.

Costs matter: a full-size round trip pays ~40 bps on this pool (4 bps
fee + 2 bps slippage + ~15 bps of price impact each side at the dev
window's depth), so entries only fire on dislocations of 100+ bps and
exits only after 150 bps of profit or a 100 bps give-back from the peak.

Parameters sit in the middle of a broad positive plateau on the dev
window (60-min lookback, entry 80-120 bps, TP 120-200 bps, trail
80-150 bps all clear +$14 on dev), not at a knife-edge optimum.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
# 60-minute return thresholds (bps) for the three scale-in tranches.
TRANCHES_BPS = (100, 130, 160)
TAKE_PROFIT_BPS = 150
TRAIL_BPS = 100
MAX_HOLD_BARS = 1440
COOLDOWN_BARS = 30
RSI_BARS = 14
RSI_MAX = 45
LOOKBACK_BARS = 60
MAX_SLIPPAGE_BPS = 100


class Bot:
    def __init__(self):
        self.closes = []          # closes in USD (float), oldest first
        self.tranche_units = 0    # quote units per tranche, set on hello
        self.entry_seq = None     # seq of the bar the position was opened on
        self.n_bought = 0         # tranches bought for the current position
        self.peak = 0.0           # highest close since entry
        self.last_exit_seq = -10 ** 9

    def on_hello(self, state):
        # One third of starting equity per tranche (integer quote units).
        self.tranche_units = int(state.hello["capital"]["quote_units"]) // len(TRANCHES_BPS)

    def rsi(self):
        """Simple 14-bar RSI over the last changes (50 when nothing moved)."""
        closes = self.closes
        if len(closes) <= RSI_BARS:
            return None
        gain = 0.0
        loss = 0.0
        for j in range(len(closes) - RSI_BARS, len(closes)):
            d = closes[j] - closes[j - 1]
            if d > 0:
                gain += d
            else:
                loss -= d
        moved = gain + loss
        return 50.0 if moved == 0 else 100.0 * gain / moved

    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        bars = [b for b in batch["bars"] if b["symbol"] == SYMBOL]
        if not bars:
            return []
        bar = bars[0]
        close = int(bar["c"]) / 10 ** 5  # price_scale 5 -> USD
        self.closes.append(close)
        closes = self.closes
        if len(closes) <= LOOKBACK_BARS:
            return []

        r60_bps = (close / closes[-LOOKBACK_BARS - 1] - 1.0) * 10000.0
        held = state.positions.get(SYMBOL)

        if held is not None and held.qty > 0:
            value = state.value(SYMBOL, held.qty)
            cost = held.cost
            pnl_bps = (value - cost) * 10000.0 / cost if cost > 0 else 0.0
            if close > self.peak:
                self.peak = close
            trail_hit = (
                self.peak > 0
                and (self.peak - close) / self.peak * 10000.0 >= TRAIL_BPS
            )
            held_too_long = (
                self.entry_seq is not None
                and state.seq - self.entry_seq >= MAX_HOLD_BARS
            )
            if pnl_bps >= TAKE_PROFIT_BPS or trail_hit or held_too_long:
                self.last_exit_seq = state.seq
                self.entry_seq = None
                self.n_bought = 0
                self.peak = 0.0
                return [
                    {
                        "side": "sell",
                        "symbol": SYMBOL,
                        "qty": held.qty,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                ]
            # Scale in deeper while the drop extends.
            if self.n_bought < len(TRANCHES_BPS) and r60_bps <= -TRANCHES_BPS[self.n_bought]:
                notional = min(self.tranche_units, state.cash)
                if notional >= 1_000_000:  # at least 1 USDC
                    self.n_bought += 1
                    return [
                        {
                            "side": "buy",
                            "symbol": SYMBOL,
                            "notional_quote_units": notional,
                            "max_slippage_bps": MAX_SLIPPAGE_BPS,
                        }
                    ]
            return []

        # Flat: enter on a deep 60-minute dislocation with RSI confirmation.
        rsi = self.rsi()
        if (
            r60_bps <= -TRANCHES_BPS[0]
            and (rsi is None or rsi < RSI_MAX)
            and state.seq - self.last_exit_seq >= COOLDOWN_BARS
        ):
            notional = min(self.tranche_units, state.cash)
            if notional < 1_000_000:
                return []
            self.entry_seq = state.seq
            self.n_bought = 1
            self.peak = close
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": notional,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []


BOT = Bot()


def main():
    makefun_bars.run(BOT.on_batch, on_hello=BOT.on_hello)


if __name__ == "__main__":
    main()
