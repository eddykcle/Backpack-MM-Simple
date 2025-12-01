#!/bin/bash
# Quick test verification script

echo "=== Test File Verification ==="
echo ""

echo "Checking test files exist..."
test_files=(
    "tests/test_daemon_manager.py"
    "tests/test_cli_commands.py"
    "tests/test_exceptions.py"
    "tests/test_strategies.py"
    "tests/test_web_server.py"
)

all_exist=true
for file in "${test_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ $file (missing)"
        all_exist=false
    fi
done

echo ""

if [ "$all_exist" = true ]; then
    echo "All test files present!"
    echo ""
    
    echo "=== Syntax Check ==="
    for file in "${test_files[@]}"; do
        if python3 -m py_compile "$file" 2>/dev/null; then
            echo "✓ $file syntax OK"
        else
            echo "✗ $file has syntax errors"
        fi
    done
    
    echo ""
    echo "=== Test Discovery ==="
    python3 -m unittest discover tests/ -v --dry-run 2>&1 | head -20
    
else
    echo "Some test files are missing!"
    exit 1
fi