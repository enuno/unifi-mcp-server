#!/bin/bash
# run_validation_tests.sh

echo "========================================="
echo "FastMCP Skill Validation Test Suite"
echo "========================================="
echo ""

# Test 1: Check file exists
echo "Test 1: Skill file exists"
if [ -f "skills/fastmcp/SKILL.md" ]; then
  echo "✅ PASS: SKILL.md exists"
else
  echo "❌ FAIL: SKILL.md not found"
  exit 1
fi

# Test 2: Check frontmatter
echo ""
echo "Test 2: Frontmatter validation"
if head -5 skills/fastmcp/SKILL.md | grep -q "^---$"; then
  echo "✅ PASS: Frontmatter present"
else
  echo "❌ FAIL: Frontmatter missing or malformed"
  exit 1
fi

# Test 3: Check required block
echo ""
echo "Test 3: Required block validation"
if grep -q "<required>" skills/fastmcp/SKILL.md; then
  echo "✅ PASS: <required> block present"
else
  echo "❌ FAIL: <required> block missing"
  exit 1
fi

# Test 4: Check for key sections
echo ""
echo "Test 4: Key sections present"
SECTIONS=("Quick Start" "Core Concepts" "Tools" "Resources" "Prompts" "Context" "Claude Desktop Integration" "Authentication" "Common Pitfalls" "Deployment")

for section in "${SECTIONS[@]}"; do
  if grep -qi "$section" skills/fastmcp/SKILL.md; then
    echo "  ✅ $section"
  else
    echo "  ❌ Missing: $section"
  fi
done

# Test 5: Check for Python examples
echo ""
echo "Test 5: Python examples present"
if grep -q '```python' skills/fastmcp/SKILL.md; then
  COUNT=$(grep -c '```python' skills/fastmcp/SKILL.md)
  echo "✅ PASS: $COUNT Python examples found"
else
  echo "❌ FAIL: No Python examples"
  exit 1
fi

# Test 6: Check for TypeScript examples
echo ""
echo "Test 6: TypeScript examples present"
if grep -q '```typescript' skills/fastmcp/SKILL.md; then
  COUNT=$(grep -c '```typescript' skills/fastmcp/SKILL.md)
  echo "✅ PASS: $COUNT TypeScript examples found"
else
  echo "❌ FAIL: No TypeScript examples"
  exit 1
fi

# Test 7: Check word count (should be substantial)
echo ""
echo "Test 7: Content length validation"
WORDS=$(wc -w < skills/fastmcp/SKILL.md)
if [ "$WORDS" -gt 3000 ]; then
  echo "✅ PASS: $WORDS words (substantial content)"
else
  echo "❌ FAIL: Only $WORDS words (needs more content)"
  exit 1
fi

echo ""
echo "========================================="
echo "All validation tests passed! ✅"
echo "========================================="
