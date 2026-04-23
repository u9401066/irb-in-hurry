#!/usr/bin/env bash
# IRB Submission Dashboard
# Usage: ./dashboard.sh [config.yml]

set -euo pipefail

CONFIG="${1:-config.yml}"
OUTPUT_DIR="output"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Extract values from config using python
# Use uv run if available, fallback to python3
if command -v uv &>/dev/null && [ -f "pyproject.toml" ]; then
    PY="uv run python"
elif command -v python3 &>/dev/null; then
    PY="python3"
else
    echo "⚠ python3 not found"
    exit 1
fi

if [ -f "$CONFIG" ]; then
    eval "$($PY -c "
import yaml
with open('$CONFIG') as f:
    c = yaml.safe_load(f)

harness = c.get('harness', {}) or {}
phases = harness.get('phases', [])

print(f'IRB_NO=\"{c[\"study\"][\"irb_no\"]}\"')
print(f'PHASE=\"{c.get(\"phase\", \"\")}\"')
print(f'TITLE=\"{c[\"study\"][\"title_zh\"][:40]}\"')
print(f'PI=\"{c[\"pi\"][\"name\"]}\"')
print(f'STUDY_TYPE=\"{c[\"study\"][\"type\"]}\"')
print(f'REVIEW_TYPE=\"{c[\"study\"].get(\"review_type\", \"\")}\"')
print(f'INSTITUTION=\"{c.get(\"institution\", \"kmuh\")}\"')
print(f'HARNESS_PHASES=\"{\",\".join(phases)}\"')
" 2>/dev/null)" || {
    echo "⚠ Could not parse $CONFIG"
    exit 1
}
else
    echo "⚠ python3 or $CONFIG not found"
    exit 1
fi

case "$INSTITUTION" in
    kmuh|KMUH)
        DASH_TITLE="KMUH 人體試驗委員會 IRB Submission Dashboard"
        ;;
    kfsyscc|KFSYSCC|*)
        DASH_TITLE="KFSYSCC IRB Submission Dashboard"
        ;;
esac

declare -A PHASE_NAMES=(
    [new]="新案審查" [amendment]="修正案審查" [re_review]="複審案審查"
    [continuing]="期中審查" [closure]="結案審查" [sae]="嚴重不良反應"
    [ib_update]="主持人手冊" [import]="專案進口" [suspension]="計畫暫停"
    [appeal]="申覆案"
)
PHASE_ZH="${PHASE_NAMES[$PHASE]:-$PHASE}"

DOCX_COUNT=$(find "$OUTPUT_DIR" -type f -name "*.docx" 2>/dev/null | wc -l | tr -d ' ')
PDF_COUNT=$(find "$OUTPUT_DIR" -type f -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
PNG_COUNT=$(find "$OUTPUT_DIR" -type f -path "*/preview/*.png" 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║${NC}     ${CYAN}${DASH_TITLE}${NC}${BOLD}          ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} IRB No:     ${GREEN}${IRB_NO}${NC}"
echo -e "${BOLD}║${NC} Phase:      ${CYAN}${PHASE_ZH}${NC} (${PHASE})"
echo -e "${BOLD}║${NC} PI:         ${PI}"
echo -e "${BOLD}║${NC} Study Type: ${STUDY_TYPE} / ${REVIEW_TYPE}"
echo -e "${BOLD}║${NC} Institution: ${INSTITUTION}"
echo -e "${BOLD}║${NC} Title:      ${TITLE}..."
if [ -n "${HARNESS_PHASES}" ]; then
    echo -e "${BOLD}║${NC} Harness:    ${HARNESS_PHASES//,/ -> }"
fi
echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} ${GREEN}■${NC} DOCX files: ${DOCX_COUNT}"
echo -e "${BOLD}║${NC} ${GREEN}■${NC} PDF files:  ${PDF_COUNT}"
echo -e "${BOLD}║${NC} ${GREEN}■${NC} Previews:   ${PNG_COUNT}"
echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"

CHECKLIST_PATH=""
if [ -n "$PHASE" ] && [ -f "$OUTPUT_DIR/$PHASE/checklist.md" ]; then
    CHECKLIST_PATH="$OUTPUT_DIR/$PHASE/checklist.md"
elif [ -f "$OUTPUT_DIR/checklist.md" ]; then
    CHECKLIST_PATH="$OUTPUT_DIR/checklist.md"
else
    CHECKLIST_PATH="$(find "$OUTPUT_DIR" -type f -name "checklist.md" 2>/dev/null | head -n 1 || true)"
fi

if [ -n "$CHECKLIST_PATH" ]; then
    DONE=$(grep -c '^■' "$CHECKLIST_PATH" 2>/dev/null || echo 0)
    TODO=$(grep -c '^□' "$CHECKLIST_PATH" 2>/dev/null || echo 0)
    TOTAL=$((DONE + TODO))

    if [ "$TODO" -eq 0 ] && [ "$DONE" -gt 0 ]; then
        echo -e "${BOLD}║${NC} Checklist:  ${GREEN}${DONE}/${TOTAL} complete ✓${NC}"
    elif [ "$TODO" -gt 0 ]; then
        echo -e "${BOLD}║${NC} Checklist:  ${YELLOW}${DONE}/${TOTAL} complete (${TODO} pending)${NC}"
    fi
    echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"

    # Show pending items
    if [ "$TODO" -gt 0 ]; then
        echo -e "${BOLD}║${NC} ${YELLOW}Pending:${NC}"
        grep '^□' "$CHECKLIST_PATH" | while read -r line; do
            echo -e "${BOLD}║${NC}   ${RED}${line}${NC}"
        done
        echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"
    fi
else
    echo -e "${BOLD}║${NC} ${RED}□ No checklist found. Run generate first${NC}"
    echo -e "${BOLD}╠══════════════════════════════════════════════╣${NC}"
fi

# Output files (including nested phase folders)
if [ "$DOCX_COUNT" -gt 0 ]; then
    echo -e "${BOLD}║${NC} ${CYAN}Output Files:${NC}"
    while IFS= read -r -d '' DOCX_FILE; do
        SIZE=$(du -h "$DOCX_FILE" 2>/dev/null | cut -f1 | tr -d ' ')
        BASENAME=$(basename "$DOCX_FILE")
        PDF_FILE="${DOCX_FILE%.docx}.pdf"
        if [ -f "$PDF_FILE" ]; then
            echo -e "${BOLD}║${NC}   ${GREEN}■${NC} ${BASENAME} (${SIZE}) ${GREEN}✓ PDF${NC}"
        else
            echo -e "${BOLD}║${NC}   ${YELLOW}■${NC} ${BASENAME} (${SIZE}) ${RED}□ PDF${NC}"
        fi
    done < <(find "$OUTPUT_DIR" -type f -name "*.docx" -print0 | sort -z)
fi

echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
