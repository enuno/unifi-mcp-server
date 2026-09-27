#!/usr/bin/env node
/**
 * Simple script to update UNIFI_API.md from developer.ui.com
 */

import puppeteer from 'puppeteer';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API_SOURCES = [
  { name: 'Site Manager', url: 'https://developer.ui.com/site-manager/v1.0.0/gettingstarted', version: 'v1.0.0' },
  { name: 'Network', url: 'https://developer.ui.com/network/v10.6.106/gettingstarted', version: 'v10.6.106' },
  { name: 'Protect', url: 'https://developer.ui.com/protect/v7.3.68/gettingstarted', version: 'v7.3.68' }
];

const DOCS_PATH = path.join(__dirname, '../docs/UNIFI_API.md');

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Extract all endpoints from a developer.ui.com page
 */
async function extractEndpoints(page, sourceUrl) {
  console.log(`  Loading ${sourceUrl}...`);

  await page.goto(sourceUrl, {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  await delay(3000);

  // Extract all endpoint links from sidebar
  const endpoints = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[href]'));

    return links
      .filter(a => {
        const href = a.href || '';
        // Filter to only API operation links (not Getting Started, etc.)
        return href.includes('/site-manager/v') ||
               href.includes('/network/v') ||
               href.includes('/protect/v');
      })
      .map(a => {
        const href = a.href;
        const url = new URL(href);
        const pathParts = url.pathname.split('/').filter(Boolean);

        return {
          name: a.textContent?.trim(),
          href: href,
          path: url.pathname,
          product: pathParts[0],
          version: pathParts[1],
          operation: pathParts[2]
        };
      })
      .filter(ep => ep.operation && ep.operation !== 'gettingstarted');
  });

  console.log(`  ✓ Found ${endpoints.length} endpoints`);
  return endpoints;
}

/**
 * Extract detailed info for a single endpoint
 */
async function extractEndpointDetails(page, endpoint) {
  console.log(`    Extracting: ${endpoint.name}...`);

  try {
    await page.goto(endpoint.href, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await delay(3000);

    const details = await page.evaluate(() => {
      const content = {};

      // Get the main content area
      const mainContent = document.body.textContent || '';

      // Try to find HTTP method and path
      const methodMatch = mainContent.match(/(GET|POST|PUT|PATCH|DELETE)\s+([\/\w\-{}]+)/);
      if (methodMatch) {
        content.method = methodMatch[1];
        content.path = methodMatch[2];
      }

      // Get description (usually first paragraph)
      const firstPara = document.querySelector('p');
      if (firstPara) {
        content.description = firstPara.textContent?.trim();
      }

      // Look for code examples
      const codeBlocks = Array.from(document.querySelectorAll('pre code, pre'));
      content.examples = codeBlocks.map(block => block.textContent?.trim()).filter(Boolean);

      return content;
    });

    return { ...endpoint, ...details };
  } catch (error) {
    console.log(`      ⚠️  Skipped (${error.message})`);
    return endpoint;
  }
}

/**
 * Load existing API docs
 */
async function loadExistingDocs() {
  try {
    const content = await fs.readFile(DOCS_PATH, 'utf-8');
    return content;
  } catch (error) {
    console.log('No existing docs found, will create new file');
    return '';
  }
}

/**
 * Check if endpoint exists in docs
 */
function endpointExistsInDocs(docs, endpoint) {
  const searchStrings = [
    endpoint.name,
    endpoint.operation,
    endpoint.path
  ].filter(Boolean);

  return searchStrings.some(str => docs.includes(str));
}

/**
 * Generate markdown for new endpoints
 */
function generateEndpointMarkdown(endpoint) {
  let md = `### ${endpoint.name}\n\n`;

  if (endpoint.method && endpoint.path) {
    md += `- **Method:** \`${endpoint.method}\`\n`;
    md += `- **Endpoint:** \`${endpoint.path}\`\n\n`;
  }

  if (endpoint.description) {
    md += `${endpoint.description}\n\n`;
  }

  if (endpoint.examples && endpoint.examples.length > 0) {
    md += `**Example:**\n\`\`\`json\n${endpoint.examples[0]}\n\`\`\`\n\n`;
  }

  md += `**Reference:** [${endpoint.name}](${endpoint.href})\n\n`;
  md += `---\n\n`;

  return md;
}

async function main() {
  console.log('\n🔍 UniFi API Documentation Updater\n');

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  try {
    // Load existing docs
    console.log('Loading existing documentation...');
    const existingDocs = await loadExistingDocs();
    console.log(`✓ Loaded (${existingDocs.length} characters)\n`);

    const allNewEndpoints = {};

    // Process each API source
    for (const source of API_SOURCES) {
      console.log(`\nProcessing ${source.name} ${source.version}...`);

      // Get list of endpoints
      const endpoints = await extractEndpoints(page, source.url);

      // Filter to only new endpoints
      const newEndpoints = endpoints.filter(ep => !endpointExistsInDocs(existingDocs, ep));

      console.log(`  → ${newEndpoints.length} new endpoints found`);

      if (newEndpoints.length > 0) {
        // Extract details for all new endpoints
        const detailedEndpoints = [];
        for (const endpoint of newEndpoints) {
          const details = await extractEndpointDetails(page, endpoint);
          detailedEndpoints.push(details);
        }

        allNewEndpoints[source.name] = detailedEndpoints;
      }
    }

    await browser.close();

    // Generate updated documentation
    console.log('\n\nGenerating updated documentation...');

    let updatedDocs = existingDocs;
    const newSections = [];

    Object.entries(allNewEndpoints).forEach(([productName, endpoints]) => {
      if (endpoints.length === 0) return;

      let section = `\n## ${productName} API - New Endpoints\n\n`;
      section += `*Added: ${new Date().toISOString().split('T')[0]}*\n\n`;

      endpoints.forEach(ep => {
        section += generateEndpointMarkdown(ep);
      });

      newSections.push(section);
    });

    if (newSections.length > 0) {
      updatedDocs += '\n\n' + newSections.join('\n\n');

      // Save updated docs
      await fs.writeFile(DOCS_PATH, updatedDocs);
      console.log(`✓ Updated documentation saved to: ${DOCS_PATH}`);

      // Summary
      console.log('\n📊 Summary:');
      Object.entries(allNewEndpoints).forEach(([name, eps]) => {
        console.log(`  ${name}: +${eps.length} new endpoints`);
      });
    } else {
      console.log('✓ No new endpoints found - documentation is up to date!');
    }

    console.log('\n✅ Complete!\n');

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    console.error(error.stack);
    await browser.close();
    process.exit(1);
  }
}

main();
