# 🛡️ VTune GuardianAI

> **AI-Powered Pre-Push Code Guardian for Intel VTune Profiler**

VTune GuardianAI automatically analyzes your code changes for **bugs, memory leaks, security vulnerabilities, and coding standard violations** before you push to mainline. It can also **auto-fix Coverity defects** using AI-generated patches.

---

## Table of Contents

- [What It Catches](#what-it-catches)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Scan Mode (check)](#scan-mode-check)
  - [Fix Mode (fix)](#fix-mode-fix)
  - [Batch Fix from Coverity Export](#batch-fix-from-coverity-export)
  - [Report Formats](#report-formats)
- [Understanding the Output](#understanding-the-output)
- [Typical Workflow](#typical-workflow)
- [Project Structure](#project-structure)
- [Supported Languages](#supported-languages)
- [Configuration Reference](#configuration-reference)
- [Quick Reference](#quick-reference)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Changelog](#changelog)
- [License](#license)

---

## What It Catches

| Category | Examples |
|----------|----------|
| 🧠 **Memory Leaks** | malloc without free, dangling pointers, use-after-free, RAII violations |
| 🔒 **Security Vulnerabilities** | Hardcoded passwords, buffer overflows, command injection, path traversal |
| 🐛 **Logic Bugs** | Off-by-one errors, null pointer dereferences, race conditions, dead code |
| 📏 **Best Practice Violations** | Magic numbers, poor naming, missing error handling, iterator invalidation |
| 🏗️ **Build Issues** | SCons/Parts build file problems, missing dependencies |
| 🔬 **Static Analysis** | cppcheck and clang-tidy findings (when installed) |
| 🔄 **Coverity Defects** | RESOURCE_LEAK, NULL_RETURNS, UNINIT, USE_AFTER_FREE, and 28+ more |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLI (Typer + Rich)                     │
│    vtune-guardian check | fix | config-show | version    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  LangGraph Agent Pipeline                 │
│                                                          │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ Git Diff │→ │File Classifier│→ │Combined Analysis │  │
│  │(chunking)│  │               │  │(LLM per file)    │  │
│  └──────────┘  └───────────────┘  └──────────────────┘  │
│                                                          │
│  ┌────────────────┐  ┌──────────────────────────────┐   │
│  │Static Analysis │  │Security Patterns (regex)     │   │
│  │(cppcheck/tidy) │  │                              │   │
│  └────────────────┘  └──────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │Build Compatibility (SCons/Parts, LLM)            │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│               LLM Provider (Automatic Fallback)          │
│                                                          │
│  Option A: AWS Bedrock                                   │
│    Primary: Claude Sonnet 4 → Fallback: Claude 3.5 Haiku │
│                                                          │
│  Option B: GitHub Models                                 │
│    Chain: o3 → o3-mini → o4-mini → gpt-4.1-mini         │
└──────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| **OS** | Linux (Ubuntu 22.04+) | Tested on RHEL 8, Ubuntu 22/24 |
| **Python** | 3.10+ | `python3 --version` to check |
| **Git** | 2.x | Must be a git repository |
| **LLM Access** | One of the below: | |
| → AWS Bedrock (recommended) | — | ITS-approved, uses Claude via AIDE |
| → GitHub Models | — | Requires GitHub Copilot subscription |

**Optional (improves C/C++ results):**
- `cppcheck` — C/C++ static analyzer (`sudo apt install cppcheck`)
- `clang-tidy` — Clang static analyzer (`sudo apt install clang-tidy`)

---

## Installation

### Quick Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/ksanatan/vtune_guardianAI.git
cd vtune_guardianAI

# Run setup script (creates venv, installs deps, creates .env)
chmod +x setup.sh
./setup.sh

# Configure your LLM credentials (see next section)
nano .env
```

### Manual Setup

```bash
git clone https://github.com/ksanatan/vtune_guardianAI.git
cd vtune_guardianAI

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package in editable mode (with dev tools)
pip install -e ".[dev]"

# Create configuration file
cp .env.example .env
```

### Verify Installation

```bash
source .venv/bin/activate
vtune-guardian version
# Output: VTune GuardianAI v0.2.0
```

---

## Configuration

Copy `.env.example` to `.env` and set your credentials:

### Option A: AWS Bedrock / Claude (Recommended — ITS Approved)

This is the recommended provider for Intel internal use.

1. **Generate AIDE token:** Go to https://tokengen.aide.infra-host.com/
2. **Copy the bearer token** (starts with `ABSK...`)
3. **Edit `.env`:**

```bash
LLM_PROVIDER=bedrock
AWS_BEARER_TOKEN_BEDROCK=ABSK_your_token_here
AWS_REGION=us-east-2
```

> **Token expiry:** AIDE tokens last ~167 hours (~7 days). Regenerate when you see authentication errors.

### Option B: GitHub Models

1. **Create a PAT:** Go to https://github.com/settings/tokens
2. **Select scope:** `copilot`
3. **Edit `.env`:**

```bash
LLM_PROVIDER=github
GITHUB_TOKEN=ghp_your_token_here
```

**Advanced — Model Chain (optional):**
```bash
# Cascading fallback: when one model is rate-limited, advances to next
GITHUB_MODEL_CHAIN=o3,o3-mini,o4-mini,gpt-4.1-mini
```

### Proxy Configuration (Intel Network)

If you're behind the Intel corporate proxy:

```bash
export https_proxy=http://proxy-dmz.intel.com:912
export http_proxy=http://proxy-dmz.intel.com:912
export no_proxy=localhost,127.0.0.1,.intel.com
```

Add these to your `~/.bashrc` for persistence.

---

## Usage

**Always activate the virtual environment first:**

```bash
cd /path/to/vtune_guardianAI
source .venv/bin/activate
```

### Scan Mode (`check`)

Analyze code for issues before pushing:

```bash
# Scan all uncommitted changes in a specific repo
vtune-guardian check --repo /path/to/your/vtune/component --all

# Scan only staged changes (default — ideal for pre-push hook)
vtune-guardian check --repo /path/to/repo

# Scan current directory
cd /path/to/your/repo
vtune-guardian check --all

# Diff against a specific branch or commit
vtune-guardian check --repo /path/to/repo --base master
vtune-guardian check --repo /path/to/repo --base HEAD~5

# Scan specific files (full file analysis, not just diffs)
vtune-guardian check --repo /path/to/repo --files src/foo.cpp,src/bar.py

# Choose provider per-run
vtune-guardian check --all --provider bedrock
vtune-guardian check --all --provider github

# Skip static analysis (faster, LLM-only)
vtune-guardian check --all --no-static

# Only show critical issues
vtune-guardian check --all --severity critical

# Verbose mode (see node-level details)
vtune-guardian check --all -v
```

### Fix Mode (`fix`)

Auto-generate fixes for specific defects using AI:

```bash
# Fix a single defect (shows diff, does NOT modify files)
vtune-guardian fix --repo /path/to/repo \
    --file src/collector/data_collector.cpp \
    --line 142 \
    --issue "RESOURCE_LEAK"

# Fix and apply the change directly to the file
vtune-guardian fix --repo /path/to/repo \
    --file src/collector/data_collector.cpp \
    --line 142 \
    --issue "RESOURCE_LEAK" \
    --apply

# Fix using Coverity checker name (auto-maps to detailed description)
vtune-guardian fix --file src/utils.py --line 88 --issue NULL_RETURNS

# Fix using a free-text description
vtune-guardian fix --file src/parser.go --line 33 --issue "Use of uninitialized variable"
```

**Important:** Without `--apply`, the fix is only displayed — your files are NOT modified. Use `--apply` to write changes.

### Batch Fix from Coverity Export

Process entire Coverity CSV or JSON exports at once:

```bash
# Preview fixes for all defects in a Coverity CSV export (dry run)
vtune-guardian fix --from-csv coverity_export.csv --repo /path/to/repo

# Apply all fixes directly to files
vtune-guardian fix --from-csv coverity_export.csv --repo /path/to/repo --apply

# From cov-format-errors JSON output
vtune-guardian fix --from-json cov-errors.json --repo /path/to/repo --apply

# Only fix High severity defects
vtune-guardian fix --from-csv coverity_export.csv --severity High --apply

# Limit to 20 fixes (default max is 50)
vtune-guardian fix --from-csv coverity_export.csv --max-fixes 20 --apply
```

**How to export from Coverity Connect:**
1. Open Coverity Connect → navigate to your project
2. Go to **View Defects** → apply your filters
3. Click **Export** → choose **CSV**
4. Save the file and pass to `--from-csv`

**Expected CSV format (column names are flexible):**
```csv
CID,Checker,File,Line,Function,Severity,Status
10001,RESOURCE_LEAK,src/collector/data_collector.cpp,142,collectData,High,New
10002,NULL_RETURNS,src/analysis/perf_analyzer.py,88,analyze,Medium,New
10003,UNINIT,src/utils/helpers.go,33,parseConfig,Low,Triaged
```

**Supported Coverity Checkers (32+ mapped):**
`RESOURCE_LEAK`, `USE_AFTER_FREE`, `DOUBLE_FREE`, `OVERRUN`, `UNINIT`, `NULL_RETURNS`, `FORWARD_NULL`, `REVERSE_INULL`, `CHECKED_RETURN`, `LOCK`, `MISSING_LOCK`, `DATA_RACE`, `DEADCODE`, `CONSTANT_EXPRESSION_RESULT`, `COPY_PASTE_ERROR`, `INTEGER_OVERFLOW`, `TAINTED_SCALAR`, `TAINTED_STRING`, `SQL_INJECTION`, `HARDCODED_CREDENTIALS`, `CTOR_DTOR_LEAK`, `VIRTUAL_DTOR`, `INVALIDATE_ITERATOR`, and more.

### Report Formats

```bash
# Terminal output (default — colored, with code + fixes)
vtune-guardian check --all

# HTML report (dark theme, saved to ./reports/)
vtune-guardian check --all --report html

# JSON report (machine-readable, for CI/CD pipelines)
vtune-guardian check --all --report json
```

### Other Commands

```bash
# Show current configuration
vtune-guardian config-show

# Show version
vtune-guardian version
```

---

## Understanding the Output

### Gate Decisions

| Decision | Meaning | Action |
|----------|---------|--------|
| ✅ **ALL CLEAR** | No issues found | Safe to push |
| ⚠️ **PUSH WITH CAUTION** | Warnings found, no critical | Review warnings, then push |
| 🚫 **PUSH BLOCKED** | Critical issues found | Fix critical issues first |

### Issue Format

Each issue displays:
1. **Severity** — 🔴 Critical / 🟡 Warning / 🔵 Info
2. **The problematic code** — exact lines highlighted
3. **A suggested fix** — corrected code shown inline

### Fix Output Example

```
── Original ──
    FILE* fp = fopen(path, "r");
    process(fp);
    return result;

── Fixed ──
    FILE* fp = fopen(path, "r");
    if (!fp) return -1;
    process(fp);
    fclose(fp);
    return result;

Fix generated: Added null check for fopen return and fclose before return to fix resource leak.
```

---

## Typical Workflow

### Pre-Push Guard

```bash
# 1. Activate GuardianAI
cd /path/to/vtune_guardianAI && source .venv/bin/activate

# 2. Go to your component repo
cd /path/to/your/vtune/component

# 3. Make your code changes, stage them
git add <files>

# 4. Run the guardian
vtune-guardian check --all

# 5. Fix any critical issues, re-run to verify
vtune-guardian check --all

# 6. Push when clean
git push
```

### Coverity Remediation Workflow

```bash
# 1. Export defects from Coverity Connect (CSV)

# 2. Auto-fix all High-severity defects
vtune-guardian fix --from-csv coverity_export.csv --severity High --apply --repo /path/to/repo

# 3. Review the changes
cd /path/to/repo && git diff

# 4. Test, commit, push
git add -A
git commit -m "Fix Coverity defects (AI-assisted)"
git push
```

### Git Pre-Push Hook (Optional)

Add to `.git/hooks/pre-push`:

```bash
#!/bin/bash
source /path/to/vtune_guardianAI/.venv/bin/activate
vtune-guardian check --severity critical
exit $?
```

Make executable: `chmod +x .git/hooks/pre-push`

---

## Project Structure

```
vtune_guardianAI/
├── README.md                   # This file
├── CHANGELOG.md                # Version history
├── pyproject.toml              # Package config & dependencies
├── setup.sh                    # One-command setup script
├── .env.example                # Configuration template
├── .gitignore
│
├── guardian/                   # Main package
│   ├── __init__.py             # Version & app name
│   ├── cli.py                  # Typer CLI (check, fix, config-show, version)
│   ├── config.py               # Configuration management (.env loading)
│   │
│   ├── agents/                 # LangGraph agent orchestration
│   │   ├── graph.py            # Main agent graph definition & execution
│   │   └── state.py            # GuardianState, FileChange, Issue models
│   │
│   ├── llm/                    # LLM provider abstraction
│   │   └── provider.py         # Bedrock + GitHub Models with fallback chains
│   │
│   ├── nodes/                  # Analysis & fix pipeline nodes
│   │   ├── git_diff.py         # Git diff extraction (2000-line chunking)
│   │   ├── file_classifier.py  # Language/file type classification
│   │   ├── combined_analysis.py # LLM-powered combined analysis (memory+review+security+bestpractice)
│   │   ├── static_analysis.py  # cppcheck/clang-tidy integration
│   │   ├── security_check.py   # Regex-based security pattern scan
│   │   ├── build_compat.py     # Build system compatibility
│   │   ├── fix_issue.py        # AI defect auto-fix engine
│   │   └── coverity_parser.py  # Coverity CSV/JSON import & mapping
│   │
│   ├── reporters/              # Output formatting
│   │   ├── terminal.py         # Rich terminal output
│   │   ├── html_report.py      # HTML dark-theme report
│   │   └── json_report.py      # JSON for CI/CD
│   │
│   └── utils/                  # Shared utilities
│       └── helpers.py          # Source context reader, language detection
│
├── tests/                      # Test suite
│   └── test_nodes.py           # Node unit tests
│
└── reports/                    # Generated reports (gitignored)
```

---

## Supported Languages

| Language | Extensions | Static Analysis | Fix Support |
|----------|-----------|-----------------|-------------|
| C/C++ | `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`, `.hxx` | cppcheck + clang-tidy + LLM | ✅ |
| Python | `.py`, `.pyw` | LLM | ✅ |
| Java | `.java` | LLM | ✅ |
| Go | `.go` | LLM | ✅ |
| Rust | `.rs` | LLM | ✅ |
| JavaScript/TypeScript | `.js`, `.ts`, `.tsx` | LLM | ✅ |
| Ruby | `.rb` | LLM | ✅ |
| C# | `.cs` | LLM | ✅ |
| Swift | `.swift` | LLM | ✅ |
| Kotlin | `.kt` | LLM | ✅ |
| Scala | `.scala` | LLM | ✅ |
| Shell/Bash | `.sh`, `.bash`, `.zsh` | LLM | ✅ |
| SQL | `.sql` | LLM | ✅ |
| Build files | `SConstruct`, `CMakeLists.txt`, `Makefile`, `.parts` | LLM | ✅ |
| Config | `.yaml`, `.yml`, `.json`, `.xml` | LLM | ✅ |

---

## Configuration Reference

All settings are loaded from `.env` (or environment variables). CLI flags override `.env` values.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `bedrock` | LLM backend: `bedrock` or `github` |
| `AWS_BEARER_TOKEN_BEDROCK` | — | AIDE bearer token (starts with `ABSK...`) |
| `AWS_REGION` | `us-east-2` | AWS region for Bedrock API |
| `BEDROCK_MODEL` | `global.anthropic.claude-sonnet-4-20250514-v1:0` | Primary Bedrock model ID |
| `BEDROCK_FALLBACK_MODEL` | `us.anthropic.claude-3-5-haiku-20241022-v1:0` | Fallback model ID |
| `GITHUB_TOKEN` | — | GitHub PAT with `copilot` scope |
| `GITHUB_MODEL` | `o3` | Primary GitHub model |
| `GITHUB_FALLBACK_MODEL` | `o3-mini` | Fallback GitHub model |
| `GITHUB_MODEL_CHAIN` | — | Comma-separated model chain (overrides primary+fallback) |
| `GITHUB_BASE_URL` | `https://models.inference.ai.azure.com` | GitHub Models endpoint |
| `CPPCHECK_PATH` | `cppcheck` | Path to cppcheck binary |
| `CLANG_TIDY_PATH` | `clang-tidy` | Path to clang-tidy binary |
| `GUARDIAN_SEVERITY_THRESHOLD` | `warning` | Min severity: `critical`, `warning`, `info` |
| `GUARDIAN_MAX_FILES` | `50` | Max files to analyze per run |
| `GUARDIAN_REPORT_FORMAT` | `terminal` | Default output: `terminal`, `json`, `html` |

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `vtune-guardian check --all` | Scan all uncommitted changes |
| `vtune-guardian check --repo PATH --all` | Scan a specific repo |
| `vtune-guardian check --base master` | Diff against master branch |
| `vtune-guardian check --files a.cpp,b.py` | Scan specific files (full) |
| `vtune-guardian check --report html` | Generate HTML report |
| `vtune-guardian check --severity critical` | Critical issues only |
| `vtune-guardian check --no-static` | Skip cppcheck/clang-tidy |
| `vtune-guardian check --provider bedrock` | Use Bedrock for this run |
| `vtune-guardian check -v` | Verbose output |
| `vtune-guardian fix -f FILE -l LINE -i ISSUE` | Fix one defect (preview) |
| `vtune-guardian fix -f FILE -l LINE -i ISSUE --apply` | Fix and write |
| `vtune-guardian fix --from-csv FILE` | Batch fix from CSV (preview) |
| `vtune-guardian fix --from-csv FILE --apply` | Batch fix and write |
| `vtune-guardian fix --from-json FILE --apply` | Batch fix from JSON |
| `vtune-guardian fix --from-csv FILE --severity High` | Filter by severity |
| `vtune-guardian fix --from-csv FILE --max-fixes 20` | Limit batch size |
| `vtune-guardian config-show` | Show configuration |
| `vtune-guardian version` | Show version |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `"Not a git repository"` | Use `--repo /path/to/repo` pointing to a dir with `.git` |
| `"GITHUB_TOKEN is required"` | Set your PAT in `.env`: `GITHUB_TOKEN=ghp_...` |
| `"Bedrock authentication failed"` | Token expired — regenerate at https://tokengen.aide.infra-host.com/ |
| `"AWS_BEARER_TOKEN_BEDROCK is required"` | Set AIDE token in `.env` or export as env variable |
| Rate limit errors | Automatic — falls back to next model in chain |
| `"cppcheck not available"` | Optional. Install: `sudo apt install cppcheck clang-tidy` |
| Proxy/network issues | `export https_proxy=http://proxy-dmz.intel.com:912` |
| `"Could not find original code block"` | File changed since analysis — re-run fix |
| `"CANNOT_FIX: ..."` | LLM needs more context — fix manually |
| Import errors after setup | Run `pip install -e ".[dev]"` inside activated venv |
| `ModuleNotFoundError: guardian` | Activate venv first: `source .venv/bin/activate` |
| Slow first run | Model cold-start; subsequent runs are faster |
| HTML report not opening | Check `./reports/` directory for the generated file |

---

## Development

### Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

### Code Style

```bash
ruff check guardian/
ruff format guardian/
```

### Adding a New Analysis Node

1. Create `guardian/nodes/your_node.py` with a function accepting `GuardianState`
2. Register it in `guardian/agents/graph.py`
3. Add a toggle in `guardian/config.py` if it should be optional

### Key Dependencies

| Library | Purpose |
|---------|---------|
| LangGraph | Agent orchestration & state machine |
| LangChain | LLM abstraction layer |
| langchain-openai | GitHub Models (OpenAI-compatible API) |
| langchain-aws | AWS Bedrock (ChatBedrockConverse) |
| boto3 | AWS SDK for Bedrock auth |
| GitPython | Git repository operations |
| Typer | CLI framework |
| Rich | Terminal formatting & progress bars |
| Pydantic | Data validation & state models |
| python-dotenv | .env file loading |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## License

Intel Proprietary — Internal Use Only

---

*VTune GuardianAI v0.2.0 — Intel Performance Analysis Tools*
