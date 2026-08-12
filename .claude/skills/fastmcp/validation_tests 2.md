# FastMCP Skill Validation Tests

This file defines acceptance criteria for the FastMCP skill. All tests must pass before the skill is considered complete.

## Test 1: Skill Activation Test

**Purpose**: Verify the skill activates when users request FastMCP development tasks

**Test Method**: Manual verification with test phrases

**Test Cases**:
```bash
# Test phrase 1: "Create an MCP server"
# Expected: Skill loads and presents checklist

# Test phrase 2: "Build a FastMCP tool"
# Expected: Skill loads and presents checklist

# Test phrase 3: "Add resources to my MCP server"
# Expected: Skill loads and presents checklist

# Test phrase 4: "Help me integrate FastMCP with Claude Desktop"
# Expected: Skill loads and presents checklist
```

**Success Criteria**:
- [ ] Skill description clearly indicates activation for MCP/FastMCP tasks
- [ ] Activation triggers are documented in skill frontmatter or description
- [ ] Checklist appears when skill is loaded

**Status**: ❌ FAIL (skill not yet created)

---

## Test 2: Completeness Test

**Purpose**: Verify all critical FastMCP concepts are covered

**Test Method**: Check for required sections in SKILL.md

**Required Sections**:
- [ ] Frontmatter with name, description
- [ ] `<required>` block with checklist
- [ ] When to Use This Skill
- [ ] Quick Start (minimal example)
- [ ] Core Concepts:
  - [ ] Tools (Python + TypeScript examples)
  - [ ] Resources (Python + TypeScript examples)
  - [ ] Prompts (Python + TypeScript examples)
  - [ ] Context (Python + TypeScript examples)
- [ ] Claude Desktop Integration
- [ ] Authentication and Security
- [ ] Advanced Patterns
- [ ] Common Pitfalls
- [ ] Deployment
- [ ] FastMCP v3 Beta Features
- [ ] Integration with Creating-Skills Workflow
- [ ] Complete Examples (Python + TypeScript)
- [ ] Templates
- [ ] References
- [ ] Version Compatibility

**Success Criteria**:
- [ ] All required sections present
- [ ] Each section has meaningful content (>100 words)
- [ ] No placeholder text like "TODO" or "Coming soon"

**Status**: ❌ FAIL (skill not yet created)

---

## Test 3: Example Validation Test

**Purpose**: Verify code examples are syntactically correct and follow best practices

**Test Method**: Extract code blocks and validate syntax

**Test Cases**:

### Python Examples
```bash
# Extract all Python code blocks
grep -A 50 '```python' skills/fastmcp/SKILL.md | sed '/```$/Q' > /tmp/python_examples.py

# Validate Python syntax
python3 -m py_compile /tmp/python_examples.py
# Expected: No syntax errors
```

### TypeScript Examples
```bash
# Extract all TypeScript code blocks
grep -A 50 '```typescript' skills/fastmcp/SKILL.md | sed '/```$/Q' > /tmp/typescript_examples.ts

# Validate TypeScript syntax (requires tsc)
tsc --noEmit /tmp/typescript_examples.ts
# Expected: No syntax errors
```

**Success Criteria**:
- [ ] All Python examples are syntactically valid
- [ ] All TypeScript examples are syntactically valid
- [ ] Examples include type hints (Python) or type annotations (TypeScript)
- [ ] Examples include error handling where appropriate
- [ ] Examples follow FastMCP best practices

**Status**: ❌ FAIL (skill not yet created)

---

## Test 4: Integration with Creating-Skills Workflow

**Purpose**: Verify the skill follows Nori skill creation patterns

**Test Method**: Compare structure with existing skills

**Comparison Checklist**:
```bash
# Check frontmatter format
head -5 skills/fastmcp/SKILL.md
# Expected: YAML frontmatter with ---, name:, description:

# Check for <required> block
grep -A 10 '<required>' skills/fastmcp/SKILL.md
# Expected: <required> block with TodoWrite checklist

# Compare with builder-role-skill structure
diff -y --suppress-common-lines \
  <(grep '^#' /home/elvis/.claude/skills/builder-role-skill/SKILL.md) \
  <(grep '^#' skills/fastmcp/SKILL.md)
# Expected: Similar heading structure
```

**Success Criteria**:
- [ ] Frontmatter matches pattern: `---\nname: ...\ndescription: ...\n---`
- [ ] Has `<required>` block with checklist
- [ ] Checklist items use TodoWrite format
- [ ] Structure similar to other role-based skills
- [ ] Uses consistent terminology (skill vs ability)

**Status**: ❌ FAIL (skill not yet created)

---

## Test 5: Progressive Disclosure Test

**Purpose**: Verify information is organized from beginner to advanced

**Test Method**: Read through skill linearly and check flow

**Flow Checklist**:
- [ ] Quick Start appears before Advanced Patterns
- [ ] Core Concepts appear before Advanced Patterns
- [ ] Examples progress from simple to complex
- [ ] Basic deployment (STDIO) before advanced (HTTP/SSE)
- [ ] v2 stable content before v3 beta content
- [ ] Common pitfalls mentioned early, detailed later
- [ ] Advanced patterns clearly marked as optional

**Success Criteria**:
- [ ] Can understand skill by reading top-to-bottom
- [ ] No forward references to undefined concepts
- [ ] Complexity increases gradually
- [ ] Optional/advanced sections clearly marked

**Status**: ❌ FAIL (skill not yet created)

---

## Test 6: Basic Tool Creation (Integration Test)

**Purpose**: Invoke skill via Claude to create a simple MCP tool

**Test Method**: Run Claude with specific prompt and verify output

**Test Command**:
```bash
# This would be run via Claude CLI or API
# Simulating: User asks Claude to create an MCP tool
echo "Create an MCP server with a tool that adds two numbers" | claude-code-cli
```

**Expected Behavior**:
1. Skill detects MCP/tool creation request
2. Skill loads and presents checklist
3. Skill provides Python example with @mcp.tool decorator
4. Skill provides TypeScript example with equivalent implementation
5. Examples include type hints/annotations
6. Examples are syntactically valid

**Verification**:
```bash
# Manual verification checklist
- [ ] Skill loaded automatically
- [ ] Checklist presented to user
- [ ] Python example provided
- [ ] TypeScript example provided
- [ ] Examples are complete and runnable
- [ ] Examples include error handling
```

**Status**: ❌ FAIL (skill not yet created)

---

## Test 7: Resource Creation (Integration Test)

**Purpose**: Invoke skill to add a resource to existing server

**Test Method**: Run Claude with resource request

**Test Command**:
```bash
echo "Add a resource to my MCP server that reads files" | claude-code-cli
```

**Expected Behavior**:
1. Skill provides URI template pattern guidance
2. Skill shows security validation example
3. Skill provides Python AND TypeScript examples
4. Examples include path validation
5. Examples include error handling

**Verification**:
- [ ] URI template pattern explained
- [ ] Security validation emphasized
- [ ] Python example with path validation
- [ ] TypeScript example with path validation
- [ ] ResourceError handling shown

**Status**: ❌ FAIL (skill not yet created)

---

## Test 8: Claude Desktop Integration (Integration Test)

**Purpose**: Invoke skill for Claude Desktop integration help

**Test Method**: Run Claude with integration question

**Test Command**:
```bash
echo "How do I integrate my MCP server with Claude Desktop?" | claude-code-cli
```

**Expected Behavior**:
1. Skill provides fastmcp CLI installation command
2. Skill provides manual config JSON example
3. Skill explains environment variable handling
4. Skill provides verification steps (hammer icon check)

**Verification**:
- [ ] fastmcp CLI command provided
- [ ] Manual config JSON example correct
- [ ] Environment variable isolation explained
- [ ] Verification steps clear
- [ ] Troubleshooting guidance included

**Status**: ❌ FAIL (skill not yet created)

---

## Test 9: Version Migration (Integration Test)

**Purpose**: Invoke skill for v2 to v3 migration guidance

**Test Method**: Run Claude with migration request

**Test Command**:
```bash
echo "I want to migrate my FastMCP server from v2 to v3" | claude-code-cli
```

**Expected Behavior**:
1. Skill provides breaking changes list
2. Skill provides migration steps
3. Skill provides compatibility matrix
4. Skill warns about v3 beta status

**Verification**:
- [ ] Breaking changes documented
- [ ] Migration steps actionable
- [ ] Compatibility matrix clear
- [ ] Beta warning prominent
- [ ] Rollback strategy mentioned

**Status**: ❌ FAIL (skill not yet created)

---

## Test 10: Creating-Skills Integration (Integration Test)

**Purpose**: Invoke both skills in sequence for custom MCP skill creation

**Test Method**: Run Claude with composite request

**Test Command**:
```bash
echo "Create a custom skill for working with my company's API using MCP" | claude-code-cli
```

**Expected Behavior**:
1. Creating-skills skill loads first
2. Creating-skills delegates to fastmcp skill for MCP implementation
3. Fastmcp skill provides MCP server structure
4. Creating-skills skill wraps MCP server as reusable skill
5. Workflow is coherent and doesn't duplicate guidance

**Verification**:
- [ ] Skills compose correctly
- [ ] No conflicting guidance
- [ ] Workflow is smooth
- [ ] Output is coherent custom skill
- [ ] Both skill checklists satisfied

**Status**: ❌ FAIL (skills not yet integrated)

---

## Test Execution Log

### Run 1: [Date]
- Test 1: ❌ FAIL
- Test 2: ❌ FAIL
- Test 3: ❌ FAIL
- Test 4: ❌ FAIL
- Test 5: ❌ FAIL
- Test 6: ❌ FAIL
- Test 7: ❌ FAIL
- Test 8: ❌ FAIL
- Test 9: ❌ FAIL
- Test 10: ❌ FAIL

**Overall**: ❌ 0/10 tests passing

### Run 2: [Date after implementation]
- Test 1: [Status]
- Test 2: [Status]
- Test 3: [Status]
- Test 4: [Status]
- Test 5: [Status]
- Test 6: [Status]
- Test 7: [Status]
- Test 8: [Status]
- Test 9: [Status]
- Test 10: [Status]

**Overall**: [X/10 tests passing]

---

## Automated Test Runner

```bash
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
```

Make executable:
```bash
chmod +x skills/fastmcp/run_validation_tests.sh
```

---

## Success Criteria Summary

**Minimum Requirements for Skill Completion**:
- ✅ All 10 tests passing
- ✅ At least 10 Python examples
- ✅ At least 10 TypeScript examples
- ✅ >3000 words of content
- ✅ All required sections present
- ✅ No syntax errors in examples
- ✅ Integration with creating-skills verified
- ✅ Progressive disclosure validated

**Current Status**: 0/10 tests passing ❌
**Next Step**: Implement SKILL.md to make tests pass (GREEN phase)
