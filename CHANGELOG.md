# Changelog

All notable changes to VTune GuardianAI will be documented in this file.

## [0.2.0] - 2026-05-28

### Added
- **`vtune-guardian fix` command** — AI-powered auto-fix for individual defects
  - Single-fix mode: `--file`, `--line`, `--issue`
  - Batch mode from Coverity CSV: `--from-csv`
  - Batch mode from Coverity JSON: `--from-json`
  - `--apply` flag to write changes (safe dry-run by default)
  - `--severity` filter and `--max-fixes` cap for batch operations
  - Rich progress bar for batch processing
- **Coverity CSV/JSON parser** (`guardian/nodes/coverity_parser.py`)
  - Parses Coverity Connect CSV exports (flexible column names, BOM-aware)
  - Parses `cov-format-errors --json-output-v8` format
  - 32+ Coverity checker-to-description mappings
- **Fix engine** (`guardian/nodes/fix_issue.py`)
  - Reads ±30 lines of context around a defect
  - Sends structured prompt to LLM for minimal fix generation
  - Parses ORIGINAL/FIXED/EXPLANATION response blocks
  - Safe apply with exact string matching + whitespace-normalized fallback
  - CANNOT_FIX detection for defects requiring more context
- **Large file chunking** in `git_diff.py`
  - 2000-line chunks with 50-line overlap for cross-boundary coverage
  - Files over 2000 lines split into multiple analysis passes
- **AWS Bedrock (Claude) provider** restored alongside GitHub Models
  - AIDE bearer token → AWS credential decoding
  - Primary + fallback model support
  - Can be selected via `LLM_PROVIDER=bedrock` or `--provider bedrock`
- **`--provider`, `--files`, `--base` flags** to `check` command
- **Comprehensive README** with end-to-end user guide
- **CHANGELOG.md**

### Changed
- Version bumped to 0.2.0
- `config.py` supports dual providers (bedrock + github)
- `provider.py` routes based on `LLM_PROVIDER` setting
- `.env.example` updated with both provider configurations

## [0.1.1] - 2026-05-20

### Changed
- Model chain fallback (o3 → o3-mini → o4-mini → gpt-4.1-mini)
- Removed legacy analysis nodes (merged into combined_analysis)
- Updated defaults to o3/o3-mini
- -U30 diff context, 25K char limit per file

## [0.1.0] - 2026-05-15

### Added
- Initial release
- `vtune-guardian check` command with full analysis pipeline
- LangGraph-based multi-node agent (optimized 4-node parallel fan-out)
- GitHub Models integration (o4-mini with GPT-4o fallback)
- Automatic fallback between primary and backup models
- Static analysis integration (cppcheck, clang-tidy)
- Terminal, HTML, and JSON report formats
- Git pre-push gate (BLOCKED / CAUTION / CLEAR)
- `config-show` and `version` commands
- Setup script for one-command installation
- `.env`-based configuration

---

*VTune GuardianAI — Intel Performance Analysis Tools*
