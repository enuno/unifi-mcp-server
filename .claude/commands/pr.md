---
description: Create a pull request with AI-generated description
---

Create a comprehensive pull request for the current branch.

Steps to execute:

1. Check current git status and branch name
2. Review all commits since branching from main
3. Analyze all code changes
4. Generate a comprehensive PR description including:
   - Summary of changes
   - Type of change (feature/bugfix/refactor/docs)
   - Testing performed
   - Checklist of completed items
   - Note about AI assistance

5. Create the PR using: `gh pr create --title "<title>" --body "<description>"`

The PR description should follow this format:

## Description
[Brief description of changes]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
[Describe testing performed]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Commented complex code
- [ ] Updated documentation
- [ ] Added tests
- [ ] Tests pass
- [ ] No new warnings

## AI Assistance
This PR was created with assistance from Claude Code.

Report back with the PR URL once created.
