# Claude Skills for UniFi MCP Server

This directory contains specialized Claude skills that provide interactive guidance and decision support for developing, testing, and maintaining the UniFi MCP Server project.

## Overview

**Skills vs Slash Commands:**

- **Skills** provide interactive guidance, domain expertise, and multi-step workflows with decision-making
- **Slash Commands** execute deterministic operations like running tests, linting, or building

Think of skills as expert consultants that guide you through complex processes, while slash commands are quick automation tools.

## Available Skills

### Priority 1: Immediate Value (Use Daily)

#### 1. test-strategy
**When to use:** Improving test coverage for any module

Guides test creation for low-coverage modules to achieve the 60-70% coverage target. Analyzes coverage gaps, suggests specific test scenarios, and provides mock API response templates.

**Key features:**
- Coverage gap analysis
- Test scenario recommendations
- Mock API response templates
- TDD workflow guidance
- Pytest fixture patterns

**Example usage:**
```
I want to improve test coverage for src/tools/clients.py
```

#### 2. tool-design-reviewer
**When to use:** Before implementing any new MCP tool

Pre-implementation design review ensuring tools follow best practices and maintain consistency with the existing 77+ tools. Acts as a quality gate before coding.

**Key features:**
- MCP best practices validation
- Parameter and naming review
- Safety mechanism checks
- Testability assessment
- Consistency verification

**Example usage:**
```
I want to create a tool to delete a QoS profile. Can you review my design?
```

#### 3. zbf-implementation-guide
**When to use:** Working on Zone-Based Firewall features (v0.2.0 P0)

Comprehensive guide for implementing Zone-Based Firewall support, including architecture, data models, migration strategies, and best practices for the critical v0.2.0 feature.

**Key features:**
- ZBF architecture guidance
- Data model design patterns
- API endpoint verification
- Migration from traditional firewall
- Zone template systems

**Example usage:**
```
I need to complete the ZBF Phase 1 implementation
```

### Priority 2: Near-Term Value (Use Weekly)

#### 4. unifi-api-explorer
**When to use:** Researching new UniFi API endpoints

Interactive API exploration and testing to understand endpoint behavior, design Pydantic models from responses, and document API quirks before implementation.

**Key features:**
- Safe API endpoint testing
- Response structure analysis
- Pydantic model generation
- API behavior documentation
- Tool template generation

**Example usage:**
```
I want to explore the QoS profile API endpoints for Phase 3
```

#### 5. refactor-assistant
**When to use:** Improving code quality or preparing for new features

Guides code refactoring to improve testability, maintainability, and performance while preserving functionality. Particularly useful when improving test coverage.

**Key features:**
- Code smell detection
- Refactoring pattern suggestions
- Testability improvements
- Safe refactoring workflows
- Performance optimization

**Example usage:**
```
This module has 20% coverage and is hard to test. Help me refactor it.
```

### Priority 3: Long-Term Value (Use Monthly/Quarterly)

#### 6. api-doc-generator
**When to use:** After implementing new tools or before releases

Automates generation and maintenance of API.md documentation by extracting information from MCP tool definitions, docstrings, and type hints.

**Key features:**
- Automatic tool discovery
- Metadata extraction from code
- Consistent documentation format
- Completeness validation
- Cross-reference generation

**Example usage:**
```
Update API.md with all the new v0.2.0 tools
```

#### 7. release-planner
**When to use:** Planning or executing version releases

Comprehensive release management including checklists, validation, changelog generation, and release process orchestration for v0.2.0, v0.3.0, and beyond.

**Key features:**
- Release type determination
- Pre-release validation
- Automated changelog generation
- Release workflow coordination
- Post-release verification

**Example usage:**
```
I want to prepare the v0.2.0 release
```

#### 8. integration-guide
**When to use:** Implementing major new features from roadmap

Structured guidance for integrating major features that span multiple components (models, API, tools, tests, docs). Coordinates complex multi-component implementations.

**Key features:**
- Feature breakdown and phasing
- Component coordination
- Implementation workflow
- Integration testing strategy
- Documentation planning

**Example usage:**
```
Help me plan the QoS and Traffic Management implementation
```

## Quick Reference

### Skill Catalog

| Skill | Purpose | Priority | Use Frequency |
|-------|---------|----------|---------------|
| test-strategy | Improve test coverage | HIGH | Daily |
| tool-design-reviewer | Review tool designs | HIGH | Daily |
| zbf-implementation-guide | ZBF feature guidance | HIGH | Weekly (v0.2.0) |
| unifi-api-explorer | API research & testing | MEDIUM-HIGH | Weekly |
| refactor-assistant | Code quality improvement | MEDIUM | Weekly |
| api-doc-generator | Documentation automation | MEDIUM | Monthly |
| release-planner | Release management | MEDIUM | Per-release |
| integration-guide | Major feature integration | MEDIUM | Per-feature |

### By Development Phase

**Sprint 1 (Test Coverage Improvement):**
1. `test-strategy` - Plan and implement tests
2. `refactor-assistant` - Improve testability
3. `tool-design-reviewer` - Review test coverage tools

**New Feature Development:**
1. `integration-guide` - Plan feature implementation
2. `unifi-api-explorer` - Research API endpoints
3. `tool-design-reviewer` - Design tools
4. `test-strategy` - Create comprehensive tests
5. `api-doc-generator` - Update documentation

**Release Preparation:**
1. `release-planner` - Plan and execute release
2. `api-doc-generator` - Update API.md
3. `test-strategy` - Verify coverage targets

## Usage Examples

### Example 1: Test-Driven Development Workflow

**Scenario:** Improving test coverage for `src/tools/clients.py` (currently 15.91%, target 70%)

```markdown
Step 1: Invoke test-strategy skill
> I want to improve test coverage for src/tools/clients.py

Step 2: Skill analyzes coverage gaps
→ Identifies 8 uncovered functions
→ Categorizes missing tests (happy path, error handling, edge cases)
→ Suggests 15 specific test scenarios

Step 3: Implement tests using recommendations
→ Follow TDD cycle (Red → Green → Refactor)
→ Use provided mock API response templates
→ Run tests frequently: pytest tests/unit/test_clients.py -v

Step 4: Verify coverage improvement
→ Run coverage report: pytest --cov=src/tools/clients --cov-report=term
→ Verify: 15.91% → 72% ✅
```

### Example 2: New Tool Development Lifecycle

**Scenario:** Creating a new QoS profile management tool

```markdown
Step 1: Design review with tool-design-reviewer
> I want to create a tool to manage QoS profiles

→ Skill asks clarifying questions about parameters, return values
→ Reviews naming conventions (create_qos_profile ✅)
→ Checks safety mechanisms (confirm=True required ✅)
→ Validates consistency with existing tools
→ Provides implementation template

Step 2: API exploration with unifi-api-explorer
> Research the /api/s/{site}/rest/qosprofile endpoint

→ Test GET request (safe)
→ Analyze response structure
→ Design Pydantic model from response
→ Test POST/PUT/DELETE (in test site)
→ Document API behavior and quirks

Step 3: Implement tool
→ Create src/tools/qos.py
→ Use template from tool-design-reviewer
→ Integrate API client code from unifi-api-explorer

Step 4: Create tests with test-strategy
> Create tests for the new QoS tools

→ Happy path tests
→ Error handling tests
→ Edge case tests
→ Achieve 80%+ coverage

Step 5: Update docs with api-doc-generator
> Update API.md with new QoS tools

→ Automatic documentation generation
→ Consistent format
→ Usage examples included
```

### Example 3: API Integration Workflow

**Scenario:** Implementing Traffic Flow Monitoring feature

```markdown
Step 1: Feature planning with integration-guide
> Help me plan the Traffic Flow implementation from Phase 2

→ Breaks down into components (models, API, tools, tests, docs)
→ Defines implementation phases
→ Creates timeline and dependencies
→ Provides coordination checklist

Step 2: API research with unifi-api-explorer
> Explore /api/s/{site}/stat/trafficflow endpoint

→ Test endpoint availability
→ Analyze flow data structure
→ Design TrafficFlow Pydantic model
→ Document API behavior
→ Generate tool templates

Step 3: Implement each component
→ Phase A: Data models (TrafficFlow, FlowStatistics)
→ Phase B: API client integration
→ Phase C: Core tools (list, get, filter)
→ Phase D: Advanced tools (stream, analytics)

Step 4: Testing with test-strategy
→ Unit tests for models
→ Tool functionality tests
→ Integration tests
→ Achieve 86% coverage ✅

Step 5: Documentation with api-doc-generator
→ Generate API.md sections
→ Create usage examples
→ Update README.md
```

## Workflow Diagrams

### Test Coverage Improvement Workflow

```
┌─────────────────────────────────────────────────────────┐
│ START: Module with low coverage (<40%)                 │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 1. Invoke test-strategy skill                          │
│    → Analyze coverage gaps                             │
│    → Identify untested functions                       │
│    → Categorize missing tests                          │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 2. (Optional) Invoke refactor-assistant                │
│    → If code is hard to test                           │
│    → Improve testability                               │
│    → Extract functions, inject dependencies            │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Implement tests (TDD cycle)                         │
│    → Write test (Red)                                  │
│    → Make it pass (Green)                              │
│    → Refactor                                          │
│    → Repeat for each scenario                          │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Verify coverage improvement                         │
│    → Run: pytest --cov=module --cov-report=term       │
│    → Check: Coverage increased 40-50%?                 │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Run quality checks                                   │
│    → /lint: ruff check                                 │
│    → /format: black + isort                            │
│    → /test: full test suite                            │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ END: Module coverage ≥70% ✅                            │
└─────────────────────────────────────────────────────────┘
```

### New Tool Development Workflow

```
┌─────────────────────────────────────────────────────────┐
│ START: New tool requirement                            │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 1. Invoke tool-design-reviewer                         │
│    → Define tool purpose                               │
│    → Design parameters                                 │
│    → Review naming & consistency                       │
│    → Validate safety mechanisms                        │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Invoke unifi-api-explorer                           │
│    → Test API endpoints                                │
│    → Analyze response structure                        │
│    → Design Pydantic models                            │
│    → Document API behavior                             │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Implement tool                                       │
│    → Create src/tools/[module].py                      │
│    → Use @mcp.tool() decorator                         │
│    → Add safety checks                                 │
│    → Implement error handling                          │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Invoke test-strategy                                │
│    → Plan test scenarios                               │
│    → Implement comprehensive tests                     │
│    → Achieve 80%+ coverage                             │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Invoke api-doc-generator                            │
│    → Update API.md                                     │
│    → Add usage examples                                │
│    → Verify documentation complete                     │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ END: Tool ready for release ✅                          │
└─────────────────────────────────────────────────────────┘
```

## Best Practices

### When to Use Skills

**DO use skills for:**
- Complex multi-step processes
- Decision-making and planning
- Learning new patterns or best practices
- Getting domain-specific guidance
- Coordinating multiple components
- Interactive problem-solving

**DON'T use skills for:**
- Simple deterministic operations (use slash commands instead)
- Running tests, linting, formatting (use /test, /lint, /format)
- Quick file operations (use direct tools)

### Combining Skills with Slash Commands

Skills provide guidance, slash commands execute operations:

```
Skill: test-strategy
→ Recommends which tests to write
→ Suggests test scenarios
→ Provides mock templates

Slash Command: /test
→ Runs the actual tests
→ Shows pass/fail results
→ Generates coverage report

Together:
1. Use test-strategy to plan tests
2. Implement tests based on recommendations
3. Use /test to verify tests pass
4. Use test-strategy to analyze remaining gaps
5. Repeat until coverage target reached
```

### Skill Development

Want to create a new skill? Follow this template:

```markdown
---
name: skill-name
description: When to use this skill and what it does
---

# Skill Name

## Purpose
What this skill accomplishes

## When to Use This Skill
Specific scenarios where this skill is valuable

## Phase 1: Understanding Context
How the skill gathers information

## Phase 2: Analysis
How the skill analyzes the problem

## Phase 3: Guidance
Interactive recommendations and next steps

## Phase 4: Verification
How to validate the skill's recommendations

## Integration with Other Skills
Related skills and workflows

## Reference Files
Documentation to load for context
```

## Troubleshooting

### Skill Not Loading

**Problem:** Skill doesn't appear or doesn't load documentation

**Solution:**
1. Check skill file exists in `.claude/skills/`
2. Verify frontmatter is correctly formatted (YAML)
3. Ensure skill name matches filename
4. Restart Claude Code if needed

### Skill Provides Generic Advice

**Problem:** Skill doesn't use project-specific context

**Solution:**
1. Explicitly ask skill to load reference files
2. Provide more specific context about your goal
3. Reference specific files (e.g., "Load TODO.md for context")

### Unclear Which Skill to Use

**Problem:** Multiple skills seem relevant

**Decision Tree:**
- Testing/coverage work? → **test-strategy**
- Designing a new tool? → **tool-design-reviewer**
- Exploring API? → **unifi-api-explorer**
- Complex refactoring? → **refactor-assistant**
- Major feature? → **integration-guide**
- ZBF-specific? → **zbf-implementation-guide**
- Documentation? → **api-doc-generator**
- Release? → **release-planner**

## Success Metrics

Skills are working well when:

- **Test coverage** improves steadily toward 60-70% target
- **New tools** are consistently well-designed and tested
- **API integration** is smooth with fewer surprises
- **Refactoring** maintains functionality while improving quality
- **Documentation** stays in sync with code
- **Releases** go smoothly with comprehensive checklists
- **Development velocity** increases over time

## Contributing

Have ideas for new skills or improvements to existing ones?

1. Discuss in GitHub Issues or Discussions
2. Follow the skill template above
3. Test thoroughly with real scenarios
4. Update this README.md
5. Submit a pull request

## Support

- **Skill issues:** Report in GitHub Issues
- **Usage questions:** Ask in GitHub Discussions
- **Skill requests:** Open a feature request issue

---

**Last Updated:** 2025-11-21

**Project:** UniFi MCP Server v0.1.4 → v0.2.0

**Total Skills:** 8 (Priority 1: 3, Priority 2: 2, Priority 3: 3)
