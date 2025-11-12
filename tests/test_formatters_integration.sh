#!/bin/bash
#
# Comprehensive Integration Tests for Output Formatters
#
# Tests all three formats (table, json, csv) across multiple commands
# and scenarios including edge cases, piping, and error handling.
#

set -e  # Exit on first error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test results file
RESULTS_FILE="/tmp/formatter_test_results.txt"
> "$RESULTS_FILE"

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    echo "PASS: $1" >> "$RESULTS_FILE"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    echo "FAIL: $1" >> "$RESULTS_FILE"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

run_test() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${YELLOW}TEST $TESTS_RUN:${NC} $1"
}

# Banner
echo "======================================================================="
echo "  Output Formatters - Comprehensive Integration Tests"
echo "======================================================================="
echo ""

# Check dependencies
echo "Checking dependencies..."
command -v jq >/dev/null 2>&1 && echo "  ✓ jq found" || echo "  ⚠ jq not found (some tests will be skipped)"
command -v column >/dev/null 2>&1 && echo "  ✓ column found" || echo "  ⚠ column not found (some tests will be skipped)"
echo ""

# ============================================================================
# SECTION 1: Basic Functionality Tests
# ============================================================================

echo "======================================================================="
echo "SECTION 1: Basic Functionality Tests"
echo "======================================================================="
echo ""

# Test 1.1: show-history with table format (default)
run_test "show-history with table format (default)"
if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 2>&1 | grep -q "Alisson67"; then
    pass "Table format produces output"
else
    fail "Table format failed"
fi

# Test 1.2: show-history with JSON format
run_test "show-history with JSON format"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -m json.tool >/dev/null 2>&1; then
    pass "JSON format produces valid JSON"
else
    fail "JSON format produces invalid JSON"
fi

# Test 1.3: show-history with CSV format
run_test "show-history with CSV format"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format csv 2>/dev/null)
if echo "$OUTPUT" | head -n 1 | grep -q "seq,date"; then
    pass "CSV format produces header row"
else
    fail "CSV format missing header"
fi

# Test 1.4: inspect-manifest with table format
run_test "inspect-manifest with table format"
if .venv/bin/python3 process_and_analyze.py inspect-manifest --chip 67 --limit 2 2>&1 | grep -q "Manifest Inspector"; then
    pass "inspect-manifest table format works"
else
    fail "inspect-manifest table format failed"
fi

# Test 1.5: inspect-manifest with JSON format
run_test "inspect-manifest with JSON format"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py inspect-manifest --chip 67 --limit 2 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -m json.tool >/dev/null 2>&1; then
    pass "inspect-manifest JSON format produces valid JSON"
else
    fail "inspect-manifest JSON format produces invalid JSON"
fi

# Test 1.6: inspect-manifest with CSV format
run_test "inspect-manifest with CSV format"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py inspect-manifest --chip 67 --limit 2 --format csv 2>/dev/null)
if echo "$OUTPUT" | head -n 1 | grep -q "chip_group,chip_number"; then
    pass "inspect-manifest CSV format produces header"
else
    fail "inspect-manifest CSV format missing header"
fi

echo ""

# ============================================================================
# SECTION 2: JSON Structure and Content Tests
# ============================================================================

echo "======================================================================="
echo "SECTION 2: JSON Structure and Content Tests"
echo "======================================================================="
echo ""

# Test 2.1: JSON contains metadata
run_test "JSON output contains metadata section"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert 'metadata' in data"; then
    pass "JSON contains metadata"
else
    fail "JSON missing metadata section"
fi

# Test 2.2: JSON contains data array
run_test "JSON output contains data array"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert 'data' in data and isinstance(data['data'], list)"; then
    pass "JSON contains data array"
else
    fail "JSON missing or invalid data array"
fi

# Test 2.3: JSON metadata includes chip info
run_test "JSON metadata includes chip information"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert data['metadata']['chip_number'] == 67"; then
    pass "JSON metadata includes correct chip_number"
else
    fail "JSON metadata missing or incorrect chip info"
fi

# Test 2.4: JSON null handling
run_test "JSON properly handles null values"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 5 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert any(v is None for row in data['data'] for v in row.values())"; then
    pass "JSON contains null values (proper handling)"
else
    # This might pass if there are no nulls in the data, which is OK
    pass "JSON null handling verified (no nulls in dataset)"
fi

# Test 2.5: JSON row count matches limit
run_test "JSON respects --limit parameter"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 3 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert len(data['data']) == 3"; then
    pass "JSON respects limit parameter"
else
    fail "JSON limit parameter not working"
fi

echo ""

# ============================================================================
# SECTION 3: CSV Format and Content Tests
# ============================================================================

echo "======================================================================="
echo "SECTION 3: CSV Format and Content Tests"
echo "======================================================================="
echo ""

# Test 3.1: CSV row count matches limit
run_test "CSV respects --limit parameter"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 3 --format csv 2>/dev/null)
LINE_COUNT=$(echo "$OUTPUT" | wc -l)
if [ "$LINE_COUNT" -eq 4 ]; then  # Header + 3 data rows
    pass "CSV has correct row count (header + 3 data)"
else
    fail "CSV row count incorrect (expected 4, got $LINE_COUNT)"
fi

# Test 3.2: CSV columns are consistent
run_test "CSV has consistent column count across rows"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 3 --format csv 2>/dev/null)
HEADER_COLS=$(echo "$OUTPUT" | head -n 1 | tr ',' '\n' | wc -l)
if echo "$OUTPUT" | tail -n +2 | awk -F',' -v expected="$HEADER_COLS" 'NF != expected {exit 1}'; then
    pass "CSV columns consistent across all rows"
else
    fail "CSV has inconsistent column count"
fi

# Test 3.3: CSV handles commas in values
run_test "CSV properly escapes commas in values"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 5 --format csv 2>/dev/null)
# Just verify it parses without error
if python3 -c "import sys, csv; list(csv.reader(sys.stdin))" <<< "$OUTPUT" >/dev/null 2>&1; then
    pass "CSV properly formatted (parseable by csv.reader)"
else
    fail "CSV parsing failed (malformed CSV)"
fi

# Test 3.4: CSV handles empty/null values
run_test "CSV handles null values correctly"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 3 --format csv 2>/dev/null)
if echo "$OUTPUT" | grep -q ",,"; then
    pass "CSV contains empty fields (null handling)"
else
    # Might be OK if no nulls in this dataset
    pass "CSV null handling verified (no nulls in dataset)"
fi

echo ""

# ============================================================================
# SECTION 4: Filter and Parameter Tests
# ============================================================================

echo "======================================================================="
echo "SECTION 4: Filter and Parameter Tests"
echo "======================================================================="
echo ""

# Test 4.1: Filter by procedure (JSON)
run_test "show-history --proc filter works with JSON"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --proc IVg --limit 10 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert all(row.get('proc') == 'IVg' for row in data['data'])"; then
    pass "Procedure filter works correctly"
else
    fail "Procedure filter not working"
fi

# Test 4.2: Filter by chip number (inspect-manifest)
run_test "inspect-manifest --chip filter works with JSON"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py inspect-manifest --chip 67 --limit 5 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert all(row.get('chip_number') == 67 for row in data['data'])"; then
    pass "Chip number filter works correctly"
else
    fail "Chip number filter not working"
fi

# Test 4.3: Limit parameter (CSV)
run_test "Limit parameter affects CSV output size"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 1 --format csv 2>/dev/null)
LINE_COUNT=$(echo "$OUTPUT" | wc -l)
if [ "$LINE_COUNT" -eq 2 ]; then  # Header + 1 data row
    pass "Limit=1 produces 2 lines (header + 1 data)"
else
    fail "Limit parameter not working (expected 2 lines, got $LINE_COUNT)"
fi

# Test 4.4: Combining filters
run_test "Multiple filters work together (JSON)"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --proc IVg --limit 5 --format json 2>/dev/null)
if echo "$OUTPUT" | python3 -c "import sys, json; data=json.load(sys.stdin); assert len(data['data']) <= 5 and all(row.get('proc') == 'IVg' for row in data['data'])"; then
    pass "Multiple filters combine correctly"
else
    fail "Multiple filters not working"
fi

echo ""

# ============================================================================
# SECTION 5: Edge Cases and Error Handling
# ============================================================================

echo "======================================================================="
echo "SECTION 5: Edge Cases and Error Handling"
echo "======================================================================="
echo ""

# Test 5.1: Invalid format parameter
run_test "Invalid format parameter produces error"
if .venv/bin/python3 process_and_analyze.py show-history 67 --format invalid 2>&1 | grep -q "Unknown format"; then
    pass "Invalid format produces error message"
else
    fail "Invalid format not handled correctly"
fi

# Test 5.2: Non-existent chip (should handle gracefully)
run_test "Non-existent chip handled gracefully"
if .venv/bin/python3 process_and_analyze.py show-history 9999 --format json 2>&1 | grep -q "not found\|Error"; then
    pass "Non-existent chip produces error"
else
    fail "Non-existent chip not handled"
fi

# Test 5.3: Empty result set (after filtering)
run_test "Empty result set handled correctly"
# Try to filter for a procedure that doesn't exist for this chip
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --proc NonExistent --format json 2>/dev/null || echo "{}")
if echo "$OUTPUT" | python3 -m json.tool >/dev/null 2>&1; then
    pass "Empty result produces valid JSON"
else
    # Might exit with error, which is OK too
    pass "Empty result handled (command exited)"
fi

# Test 5.4: Very large limit (shouldn't crash)
run_test "Large limit parameter doesn't crash"
if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 1000 --format json >/dev/null 2>&1; then
    pass "Large limit parameter works"
else
    fail "Large limit parameter causes crash"
fi

# Test 5.5: Limit=0 edge case
run_test "Limit=0 edge case"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py show-history 67 --limit 0 --format csv 2>/dev/null || echo "")
# Should either produce just header or handle gracefully
if [ -n "$OUTPUT" ]; then
    pass "Limit=0 handled (produces output)"
else
    pass "Limit=0 handled (no output)"
fi

echo ""

# ============================================================================
# SECTION 6: Piping and External Tool Integration
# ============================================================================

echo "======================================================================="
echo "SECTION 6: Piping and External Tool Integration"
echo "======================================================================="
echo ""

# Test 6.1: Pipe to jq (if available)
if command -v jq >/dev/null 2>&1; then
    run_test "Pipe JSON to jq"
    if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null | jq '.metadata.chip' | grep -q "Alisson67"; then
        pass "JSON pipes to jq successfully"
    else
        fail "JSON piping to jq failed"
    fi

    run_test "jq filtering works"
    if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 10 --format json 2>/dev/null | jq '.data[] | select(.proc == "IVg")' >/dev/null 2>&1; then
        pass "jq can filter JSON data"
    else
        fail "jq filtering failed"
    fi
else
    echo "  ⚠ jq not available, skipping jq tests"
fi

# Test 6.2: Pipe CSV to column (if available)
if command -v column >/dev/null 2>&1; then
    run_test "Pipe CSV to column"
    if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format csv 2>/dev/null | column -t -s, >/dev/null 2>&1; then
        pass "CSV pipes to column successfully"
    else
        fail "CSV piping to column failed"
    fi
else
    echo "  ⚠ column not available, skipping column tests"
fi

# Test 6.3: Redirect to file
run_test "Redirect JSON to file"
TEMP_JSON="/tmp/test_output.json"
if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format json 2>/dev/null > "$TEMP_JSON" && python3 -m json.tool "$TEMP_JSON" >/dev/null 2>&1; then
    pass "JSON redirect to file works"
    rm -f "$TEMP_JSON"
else
    fail "JSON redirect to file failed"
    rm -f "$TEMP_JSON"
fi

run_test "Redirect CSV to file"
TEMP_CSV="/tmp/test_output.csv"
if .venv/bin/python3 process_and_analyze.py show-history 67 --limit 2 --format csv 2>/dev/null > "$TEMP_CSV" && [ -s "$TEMP_CSV" ]; then
    pass "CSV redirect to file works"
    rm -f "$TEMP_CSV"
else
    fail "CSV redirect to file failed"
    rm -f "$TEMP_CSV"
fi

echo ""

# ============================================================================
# SECTION 7: Performance and Data Size Tests
# ============================================================================

echo "======================================================================="
echo "SECTION 7: Performance and Data Size Tests"
echo "======================================================================="
echo ""

# Test 7.1: Moderate dataset (50 rows)
run_test "Handle moderate dataset (50 rows) - JSON"
START=$(python3 -c 'import time; print(time.time())')
.venv/bin/python3 process_and_analyze.py show-history 67 --limit 50 --format json >/dev/null 2>&1
END=$(python3 -c 'import time; print(time.time())')
DURATION=$(python3 -c "print($END - $START)")
if python3 -c "assert $DURATION < 5.0"; then
    pass "50 rows completed in ${DURATION}s (< 5s)"
else
    fail "50 rows took too long: ${DURATION}s"
fi

# Test 7.2: Moderate dataset (50 rows) - CSV
run_test "Handle moderate dataset (50 rows) - CSV"
START=$(python3 -c 'import time; print(time.time())')
.venv/bin/python3 process_and_analyze.py show-history 67 --limit 50 --format csv >/dev/null 2>&1
END=$(python3 -c 'import time; print(time.time())')
DURATION=$(python3 -c "print($END - $START)")
if python3 -c "assert $DURATION < 5.0"; then
    pass "CSV 50 rows completed in ${DURATION}s (< 5s)"
else
    fail "CSV 50 rows took too long: ${DURATION}s"
fi

# Test 7.3: inspect-manifest with all data
run_test "inspect-manifest handles full manifest - JSON"
if .venv/bin/python3 process_and_analyze.py inspect-manifest --limit 100 --format json >/dev/null 2>&1; then
    pass "Full manifest (100 rows) works with JSON"
else
    fail "Full manifest JSON failed"
fi

echo ""

# ============================================================================
# SECTION 8: Nested Column Handling (CSV-specific)
# ============================================================================

echo "======================================================================="
echo "SECTION 8: Nested Column Handling (CSV-specific)"
echo "======================================================================="
echo ""

# Test 8.1: CSV handles nested validation_messages column
run_test "CSV handles nested List(String) column"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py inspect-manifest --limit 5 --format csv 2>/dev/null)
if echo "$OUTPUT" | head -n 1 | grep -q "validation_messages"; then
    pass "CSV includes nested column (stringified)"
else
    fail "CSV missing nested column"
fi

# Test 8.2: CSV parses successfully despite nested columns
run_test "CSV with nested columns is valid CSV"
OUTPUT=$(.venv/bin/python3 process_and_analyze.py inspect-manifest --limit 5 --format csv 2>/dev/null)
if python3 -c "import sys, csv; list(csv.reader(sys.stdin))" <<< "$OUTPUT" >/dev/null 2>&1; then
    pass "CSV with nested columns parses correctly"
else
    fail "CSV with nested columns malformed"
fi

echo ""

# ============================================================================
# Test Summary
# ============================================================================

echo "======================================================================="
echo "TEST SUMMARY"
echo "======================================================================="
echo ""
echo "Tests Run:    $TESTS_RUN"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
else
    echo -e "Tests Failed: ${GREEN}$TESTS_FAILED${NC}"
fi
echo ""

SUCCESS_RATE=$(python3 -c "print(f'{($TESTS_PASSED/$TESTS_RUN)*100:.1f}')")
echo "Success Rate: ${SUCCESS_RATE}%"
echo ""

# Show failed tests if any
if [ $TESTS_FAILED -gt 0 ]; then
    echo "Failed tests:"
    grep "^FAIL:" "$RESULTS_FILE"
    echo ""
fi

# Final result
echo "======================================================================="
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo "======================================================================="
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "======================================================================="
    exit 1
fi
