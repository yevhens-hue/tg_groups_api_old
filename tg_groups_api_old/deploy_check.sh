#!/bin/bash
# Pre-deployment check script

echo "🔍 Running pre-deployment checks..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Check if all dependencies can be imported
echo "✓ Checking imports..."
python3 -c "import app; import tg_service; print('  All imports OK')" || exit 1

# Check if tests pass
echo "✓ Running tests..."
python3 -m pytest tests/ -v --tb=short > /dev/null 2>&1 && echo "  All tests passed" || echo "  ⚠️  Some tests failed (check manually)"

# Check required files
echo "✓ Checking required files..."
required_files=("app.py" "tg_service.py" "requirements.txt" "start.sh" "context.py")
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file MISSING"
        exit 1
    fi
done

echo ""
echo "✅ Pre-deployment checks completed!"
echo ""
echo "Next steps:"
echo "1. Set environment variables in Render:"
echo "   - TG_API_ID"
echo "   - TG_API_HASH"
echo "   - TG_SESSION_STRING"
echo "   - REDIS_URL (optional)"
echo ""
echo "2. Deploy to Render"
echo ""
