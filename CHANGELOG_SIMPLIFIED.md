# Version 2.0.0 — September 20, 2026
## What's new?
- **Web app**: the whole app now runs in the browser on a phone or a computer, not just as a desktop app. You can import players, generate sessions, edit rounds, view charts, and download results directly from the web interface.
- **Safer, portable session files**: web sessions are saved as `.json` files instead of pickle files, so they can be reopened on another device and are safer to handle on a public server.
- **Railway deployment support**: the repo now includes the server, frontend build, Docker setup, and deployment docs needed to host the app online.
- **Better balanced rounds**: the optimisation now really compares whole rounds. Sessions come out happier and more even.
- **Clearer spectrum profiles**: the spec types were reworked so their behavior is more consistent and easier to understand.
## Bug fixes
- The level noise in level rounds now actually mixes players close to a level boundary.
- Forcing preferred pairs no longer leaves the happiness of later rounds out of date.
- The Excel summary now matches the players' happiness right after generation, and teams are in the same order as on screen.
- Names starting with an accented capital letter no longer break the session games image.

## Important differences
- In the web app, players, settings, and recent sessions stay in your browser until you reset or export them.
- The desktop app can still load pickle sessions, but the web app only accepts JSON session files.


# Version 1.7.0
## What's new?
- **AI Quick Reference** — a new `docs/AI_REFERENCE.md` document gives a quick lookup of data model attributes, function locations, and common task recipes for contributors and AI tools.
- **Bug replay script** — `scripts/replay_bug.py` makes it easy to reproduce a reported bug by setting up the right environment and launching the app straight to the failing state.
- **Bug reporter** — a new tool (`ui/functions/bug_reporter.py`) packages up logs, preferences, and session data into a report to make bug investigations faster.
- **Model helper tests** — added tests covering `compute_session_score`, `reorder_rounds`, `GameOfFour`, and `TeamOfTwo`.

# Version 1.6.0 — May 14, 2026
## What's new?
- **Load an old session** — a new 📂 Load Session button on the main screen lets you pick any `.pkl` file from a past session. The Games Editor, Session Games view, and plots all open exactly as they would after generating a new session.
- **No more overwriting on Apply** — each time you apply changes in the Games Editor, a new numbered snapshot is saved (`_v1`, `_v2`, …) instead of overwriting a single file. The original generated session is always preserved.
- **Restore previous state from score history** — the score history strip in the Games Editor now shows clickable chips for every past state. Click an earlier chip to jump back to that version of the session.
- **Extra parameters picked up live** — changes to `extra_parameters_temp.json` (seed range, iteration count, penalties…) are now read fresh on every generation, so you no longer need to restart the app after editing that file.
- **Archive extra parameters on close** — when you quit, if the temp extra-parameters file differs from the saved one, a dialog offers to archive it as a dated backup (`extra_parameters_temp_DD_MM_YYYY.json`) so you can reuse it later.

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
