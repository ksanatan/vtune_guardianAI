#!/bin/bash
# ============================================
# VTune GuardianAI - One-Command Setup Script
# ============================================

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════╗"
echo "║       VTune GuardianAI - Setup Script        ║"
echo "║   AI-Powered Pre-Push Code Guardian          ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python version
echo -e "${YELLOW}[1/5]${NC} Checking Python version..."
PYTHON_CMD=""
if command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}Error: Python 3.10+ is required but not found.${NC}"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "  Found ${GREEN}$PYTHON_CMD ($PYTHON_VERSION)${NC}"

# Create virtual environment
echo -e "${YELLOW}[2/5]${NC} Creating virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    echo -e "  ${GREEN}Virtual environment created${NC}"
else
    echo -e "  ${GREEN}Virtual environment already exists${NC}"
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo -e "${YELLOW}[3/5]${NC} Installing dependencies..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo -e "  ${GREEN}Dependencies installed${NC}"

# Setup .env file
echo -e "${YELLOW}[4/5]${NC} Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}.env file created from template${NC}"
else
    echo -e "  ${GREEN}.env file already exists${NC}"
fi

# Check for optional tools
echo -e "${YELLOW}[5/5]${NC} Checking optional tools..."
if command -v cppcheck &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} cppcheck found"
else
    echo -e "  ${YELLOW}⚠${NC} cppcheck not found (install with: sudo apt install cppcheck)"
fi

if command -v clang-tidy &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} clang-tidy found"
else
    echo -e "  ${YELLOW}⚠${NC} clang-tidy not found (install with: sudo apt install clang-tidy)"
fi

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║       Setup Complete! 🚀                     ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "    source .venv/bin/activate"
echo -e "    vtune-guardian check --all              # Scan all uncommitted changes"
echo -e "    vtune-guardian check --repo /path/to/repo --all"
echo -e "    vtune-guardian fix --file f.cpp --line 42 --issue RESOURCE_LEAK"
echo -e "    vtune-guardian fix --from-csv coverity.csv --apply"
echo ""
echo -e "  ${BOLD}Configuration:${NC}"
echo -e "    Edit .env and set your credentials:"
echo -e "      Bedrock (recommended): AWS_BEARER_TOKEN_BEDROCK=ABSK_..."
echo -e "      GitHub Models:          GITHUB_TOKEN=ghp_..."
echo ""
echo -e "  ${BOLD}Documentation:${NC}"
echo -e "    See README.md for full usage guide."
echo ""
