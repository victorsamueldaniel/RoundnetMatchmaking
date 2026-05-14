
# Version 1.6.0 — May 14, 2026
## What's new?
- **Load an old session** — a new 📂 Load Session button on the main screen lets you pick any `.pkl` file from a past session. The Games Editor, Session Games view, and plots all open exactly as they would after generating a new session.
- **No more overwriting on Apply** — each time you apply changes in the Games Editor, a new numbered snapshot is saved (`_v1`, `_v2`, …) instead of overwriting a single file. The original generated session is always preserved.
- **Restore previous state from score history** — the score history strip in the Games Editor now shows clickable chips for every past state. Click an earlier chip to jump back to that version of the session.

# Version 1.5.0 — May 10, 2026
## What's new?
- In level-based games, players near a level boundary will occasionally be sorted into a different group, adding more variety across rounds.
- The app now remembers your settings between sessions. Most parameters (number of rounds, games per round, level gap, lambda, percentile, spectrum, and per-round type/gender preferences) are saved automatically as you change them. Player selection, female level shift, and preferred pairs are saved only if you choose to — a dialog appears on close listing each changed parameter so you can decide what to keep.
## Bug fixes
- Fixed round type/gender preferences resetting to defaults when clicking `+` or `−` on the number of rounds.

# Version 1.4.0 — May 8, 2026
## What's new?
- Added a contact page tab.
- Games Editor now highlights over-benched players live during pending swaps (black background, white text, SAD! label on all matching Not Playing buttons).
- Preferred pair selection now supports picking 3 or 4 players.
- Preferred pair algorithm overhauled: now searches the best swap across all possible rounds and pairs globally, instead of greedy per-round search. Happiness weights adjust based on the number of games (e.g. 4 games → `[+12,+10, +8, +8]` of happiness for each match).
- "Show level on PNG" button moved to Session Games tab and now applies changes dynamically.
## Bug fixes
- Fixed quantile thresholds (now correctly ≤33%, >33% to ≤66%, >66%).

# version 1.3.0 — May 5, 2026
## What's new?
- Mac OS Intel and ARM executable, Unix executable.
## BUG FIXES
- Changed alphabetical ordering, so accented letters come before the next one (Like "Aliénor" would come before "Alissa") in players frame
- Spinbox of player level in player edit dialog used to be capped at 4, it is now capped at 10'000
- removed display bug on session png when level is selected
# Version 1.2.0 — April 25, 2026
## What's new ?
### Reorder rounds after generating a session
You can now rearrange rounds after a session is generated. Each round appears as its own tile in the Session Games tab — click one round, then click another to swap them. When you're happy with the order, hit **Apply Changes** to lock it in.

### See happiness impact before committing a swap
In the Games Editor, player buttons now turn **green** or **red** while you're moving players around, showing whether that swap would improve or hurt their happiness — before you apply anything.

### New slider: "Bottom x% size"
A new slider lets you control how many of the lowest-happiness players the algorithm focuses on when optimising a session. A lower value means it zeroes in on only the very unhappiest players; a higher value gives more weight to a larger group.

### Cleaner round images
Each round image now fits a portrait-style layout, making sessions easier to read when shared as a screenshot or printed.

## BUG FIXES
### happiness computation
Happiness Computation is now correctly done, especially on first swap in games editor. The pair preferences work now better with happiness computation fixed

---

# Version 1.1.0 — April 21, 2026

- First public release.
