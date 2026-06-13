# AI-Assisted Development Process — RoundnetMatchmaking

Attach or paste this file at the start of any GitHub Copilot conversation.
The AI applies every step automatically. Only `ASK USER:` items require a response.

---

## Step 1 — Classify the change

Identify which bucket(s) the request touches. A single change can span multiple.

- **core** — `core/` (algorithm.py, models.py, charts.py, data_loader.py, fine_tuning_functions.py, pickle_helper.py, main.py)
- **ui-tab** — `ui/tabs/` (one Mixin per tab)
- **ui-infra** — `ui/functions/` or `ui/main/` (orchestrator, helpers, build script)
- **prefs** — `ui/functions/preferences_manager.py` or `ui/user_preferences/*.json`
- **tests** — `tests/`
- **build-ci** — `.github/workflows/`, `ui/main/build_exe.py`, `pyproject.toml`
- **docs-only** — `docs/`, `README.md`, changelogs, `DEV_PROCESS.md`

---

## Step 2 — Documentation

Apply automatically based on bucket. Only ask when flagged.

| Trigger | Action |
|---|---|
| Any functional change | `ASK USER: Should this change be added to CHANGELOG.md and CHANGELOG_SIMPLIFIED.md?` |
| User-facing behaviour changes (new feature, changed flow) | Flag `README.md` for update |
| New tab, new Mixin, structural UI refactor | Flag `docs/UI_STRUCTURE.md` for update |
| New or renamed preference key | Flag `docs/PREFERENCES_PERSISTENCE.md` for update |
| Core algorithm logic change | Flag `docs/ITERATIONS_IMPLEMENTATION.md` for update |
| Build script or CI workflow change | Flag `docs/BUILD_INSTRUCTIONS.md` for update |
| New call-flow function or data model change | `ASK USER: Should the session creation diagram be updated? (edit session_diagram_registry.json, then run: python docs/diagrams/session_creation/generate_session_diagram.py)` |
| New reusable pattern, recipe, or public function signature | Flag `docs/AI_REFERENCE.md` for update |

### Documentation file reference

| File | Purpose |
|---|---|
| `README.md` | User-facing quick start and troubleshooting |
| `CHANGELOG.md` | Developer-detail changelog (Keep-a-Changelog format) |
| `CHANGELOG_SIMPLIFIED.md` | User-friendly version notes |
| `CONTRIBUTING.md` | Contributor setup and PR guide — update only for process changes |
| `docs/UI_STRUCTURE.md` | UI architecture and module layout |
| `docs/PREFERENCES_PERSISTENCE.md` | Preference system: keys, lifecycle, how to add parameters |
| `docs/ITERATIONS_IMPLEMENTATION.md` | Algorithm logic, scoring layers, iteration budget |
| `docs/BUILD_INSTRUCTIONS.md` | Build, CI, and release workflow |
| `docs/diagrams/session_creation/session_diagram_registry.json` | Source of truth for the session creation diagram — edit this, not the generated `.md` |
| `docs/AI_REFERENCE.md` | AI quick-reference: data model attributes, function index, common task recipes |

---

## Step 3 — Architecture rules

Enforce these patterns. Reject or rework changes that violate them.

### New UI tab
- Create a new Mixin in `ui/tabs/`
- Add it to the `PlayerSelectionUI` inheritance list in `ui/main/roundnet_matchmaking_ui.py`
- Register it in `ui/main/build_exe.py` under `FILES_TO_COPY`

### New auto-saved preference (silently persists on every UI change)
Five-step chain, all in `ui/functions/preferences_manager.py` and the relevant tab Mixin:
1. Add key to `UI_DEFAULT_SAVED_KEYS`
2. Add default to `_UI_DEFAULTS`
3. Read widget value in `_collect_ui_default_saved()`
4. Restore in `_apply_ui_preferences()`
5. Wire trace in `_load_and_apply_preferences()`: `var.trace_add("write", self._on_auto_save_change)`

### New opt-in preference (user confirms at close)
Four-step chain:
1. Add key to `UI_DEFAULT_NOT_SAVED_KEYS`
2. Add human-readable label to `UI_DEFAULT_NOT_SAVED_LABELS`
3. Add default to `_UI_DEFAULTS`
4. Read in `_collect_ui_all_tracked()` and restore in `_apply_ui_preferences()`

### Core module loading
Always use `load_module()` from `ui/functions/ui_helpers.py`. Never use a direct import of a `core/` module from UI code.

### Shared helpers placement
- Cross-cutting runtime infrastructure (module loading, icons, console redirect) → `ui/functions/ui_helpers.py`
- Tab-domain workflow helpers (round priorities, happiness colours, plot discovery) → `ui/functions/tab_functions.py`

### Session diagram
Any new call-flow function node or data model entity: edit `session_diagram_registry.json`, then regenerate:
```
python docs/diagrams/session_creation/generate_session_diagram.py
```
Never edit `SESSION_CREATION_DIAGRAM.md` by hand — it is generated.

---

## Step 4 — Risk assessment

Flag the tier before implementing.

| Tier | Files / areas |
|---|---|
| 🔴 High | `_on_app_close` and temp file cleanup · `load_module` hot-reload · pickle serialize/deserialize (`pickle_helper.py`) · `SessionOfRounds` / `GamesRound` class structure |
| 🟡 Medium | Splash/loading flow · tab orchestration (`PlayerSelectionUI.__init__`) · xlsx parsing (`data_loader.py`, `setup_wizard.py`) · preference lifecycle (load, trace, save, cleanup) |
| 🟢 Low | UI cosmetics · label text · color constants · console print output |

For 🔴 changes: state the risk explicitly before writing any code.

---

## Step 5 — Backwards compatibility

Check all four surfaces. Act automatically where possible; ask when the impact requires a decision.

### 1. Pickle session files (`.pkl`)
Existing session files on disk are `SessionOfRounds` pickles. Any change to the attributes of
`SessionOfRounds`, `GamesRound`, `GameOfFour`, `TeamOfTwo`, or `Player` can corrupt deserialization of old files.

- **Safe**: adding a new attribute — always read it with `getattr(obj, 'attr', default)` on load
- **Breaking**: renaming or removing an attribute

If a class attribute is renamed or removed:
`ASK USER: This changes a pickled class attribute — existing .pkl session files may fail to load. Do you want a stamp-on-load guard or a __setstate__ migration?`

Established pattern (use it): stamp missing attributes on load:
```python
if not getattr(session, '_new_attr', None):
    session._new_attr = default_value
```

### 2. Preference JSON files
`_read_json()` uses `_deep_merge(defaults, overrides)`, so:
- **Safe**: adding a new key (defaults fill in for missing keys), removing a key
- **Breaking**: renaming a key — the old file has the old key, new code reads a different key and silently falls back to the default, losing the user's saved value

If a preference key is renamed:
`ASK USER: This renames a saved preference key — existing user files will silently revert to the default for this parameter. Do you want a migration reader added to _read_json()?`

Note: `schema_version = 1` exists in both JSON files but no migration logic is implemented yet.

### 3. Entry points
Do not remove or rename without a deprecation notice:
- `roundnet-matchmaking` CLI command (defined in `pyproject.toml`)
- `ui.main.player_selection_ui` legacy wrapper (forwards to `roundnet_matchmaking_ui.main`)

### 4. `xlsx_config.json`
Any change to the structure this file is parsed with in `setup_wizard.py` requires users to re-run the setup wizard. Flag this explicitly in the PR description and changelog.

---

## Step 6 — Testing

`ASK USER: to run both suites after any non-docs change:`
```
python tests/run_script_tests.py
pytest -q
```
Make sure the Testing scripts are not altered by the modification

### Script-based suite (`run_script_tests.py`)
Covers: `test_iterations.py`, `test_post_processing.py`, `test_pickle.py`, `test_session_diagram_sync.py`

### Manual verification required when touching
- Splash/loading window or startup flow
- App close dialog (`_on_app_close`, `_UnsavedPrefsDialog`, `_ask_save_extra_params`)
- Pickle round-trip (save → reload a session in the UI)
- Setup wizard (delete `xlsx/xlsx_config.json` and relaunch)

---

## Step 7 — Versioning & release

### Version bump
Update `pyproject.toml` → `version = "X.Y.Z"` on every release.

> ⚠️ Known drift: `pyproject.toml` is currently at `1.3.0` but `CHANGELOG.md` is at `1.6.0`. On the next release, align both.

`ASK USER: Confirm the new version number for pyproject.toml, CHANGELOG.md, and CHANGELOG_SIMPLIFIED.md.`

### Changelog format
- `CHANGELOG.md`: Keep-a-Changelog format with `### Added / Changed / Removed / Bug fixes` subsections and date
- `CHANGELOG_SIMPLIFIED.md`: Plain user-facing summary, no subsections

### Release workflow
```
git tag vX.Y.Z
git push origin vX.Y.Z
```
This triggers `.github/workflows/build.yml` which builds and publishes four platform artifacts automatically (Windows, macOS arm64, macOS x86, Linux).

---

## Step 8 — Git hygiene

- Use imperative commit messages: `Add X`, `Fix Y`, `Remove Z`, not `Added` or `Fixes`
- Reference issue numbers when relevant: `Fix preferred-pair swap (#42)`
- Suggest a new branch when the change is large, risky (🔴), or experimental
- Check if `.gitignore` file should be updated

---

## Step 9 — DEV_PROCESS.md self-update check

After every change, verify whether any fact encoded in this file is now stale.

| If the change touches... | Check this section |
|---|---|
| Test file list, test directory, test runner command | Step 6 — Testing |
| A new or renamed doc file | Step 2 — Documentation table |
| A new architectural pattern or convention | Step 3 — Architecture rules |
| A new high-risk file or area | Step 4 — Risk tiers |
| A new persistent file format | Step 5 — Backwards compatibility surfaces |
| CI workflow, new release platform, tag format | Step 7 — Versioning & release |

If any section is stale:
`ASK USER: Section X in DEV_PROCESS.md appears outdated by this change — should I update it?`
