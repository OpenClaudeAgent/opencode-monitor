#!/bin/bash
# Test Quality Audit Script
# Usage: ./scripts/test-audit.sh [test_file]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Test Quality Audit ===${NC}"
echo ""

if [ -n "$1" ]; then
    FILES="$1"
else
    FILES="tests/test_*.py"
fi

echo -e "${YELLOW}Analyzing: $FILES${NC}"
echo ""

# Header
printf "%-45s %8s %8s %8s %8s\n" "FILE" "LINES" "TESTS" "ASSERTS" "RATIO"
printf "%-45s %8s %8s %8s %8s\n" "----" "-----" "-----" "-------" "-----"

total_lines=0
total_tests=0
total_asserts=0

for f in $FILES; do
    if [ -f "$f" ]; then
        lines=$(wc -l < "$f")
        tests=$(grep -c "def test_" "$f" 2>/dev/null || echo 0)
        asserts=$(grep -c "^\s*assert" "$f" 2>/dev/null || echo 0)
        
        if [ "$tests" -gt 0 ]; then
            ratio=$(echo "scale=1; $asserts / $tests" | bc)
        else
            ratio="N/A"
        fi
        
        # Color based on ratio
        if [ "$ratio" != "N/A" ]; then
            if (( $(echo "$ratio < 2.0" | bc -l) )); then
                color=$RED
            elif (( $(echo "$ratio < 4.0" | bc -l) )); then
                color=$YELLOW
            else
                color=$GREEN
            fi
        else
            color=$NC
        fi
        
        basename=$(basename "$f")
        printf "%-45s %8d %8d %8d ${color}%8s${NC}\n" "$basename" "$lines" "$tests" "$asserts" "$ratio"
        
        total_lines=$((total_lines + lines))
        total_tests=$((total_tests + tests))
        total_asserts=$((total_asserts + asserts))
    fi
done

echo ""
printf "%-45s %8s %8s %8s %8s\n" "----" "-----" "-----" "-------" "-----"

if [ "$total_tests" -gt 0 ]; then
    total_ratio=$(echo "scale=1; $total_asserts / $total_tests" | bc)
else
    total_ratio="N/A"
fi

printf "%-45s %8d %8d %8d %8s\n" "TOTAL" "$total_lines" "$total_tests" "$total_asserts" "$total_ratio"

echo ""
echo -e "${BLUE}=== Legend ===${NC}"
echo -e "${RED}RED${NC}    : Ratio < 2.0 (needs improvement)"
echo -e "${YELLOW}YELLOW${NC} : Ratio 2.0-4.0 (acceptable)"
echo -e "${GREEN}GREEN${NC}  : Ratio >= 4.0 (good)"
echo ""

# Source code stats
src_lines=$(find src -name "*.py" -type f | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
test_ratio=$(echo "scale=2; $total_lines / $src_lines" | bc)

echo -e "${BLUE}=== Overall Metrics ===${NC}"
echo "Source lines:     $src_lines"
echo "Test lines:       $total_lines"
echo -e "Ratio test/code:  ${YELLOW}$test_ratio${NC} (target: < 0.8)"
