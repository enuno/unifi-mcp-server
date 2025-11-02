# Cursor Rules for UniFi MCP Server

This directory contains project-specific rules and guidelines for Cursor IDE AI assistants. These rules migrated from the legacy `.cursorrules` format to the current modular `.mdc` (Markdown Cursor) standard.

## File Organization

Rules are organized by domain for better context-specific application:

### Core Rules (Always Applied)

**core-principles.mdc** - Fundamental coding principles

- Async-first development patterns
- Type safety and validation
- Security-first design
- Comprehensive testing requirements
- Documentation standards

**mcp-tools.mdc** - MCP tool implementation patterns

- Tool structure and organization
- Safety checks and confirm parameters
- Error handling patterns
- Cache invalidation strategies

**unifi-api.mdc** - UniFi API integration guidelines

- Authentication with API keys
- Cloud vs local gateway modes
- Rate limiting considerations
- Error handling patterns
- Official documentation references

### Contextual Rules

**project-context.mdc** - Project overview and context

- Technology stack
- Architecture patterns
- File structure conventions
- Naming standards

**workflow.mdc** - Development workflow

- Git branching and commit practices
- Testing procedures
- Code quality checklist
- Pre-commit requirements

**environment-setup.mdc** - Configuration management

- Environment variables
- Configuration loading order
- Security best practices

**common-mistakes.mdc** - Best practices and pitfalls

- Common mistakes to avoid
- Quick command reference
- Key resources
- Reminders

## How to Use

Cursor IDE automatically loads these rules based on:

1. **File patterns** (`globs`) - Rules apply when editing matching files
2. **Always apply flag** (`alwaysApply: true`) - Rules always loaded regardless of context
3. **File context** - Rules apply when working in specific directories

## Migration Notes

Migrated from legacy `.cursorrules` format on 2025-01-XX:

- Split monolithic rules into focused `.mdc` files
- Added metadata headers for better organization
- Maintained all original guidelines and patterns
- Improved discoverability with descriptive file names

## Contributing

When adding new rules:

1. Create a new `.mdc` file with descriptive name
2. Add YAML frontmatter with `description`, `globs`, and `alwaysApply`
3. Follow existing format and style
4. Update this README with brief description

## Related Documentation

For more detailed guidelines, see:

- `docs/AI-Coding/AI_CODING_ASSISTANT.md` - AI coding assistant guidelines
- `docs/AI-Coding/AI_GIT_PRACTICES.md` - Git best practices
- `AGENTS.md` - Agent guidelines and rules
- `CONTRIBUTING.md` - General contribution guidelines
