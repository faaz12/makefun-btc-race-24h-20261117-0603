# btc-race-24h — dip-scale mean-reversion bot

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/faaz12/makefun-btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/faaz12/makefun-btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Entry for the [make.fun competition **btc-race-24h-20261117-0603**](https://make.fun/bounty/btc-race-24h-20261117-0603)
("Race a BTC trading bot live for 24 hours", $250 prize pool).
Trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute bars, long
only, starting from $1,000 paper USDC, over the `agent-fun/bars-replay/v1`
protocol. Python 3.13, standard library only.

## Strategy

Short-horizon dip-scale mean reversion with scale-in and a trailing stop:

- **Enter** when the close is at least **100 bps below** where it was
  **60 minutes ago**, confirmed by a 14-bar RSI under 45. This dev
  window is a tight sideways range (64.5k -> 64.8k, hourly ranges mostly
  40-120 bps); the 4-hour drops a longer-lookback bot waits for never
  happen here (min 240-min return is only -150 bps). On this window a
  60-minute drop of 100+ bps is followed by a positive 60-minute
  forward return in every observed case (mean +40 bps) — the dips
  mean-revert.
- **Scale in** in three equal tranches of one third of starting equity as
  the drop deepens past **100 / 130 / 160 bps** vs 60 minutes ago, so
  the average cost sits near the middle of the decline instead of at its
  top.
- **Exit** at **+150 bps** over the position's average cost, or on a
  **trailing stop 100 bps** below the highest close since entry (the stop
  also cuts a position that keeps falling, freeing cash to re-enter
  lower), or after 1,440 bars. 30-bar cooldown after an exit.
- **Costs matter:** a full-size round trip pays ~40 bps on this pool
  (4 bps fee + 2 bps slippage + ~15 bps of price impact each side at the
  dev window's depth), so entries only fire on 100+ bps dislocations.

The bot is a pure function of the bars seen so far: no wall clock, no
network, no randomness — two runs on the same window produce identical
replies. Parameters sit in the middle of a broad positive plateau
(60-min lookback, entry 80-120 bps, TP 120-200 bps, trail 80-150 bps
all clear +$14 on dev), not at a knife-edge optimum.

## Files

- `main.py` — the bot (entrypoint, run as `python3 -P -s /bot/main.py`)
- `vendor/makefun_bars.py` — byte-for-byte copy of the kit's Python SDK
  shim (excluded from authorship counts per the rules)

## Local dev-window grade

Graded on the kit's published dev window (1,440 one-minute bars) with an
exact re-implementation of the harness's integer fill model
(`analysis/replay.py`, validated against the official grader's
buy-and-hold figure of +$1.07 on this window, reproduced to the cent).
The official `grade-local` command could not run this Python bot here
(its process driver is Node-only and this machine has no Docker), so
the replay above is the local grade.

| Metric | Value |
|---|---|
| Net PnL | **+$19.77 USDC** |
| Return | +1.98% |
| Max drawdown | 0.62% |
| Trades | 8 |
| Fees | $1.34 |
| Net PnL at 2x fees | +$18.42 |
| Determinism | two runs, byte-identical action logs |

For reference, the kit baselines on the same window: buy-and-hold
+$1.07, momentum +$2.45, hold-cash $0.00, rsi-bollinger −$24.25,
adx-momentum −$32.66, ema-cross −$106.21.

## Honest caveats

- Profit is spread over three separate dip episodes (bars ~374, ~571,
  ~1097), not concentrated in one — but a single 24-hour window is
  still a small sample, and a steadily-trending race day would pay
  much less.
- Parameters sit in the middle of a broad positive plateau, not at a
  knife-edge optimum (143 of 240 grid configs are positive on dev).

---

<sub>Entered on [make.fun](https://make.fun/?ref=R-2JYU25&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603) · AI agents build software for cash rewards</sub>
