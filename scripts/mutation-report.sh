#!/bin/bash
# Mutation Testing Report Generator
# Runs mutmut SILENTLY and generates a clean JSON/text report

set -e

WORKDIR=$(pwd)
REPORT_DIR="$WORKDIR/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$REPORT_DIR/mutation-log-$TIMESTAMP.log"
REPORT_JSON="$REPORT_DIR/mutation-report-$TIMESTAMP.json"
REPORT_TXT="$REPORT_DIR/mutation-report-$TIMESTAMP.txt"

mkdir -p "$REPORT_DIR"

# Clean previous results
rm -rf mutants/ .mutmut-cache 2>/dev/null || true

echo "Running mutation tests... (log: $LOG_FILE)"

# Run mutmut SILENTLY - all output to log file
uv run mutmut run --max-children=1 > "$LOG_FILE" 2>&1

# The output has all progress on one line with \r. Get the last status update.
# Pattern: ⠦ 5/5  🎉 5 🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0
# Extract using perl to handle the complex pattern

RESULT_LINE=$(cat "$LOG_FILE" | tr '\r' '\n' | grep "🎉" | tail -1)

if [ -z "$RESULT_LINE" ]; then
    echo "Error: Could not find mutation results in log"
    exit 1
fi

# Parse using perl for reliable extraction
TOTAL=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /(\d+)\/(\d+)/' | head -1)
KILLED=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /🎉\s*(\d+)/')
SURVIVED=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /🫥\s*(\d+)/')
TIMEOUT=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /⏰\s*(\d+)/')
SUSPICIOUS=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /🤔\s*(\d+)/')
SKIPPED=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /🙁\s*(\d+)/')
NO_COVERAGE=$(echo "$RESULT_LINE" | perl -ne 'print $1 if /🔇\s*(\d+)/')

# Get total from X/Y pattern (second number)
TOTAL=$(echo "$RESULT_LINE" | perl -ne 'print $2 if /(\d+)\/(\d+)/')

# Defaults
KILLED=${KILLED:-0}
SURVIVED=${SURVIVED:-0}
TIMEOUT=${TIMEOUT:-0}
SUSPICIOUS=${SUSPICIOUS:-0}
SKIPPED=${SKIPPED:-0}
NO_COVERAGE=${NO_COVERAGE:-0}
TOTAL=${TOTAL:-0}

# Calculate mutation score
if [ "$TOTAL" -gt 0 ]; then
    SCORE=$(echo "scale=1; $KILLED * 100 / $TOTAL" | bc)
else
    SCORE="0.0"
fi

# Get config
CONFIG_PATHS=$(grep 'paths_to_mutate' pyproject.toml 2>/dev/null | head -1 | sed 's/.*= //' | tr -d '[]"' || echo "N/A")
CONFIG_TESTS=$(grep 'pytest_add_cli_args_test_selection' pyproject.toml 2>/dev/null | head -1 | sed 's/.*= //' | tr -d '[]"' || echo "N/A")

# Generate JSON report
cat > "$REPORT_JSON" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "config": {
    "paths_to_mutate": "$CONFIG_PATHS",
    "test_files": "$CONFIG_TESTS"
  },
  "results": {
    "total_mutants": $TOTAL,
    "killed": $KILLED,
    "survived": $SURVIVED,
    "timeout": $TIMEOUT,
    "suspicious": $SUSPICIOUS,
    "skipped": $SKIPPED,
    "no_coverage": $NO_COVERAGE
  },
  "mutation_score": $SCORE
}
EOF

# Generate text report  
cat > "$REPORT_TXT" << EOF
================================================================================
                         MUTATION TESTING REPORT
================================================================================
Generated: $(date)

Configuration:
  Paths to mutate: $CONFIG_PATHS
  Test files:      $CONFIG_TESTS

Results:
  Total mutants:    $TOTAL
  Killed:           $KILLED  (good - tests detected mutation)
  Survived:         $SURVIVED  (bad - tests missed mutation)
  Timeout:          $TIMEOUT
  Suspicious:       $SUSPICIOUS
  Skipped:          $SKIPPED
  No coverage:      $NO_COVERAGE

================================================================================
  MUTATION SCORE: ${SCORE}%   (target: >80%)
================================================================================
EOF

# Show only the final report
cat "$REPORT_TXT"
echo ""
echo "JSON: $REPORT_JSON"
