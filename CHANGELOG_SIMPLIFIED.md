
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
