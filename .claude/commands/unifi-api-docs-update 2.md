---
description: Update UNIFI_API.md with latest endpoints from developer.ui.com
allowed-tools:
  - Bash(node:*)
  - Bash(npm:*)
  - Read
  - Edit
  - Grep
author: project
version: 1.0.0
---

Scrape the latest UniFi API documentation from developer.ui.com and update docs/UNIFI_API.md with newly discovered endpoints.

This command runs the `scripts/update-api-docs.js` Puppeteer-based scraper to fetch API documentation from the official UniFi developer site and compare it against the current documentation.

**API Sources:**

- Site Manager API (v1.0.0): https://developer.ui.com/site-manager/v1.0.0/gettingstarted
- Network API (v10.1.68): https://developer.ui.com/network/v10.1.68/gettingstarted
- Protect API (v6.2.83): https://developer.ui.com/protect/v6.2.83/gettingstarted

**Steps to execute:**

1. Verify dependencies are installed:
   ```bash
   npm list puppeteer
   ```
   If not installed, run: `npm install puppeteer`

2. Run the API documentation updater:
   ```bash
   node scripts/update-api-docs.js
   ```

3. Review the changes:
   - Check how many new endpoints were discovered
   - Verify the markdown formatting is correct
   - Review the extracted examples and descriptions

4. Show summary:
   ```bash
   git diff --stat docs/UNIFI_API.md
   ```

**What the script does:**

1. **Extracts endpoints** from each API source:
   - Navigates to the getting started page
   - Discovers all endpoint links from the sidebar
   - Filters out non-API pages (getting started, guides, etc.)

2. **Compares with existing documentation**:
   - Loads current docs/UNIFI_API.md
   - Checks if each endpoint is already documented
   - Identifies new endpoints to add

3. **Extracts detailed information** for new endpoints:
   - HTTP method (GET, POST, PUT, PATCH, DELETE)
   - Endpoint path
   - Description
   - Code examples (curl commands)
   - Reference link to official docs

4. **Updates documentation**:
   - Generates markdown sections for each API product
   - Adds new endpoints with proper formatting
   - Appends sections to existing documentation
   - Preserves all existing content

**Expected output:**

```
🔍 UniFi API Documentation Updater

Loading existing documentation...
✓ Loaded (42243 characters)

Processing Site Manager v1.0.0...
  Loading https://developer.ui.com/site-manager/v1.0.0/gettingstarted...
  ✓ Found 11 endpoints
  → 4 new endpoints found
    Extracting: Query ISP Metrics...
    Extracting: List SD-WAN Configs...
    Extracting: Get SD-WAN Config by ID...
    Extracting: Get SD-WAN Config Status...

Processing Network v10.1.68...
  Loading https://developer.ui.com/network/v10.1.68/gettingstarted...
  ✓ Found 74 endpoints
  → 3 new endpoints found
    Extracting: Adopt Devices...
    Extracting: List DPI Application Categories...
    Extracting: Quick Start...

Processing Protect v6.2.83...
  Loading https://developer.ui.com/protect/v6.2.83/gettingstarted...
  ✓ Found 41 endpoints
  → 36 new endpoints found
    Extracting: Get application information...
    Extracting: Get viewer details...
    [... more endpoints ...]

Generating updated documentation...
✓ Updated documentation saved to: docs/UNIFI_API.md

📊 Summary:
  Site Manager: +4 new endpoints
  Network: +3 new endpoints
  Protect: +36 new endpoints

✅ Complete!
```

**Report back with:**

- Number of new endpoints discovered per API product
- Total lines added to documentation
- Any errors or warnings during extraction
- Git diff statistics showing the changes

**Safety checks:**

- Script only adds new endpoints, never removes existing content
- All official API URLs are hardcoded (no user input)
- Runs in headless mode (no manual interaction needed)
- Timeout handling for slow pages
- Error handling to skip problematic endpoints

**Notes:**

- The script uses Puppeteer to scrape public documentation (no authentication required)
- First run may take 2-3 minutes depending on network speed
- Subsequent runs will be faster as most endpoints are already documented
- Script is safe to run multiple times (idempotent)
