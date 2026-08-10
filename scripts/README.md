# UniFi API Documentation Scraper

Puppeteer-based scraper for extracting API documentation from the UniFi Network portal.

## Overview

This scraper authenticates to the UniFi portal, navigates the API documentation, and extracts detailed endpoint information into a structured JSON format. It can then compare versions and generate updated Markdown documentation.

## Features

- 🔐 **Secure Authentication** - Session cookie management and credential handling
- 🎯 **Intelligent Extraction** - Multiple selector strategies with fallbacks
- 📊 **Version Comparison** - Detailed diff generation between API versions
- 📝 **Documentation Generation** - Automated Markdown documentation updates
- 🐛 **Debug Mode** - Screenshots and DOM dumps for troubleshooting
- ♻️  **Session Reuse** - Cached authentication for faster subsequent runs

## Installation

```bash
cd scripts
npm install
```

## Configuration

Create a `.env` file in the `scripts/` directory:

```bash
cp .env.example .env
```

Edit `.env` with your UniFi account credentials:

```env
UNIFI_EMAIL=your.email@example.com
UNIFI_PASSWORD=your_password_here
HEADLESS=true
```

**Security Note:** Never commit the `.env` file to version control. It's already included in `.gitignore`.

## Usage

### 1. Scrape API Documentation

Extract the current API documentation:

```bash
# Headless mode (default)
npm run scrape

# Headed mode (see browser window)
npm run scrape:headed

# With debug output and screenshots
node scraper/scrape-api-docs.js --debug

# Specify version
node scraper/scrape-api-docs.js --version=10.1.68

# Clear saved session cookies
node scraper/scrape-api-docs.js --clear-session
```

**Output:** `scraped-api-spec-v{version}.json`

### 2. Compare API Versions

Compare two API specification versions:

```bash
# Using version shorthand
npm run compare 10.0.160 10.1.68

# Using full paths
node compare/diff-api-specs.js scraped-api-spec-v10.0.160.json scraped-api-spec-v10.1.68.json
```

**Output:** `api-diff-v{old}-to-v{new}.json`

The comparison will show:

- New categories and endpoints
- Removed categories and endpoints
- Modified endpoints with detailed changes
- Statistics and summary

### 3. Update Documentation

Generate updated `docs/UNIFI_API.md`:

```bash
# Using version shorthand (auto-finds matching diff)
npm run update-docs 10.1.68

# With explicit diff file
node update/update-docs.js scraped-api-spec-v10.1.68.json api-diff-v10.0.160-to-v10.1.68.json
```

**Output:** `docs/UNIFI_API.md`

## Complete Workflow

To update documentation for a new API version:

```bash
# 1. Scrape new version
npm run scrape -- --version=10.1.68

# 2. Compare with previous version
npm run compare 10.0.160 10.1.68

# 3. Generate updated documentation
npm run update-docs 10.1.68

# 4. Review changes
git diff docs/UNIFI_API.md

# 5. Commit if satisfied
git add docs/UNIFI_API.md
git commit -m "docs: update UNIFI_API.md to v10.1.68"
```

## Architecture

### Directory Structure

```
scripts/
├── scraper/
│   ├── scrape-api-docs.js       # Main entry point
│   ├── auth/
│   │   └── unifi-login.js       # Authentication & session management
│   ├── extractors/
│   │   ├── navigation-extractor.js   # Extract doc structure
│   │   ├── endpoint-extractor.js     # Extract endpoint details
│   │   └── schema-extractor.js       # Extract schemas & parameters
│   ├── parsers/
│   │   └── api-spec-parser.js   # Normalize to structured format
│   └── utils/
│       ├── wait-for-selectors.js     # Robust selector waiting
│       └── screenshot-debugger.js    # Debug helpers
├── compare/
│   └── diff-api-specs.js        # Version comparison
└── update/
    └── update-docs.js           # Markdown generation
```

### Data Flow

```
1. Authentication
   └─> Save session cookies

2. Navigation Extraction
   └─> Discover categories & endpoints

3. Endpoint Extraction
   ├─> For each endpoint:
   │   ├─> Extract method, path, description
   │   ├─> Extract parameters (path & query)
   │   ├─> Extract request/response schemas
   │   └─> Extract examples
   └─> Save to JSON

4. Comparison (optional)
   ├─> Load old & new specs
   ├─> Identify added/removed/modified items
   └─> Save diff to JSON

5. Documentation Generation
   ├─> Load spec & diff
   ├─> Generate markdown sections
   └─> Write to docs/UNIFI_API.md
```

## Troubleshooting

### Authentication Issues

If you encounter login problems:

```bash
# Clear saved session and try again
node scraper/scrape-api-docs.js --clear-session --headed
```

**Passkeys/WebAuthn:** If your account uses passkeys (Touch ID, Face ID, security keys, or biometric authentication), the scraper will automatically detect this and wait up to 120 seconds for you to complete authentication. **You MUST use `--headed` mode** for passkey authentication.

**Traditional 2FA:** If you use SMS or authenticator app codes (not passkeys), the scraper will pause for up to 90 seconds to allow manual code entry. Use `--headed` mode.

**Password-only accounts:** If you use a traditional password without 2FA or passkeys, the scraper can run in headless mode (but headed mode is recommended for troubleshooting).

### Selector Issues

If the scraper fails to find elements:

```bash
# Run with debug mode to capture screenshots
node scraper/scrape-api-docs.js --debug
```

Check the `screenshots/` directory for visual debugging.

### Session Expiration

Session cookies are saved to `session-cookies.json` and reused. If you encounter authentication errors:

1. Delete `session-cookies.json`
2. Run scraper again with `--clear-session`

### Slow Extraction

The scraper processes endpoints sequentially to avoid rate limiting. For large API specifications:

- Expected time: ~1-2 minutes per 10 endpoints
- Add delays between requests (configurable in `endpoint-extractor.js`)
- Session cookies speed up subsequent runs

## Security Best Practices

1. **Never commit credentials**
   - `.env` is gitignored
   - Use environment variables in CI/CD

2. **Session management**
   - `session-cookies.json` is gitignored
   - Cookies auto-expire based on portal settings

3. **Credential prompts**
   - If `.env` is missing, scraper prompts interactively
   - Passwords are masked during input

## Limitations

- **Dynamic Content:** Relies on UniFi portal structure; may break with UI updates
- **Rate Limiting:** Sequential extraction to respect API rate limits
- **Authentication:** Requires valid UniFi account with API doc access
- **Early Access:** v10.1.68 is EA (Early Access) and may change

## Future Enhancements

- [ ] Parallel endpoint extraction with rate limiting
- [ ] Configurable extraction strategies (CSS selectors, XPath)
- [ ] OpenAPI/Swagger output format
- [ ] Automated scheduling (cron job)
- [ ] Diff visualization (HTML report)
- [ ] CI/CD integration (GitHub Actions)

## Contributing

When modifying the scraper:

1. Test with `--headed` mode first to see browser behavior
2. Use `--debug` to capture screenshots for troubleshooting
3. Update selector strategies if portal structure changes
4. Add fallback selectors for robustness
5. Document any new options or features

## check_model_ids.py

Checks that every Claude model id referenced in this repository is still
served by the Anthropic API. Pinned dated snapshots (for example
`claude-3-7-sonnet-20250219`) keep working right up to their retirement date
and then fail everywhere at once, so this turns a silent expiry into a check
you can run.

```bash
# List which ids are referenced and where — no network, no credentials
python scripts/check_model_ids.py --offline

# Verify those ids against the live API
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/check_model_ids.py
```

`ANTHROPIC_AUTH_TOKEN` (written by Claude Code OAuth logins) is accepted as a
fallback when `ANTHROPIC_API_KEY` is unset.

Exit codes: `0` all referenced ids are served, `1` at least one is retired,
`2` the API could not be reached, or no credential was found. The non-zero
exit on retirement makes it usable as a scheduled CI job.

This PR does not wire the script into any workflow. Running it live needs an
`ANTHROPIC_API_KEY` secret, and whether to spend one on a scheduled job is the
maintainer's call, so it stays a manual script here. `--offline` needs no
credential and can be added to an existing job as-is.

Only ids that are actually sent to the API are matched. Product names such as
`claude-code-action` or `claude-desktop` are ignored.

The behaviour above is covered by `tests/unit/test_check_model_ids.py`, which
stubs the API response so no network access or credential is needed:

```bash
pytest tests/unit/test_check_model_ids.py
```

## License

Same as parent project (see root LICENSE file).
