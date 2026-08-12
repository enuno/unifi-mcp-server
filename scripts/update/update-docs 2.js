#!/usr/bin/env node
/**
 * Documentation Update Module
 * Generates updated UNIFI_API.md from API specification and diff
 */

import fs from 'fs/promises';
import path from 'path';
import chalk from 'chalk';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Generate markdown documentation
 * @param {Object} apiSpec - API specification
 * @param {Object} diff - Diff object (optional)
 * @returns {string} Markdown content
 */
function generateMarkdown(apiSpec, diff = null) {
  let markdown = '';

  // Header
  markdown += `# UniFi Network API Documentation (v${apiSpec.version})\n\n`;
  markdown += `**Last Updated:** ${apiSpec.lastUpdated}\n\n`;

  // Version update notice
  if (diff && (diff.added.endpoints.length > 0 || diff.added.categories.length > 0 || diff.modified.endpoints.length > 0)) {
    markdown += `## 🆕 What's New in v${apiSpec.version}\n\n`;

    if (diff.version.old) {
      markdown += `Updated from **v${diff.version.old}** to **v${diff.version.new}**\n\n`;
    }

    if (diff.added.categories.length > 0) {
      markdown += `- **${diff.added.categories.length} new API categories**\n`;
    }

    if (diff.added.endpoints.length > 0) {
      markdown += `- **${diff.added.endpoints.length} new endpoints**\n`;
    }

    if (diff.modified.endpoints.length > 0) {
      markdown += `- **${diff.modified.endpoints.length} modified endpoints**\n`;
    }

    markdown += `\n---\n\n`;
  }

  // Table of Contents
  markdown += `## Table of Contents\n\n`;

  // Add standard sections
  markdown += `- [Getting Started](#getting-started)\n`;
  markdown += `- [Authentication](#authentication)\n`;
  markdown += `- [Filtering & Pagination](#filtering--pagination)\n`;
  markdown += `- [Error Handling](#error-handling)\n\n`;

  // Add API categories
  markdown += `### API Resources\n\n`;
  apiSpec.categories.forEach(category => {
    const slug = category.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    markdown += `- [${category.name}](#${slug})\n`;
  });

  markdown += `\n---\n\n`;

  // Getting Started section
  markdown += generateGettingStarted(apiSpec);

  // API Categories
  apiSpec.categories.forEach(category => {
    markdown += generateCategorySection(category, diff);
  });

  // Changelog
  if (diff) {
    markdown += generateChangelogSection(diff);
  }

  return markdown;
}

/**
 * Generate Getting Started section
 * @param {Object} apiSpec - API specification
 * @returns {string}
 */
function generateGettingStarted(apiSpec) {
  return `## Getting Started

### Base URL

\`\`\`
${apiSpec.baseUrl}
\`\`\`

### Authentication

All API requests require authentication. You can authenticate using:

1. **API Token** (recommended for server-to-server)
2. **Session Cookie** (for web applications)

#### API Token Authentication

\`\`\`bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \\
  ${apiSpec.baseUrl}/v1/sites
\`\`\`

### Filtering & Pagination

Most list endpoints support filtering and pagination through query parameters:

- \`limit\` - Maximum number of results (default: 100)
- \`offset\` - Number of results to skip
- \`sort\` - Sort field and order (e.g., \`created_at:desc\`)

### Error Handling

The API uses standard HTTP status codes:

- \`200\` - Success
- \`400\` - Bad Request (validation error)
- \`401\` - Unauthorized (missing or invalid authentication)
- \`403\` - Forbidden (insufficient permissions)
- \`404\` - Not Found
- \`500\` - Internal Server Error

Error responses include a JSON body:

\`\`\`json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid parameter value",
    "details": {}
  }
}
\`\`\`

---

`;
}

/**
 * Generate category section
 * @param {Object} category - Category object
 * @param {Object} diff - Diff object
 * @returns {string}
 */
function generateCategorySection(category, diff) {
  const slug = category.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  let section = `## ${category.name}\n\n`;

  // Check if category is new
  if (diff && diff.added.categories.find(c => c.name === category.name)) {
    section = `## ${category.name} 🆕\n\n`;
  }

  category.endpoints.forEach(endpoint => {
    section += generateEndpointSection(endpoint, category.name, diff);
  });

  return section;
}

/**
 * Generate endpoint section
 * @param {Object} endpoint - Endpoint object
 * @param {string} categoryName - Category name
 * @param {Object} diff - Diff object
 * @returns {string}
 */
function generateEndpointSection(endpoint, categoryName, diff) {
  let section = '';

  const endpointKey = `${endpoint.method} ${endpoint.path}`;

  // Check if endpoint is new or modified
  let badge = '';
  if (diff) {
    const isNew = diff.added.endpoints.find(
      e => `${e.method} ${e.path}` === endpointKey
    );
    const isModified = diff.modified.endpoints.find(
      e => e.endpoint === endpointKey
    );

    if (isNew) {
      badge = ' 🆕';
    } else if (isModified) {
      badge = ' ⚠️ Modified';
    }
  }

  section += `### ${endpoint.description || endpoint.path}${badge}\n\n`;

  section += `- **Method:** \`${endpoint.method}\`\n`;
  section += `- **Endpoint:** \`${endpoint.path}\`\n\n`;

  if (endpoint.description) {
    section += `${endpoint.description}\n\n`;
  }

  // Path Parameters
  if (endpoint.pathParameters && endpoint.pathParameters.length > 0) {
    section += `**Path Parameters:**\n\n`;
    section += generateParameterTable(endpoint.pathParameters);
  }

  // Query Parameters
  if (endpoint.queryParameters && endpoint.queryParameters.length > 0) {
    section += `**Query Parameters:**\n\n`;
    section += generateParameterTable(endpoint.queryParameters);
  }

  // Request Body
  if (endpoint.requestBody) {
    section += `**Request Body:**\n\n`;
    section += generateSchemaTable(endpoint.requestBody);
  }

  // Response
  if (endpoint.responseBody) {
    section += `**Response:**\n\n`;
    section += generateSchemaTable(endpoint.responseBody);
  }

  // Examples
  if (endpoint.examples?.request) {
    section += `**Example Request:**\n\n\`\`\`json\n${endpoint.examples.request}\n\`\`\`\n\n`;
  }

  if (endpoint.examples?.response) {
    section += `**Example Response:**\n\n\`\`\`json\n${endpoint.examples.response}\n\`\`\`\n\n`;
  }

  section += `---\n\n`;

  return section;
}

/**
 * Generate parameter table
 * @param {Array} parameters - Array of parameters
 * @returns {string}
 */
function generateParameterTable(parameters) {
  let table = '| Parameter | Type | Required | Description | Default |\n';
  table += '|-----------|------|----------|-------------|----------|\n';

  parameters.forEach(param => {
    const name = param.name || '';
    const type = param.type || 'string';
    const required = param.required ? 'Yes' : 'No';
    const description = (param.description || '').replace(/\|/g, '\\|');
    const defaultValue = param.default !== null && param.default !== undefined
      ? String(param.default)
      : '-';

    table += `| \`${name}\` | ${type} | ${required} | ${description} | ${defaultValue} |\n`;
  });

  table += '\n';
  return table;
}

/**
 * Generate schema table
 * @param {Object|Array} schema - Schema object or array of fields
 * @returns {string}
 */
function generateSchemaTable(schema) {
  if (!schema) return '';

  // If schema is an object with properties, convert to array
  let fields = [];

  if (Array.isArray(schema)) {
    fields = schema;
  } else if (typeof schema === 'object') {
    // Check if it's a JSON example
    return `\`\`\`json\n${JSON.stringify(schema, null, 2)}\n\`\`\`\n\n`;
  }

  if (fields.length === 0) return '';

  let table = '| Field | Type | Required | Description |\n';
  table += '|-------|------|----------|-------------|\n';

  fields.forEach(field => {
    const name = field.name || '';
    const type = field.type || 'unknown';
    const required = field.required ? 'Yes' : 'No';
    const description = (field.description || '').replace(/\|/g, '\\|');

    table += `| \`${name}\` | ${type} | ${required} | ${description} |\n`;
  });

  table += '\n';
  return table;
}

/**
 * Generate changelog section
 * @param {Object} diff - Diff object
 * @returns {string}
 */
function generateChangelogSection(diff) {
  if (!diff) return '';

  let section = `## Changelog\n\n`;

  section += `### ${diff.version.new} (${diff.lastUpdated.new})\n\n`;

  if (diff.added.categories.length > 0) {
    section += `**New Categories:**\n\n`;
    diff.added.categories.forEach(cat => {
      section += `- ${cat.name}\n`;
    });
    section += `\n`;
  }

  if (diff.added.endpoints.length > 0) {
    section += `**New Endpoints:**\n\n`;
    diff.added.endpoints.forEach(ep => {
      section += `- \`${ep.method} ${ep.path}\` - ${ep.description}\n`;
    });
    section += `\n`;
  }

  if (diff.modified.endpoints.length > 0) {
    section += `**Modified Endpoints:**\n\n`;
    diff.modified.endpoints.forEach(ep => {
      section += `- \`${ep.endpoint}\`\n`;
    });
    section += `\n`;
  }

  if (diff.removed.endpoints.length > 0) {
    section += `**Deprecated/Removed Endpoints:**\n\n`;
    diff.removed.endpoints.forEach(ep => {
      section += `- \`${ep.method} ${ep.path}\`\n`;
    });
    section += `\n`;
  }

  return section;
}

/**
 * Main function
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length < 1) {
    console.log(chalk.yellow('\nUsage: node update-docs.js <api-spec.json> [diff.json]\n'));
    console.log('Or use version shorthand:');
    console.log(chalk.gray('  node update-docs.js 10.1.68\n'));
    process.exit(1);
  }

  let specPath = args[0];
  let diffPath = args[1];

  // Handle version shorthand
  if (!specPath.endsWith('.json')) {
    specPath = path.join(__dirname, `../scraped-api-spec-v${specPath}.json`);

    // Try to find matching diff
    if (!diffPath) {
      const version = args[0];
      const diffPattern = path.join(__dirname, `../api-diff-*-to-v${version}.json`);

      try {
        const files = await fs.readdir(path.dirname(diffPattern));
        const matchingDiff = files.find(f =>
          f.startsWith('api-diff-') && f.endsWith(`-to-v${version}.json`)
        );

        if (matchingDiff) {
          diffPath = path.join(__dirname, '..', matchingDiff);
          console.log(chalk.gray(`Found diff file: ${matchingDiff}`));
        }
      } catch (e) {
        // No diff found
      }
    }
  }

  try {
    // Load API specification
    console.log(chalk.gray(`Loading ${path.basename(specPath)}...`));
    const apiSpec = JSON.parse(await fs.readFile(specPath, 'utf-8'));

    // Load diff if available
    let diff = null;
    if (diffPath) {
      console.log(chalk.gray(`Loading ${path.basename(diffPath)}...`));
      diff = JSON.parse(await fs.readFile(diffPath, 'utf-8'));
    }

    // Generate markdown
    console.log(chalk.gray('Generating documentation...'));
    const markdown = generateMarkdown(apiSpec, diff);

    // Save to docs/UNIFI_API.md
    const docsDir = path.join(__dirname, '../../docs');
    const outputPath = path.join(docsDir, 'UNIFI_API.md');

    await fs.writeFile(outputPath, markdown);

    console.log(chalk.green(`\n✓ Documentation updated: ${path.relative(process.cwd(), outputPath)}\n`));

    // Print stats
    const stats = {
      categories: apiSpec.categories.length,
      endpoints: apiSpec.categories.reduce((sum, cat) => sum + cat.endpoints.length, 0)
    };

    console.log(chalk.gray(`  Categories: ${stats.categories}`));
    console.log(chalk.gray(`  Endpoints: ${stats.endpoints}\n`));

  } catch (error) {
    console.error(chalk.red('\nError:'), error.message);
    console.error(chalk.gray(error.stack));
    process.exit(1);
  }
}

main();
