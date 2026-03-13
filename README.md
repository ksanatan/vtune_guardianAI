# 🛡️ VTune GuardianAI

> **AI-Powered Pre-Push Code Guardian for Intel VTune Profiler**

VTune GuardianAI automatically analyzes your code changes for **bugs, memory leaks, security vulnerabilities, and coding standard violations** before you push to mainline.

For every issue found, it shows you the **problematic code** and a **suggested fix**.

---

## What It Catches

- 🧠 **Memory Leaks** — malloc without free, dangling pointers, use-after-free
- 🔒 **Security Vulnerabilities** — hardcoded passwords, buffer overflows, command injection
- 🐛 **Logic Bugs** — off-by-one errors, null pointer dereferences, race conditions
- 📏 **Best Practice Violations** — magic numbers, poor naming, missing error handling
- 🏗️ **Build Issues** — SCons/Parts build file problems
- 🔬 **Static Analysis** — cppcheck and clang-tidy findings (when installed)

---

## Architecture

```
vtune-guardian check --repo /path/to/repo --all
        │
        ▼
    git_diff (-U30 context) → file_classifier
        │
    ┌───┼───────┬──────────────┐
    ▼   ▼       ▼              ▼
 static combined  security   build
 analysis  AI     patterns   compat
 (cppcheck (LLM)  (regex)    (LLM)
  clang-   │
  tidy)    │
    └───┬──┴───────┬──────────┘
        ▼          ▼
     aggregator → decision → report
                  (block/warn/pass)
```

**Model Chain**: When a model is rate-limited, GuardianAI automatically advances
to the next model in the chain and retries. Results from previous models are kept.

```
o3 (best) → o4-mini → o3-mini → gpt-4.1-mini
 ~15 calls    ~15       ~15        ~15  = ~60 calls/day
```

---

## Prerequisites

- **Linux** (tested on Ubuntu 22.04)
- **Python 3.10+**
- **Git**
- **GitHub Copilot subscription** (for the AI analysis — free tier works)
- **cppcheck** (optional): `sudo apt install cppcheck`
- **clang-tidy** (optional): `sudo apt install clang-tidy`

---

## Setup (One Time)

```bash
# 1. Go to the project directory
cd VTune_guardianAI

# 2. Run the setup script
chmod +x setup.sh
./setup.sh

# 3. Create a GitHub Personal Access Token (PAT)
#    → Go to: https://github.com/settings/tokens
#    → Click "Generate new token (classic)"
#    → Select scope: copilot
#    → Copy the token

# 4. Paste your token into .env
#    Open .env and set:
GITHUB_TOKEN=ghp_your_token_here
```

That's it. You're ready to go.

---

## How to Use

**Every time you open a new terminal:**

```bash
cd VTune_guardianAI
source .venv/bin/activate
```

### Basic Usage

```bash
# Scan all uncommitted changes in a repo
vtune-guardian check --repo /path/to/your/vtune/component --all

# Scan only staged changes
vtune-guardian check --repo /path/to/your/repo

# Scan current directory
cd /path/to/your/repo
vtune-guardian check --all
```

### Report Formats

```bash
# Terminal output (default — colored, with code + fixes)
vtune-guardian check --repo /path/to/repo --all

# HTML report (dark theme, opens in browser)
vtune-guardian check --repo /path/to/repo --all --report html

# JSON report (for CI/CD integration)
vtune-guardian check --repo /path/to/repo --all --report json
```

### Other Options

```bash
# Only show critical issues
vtune-guardian check --all --severity critical

# Skip static analysis (cppcheck/clang-tidy)
vtune-guardian check --all --no-static

# Verbose mode (see node-level details)
vtune-guardian check --all -v

# Show current configuration
vtune-guardian config-show

# Check version
vtune-guardian version
```

---

## Understanding the Output

| Decision | What It Means | What to Do |
|----------|--------------|------------|
| ✅ **ALL CLEAR** | No issues found | Safe to push |
| ⚠️ **PUSH WITH CAUTION** | Warnings found, no critical | Review warnings, then push |
| 🚫 **PUSH BLOCKED** | Critical issues found | Fix critical issues before pushing |

Each issue shows:
1. **Severity** — 🔴 Critical / 🟡 Warning / 🔵 Info
2. **The problematic code** with the exact line highlighted
3. **A suggested fix** with corrected code

---

## Typical Workflow

```bash
# 1. Activate GuardianAI
cd VTune_guardianAI && source .venv/bin/activate

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

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `vtune-guardian check --all` | Scan all uncommitted changes |
| `vtune-guardian check --repo PATH --all` | Scan a specific repo |
| `vtune-guardian check --report html` | HTML report |
| `vtune-guardian check --severity critical` | Critical only |
| `vtune-guardian check --no-static` | Skip cppcheck/clang-tidy |
| `vtune-guardian check -v` | Verbose output |
| `vtune-guardian config-show` | Show config |
| `vtune-guardian version` | Show version |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Not a git repository" | Use `--repo /path/to/repo` pointing to a directory with `.git` |
| "GITHUB_TOKEN is required" | Set your token in `.env`: `GITHUB_TOKEN=ghp_...` |
| Rate limit errors | Automatic — model chain cycles through o3 → o4-mini → o3-mini → gpt-4.1-mini |
| "cppcheck not available" | Install: `sudo apt install cppcheck` |
| "clang-tidy not available" | Install: `sudo apt install clang-tidy` |
| Proxy issues | `export https_proxy=http://proxy-dmz.intel.com:912` |

---

## 📄 License

Intel Proprietary — Internal Use Only

*VTune GuardianAI v0.1.0 — Intel Performance Analysis Tools*
