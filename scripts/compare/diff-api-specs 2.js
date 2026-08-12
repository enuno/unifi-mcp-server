#!/usr/bin/env node
/**
 * API Specification Comparator
 * Compares two API specification versions and generates a diff
 */

import fs from 'fs/promises';
import path from 'path';
import chalk from 'chalk';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Compare two API specifications
 * @param {Object} oldSpec - Old API specification
 * @param {Object} newSpec - New API specification
 * @returns {Object} Diff object
 */
function compareAPISpecs(oldSpec, newSpec) {
  const diff = {
    version: {
      old: oldSpec.version,
      new: newSpec.version
    },
    lastUpdated: {
      old: oldSpec.lastUpdated,
      new: newSpec.lastUpdated
    },
    added: {
      categories: [],
      endpoints: []
    },
    removed: {
      categories: [],
      endpoints: []
    },
    modified: {
      endpoints: []
    },
    unchanged: {
      categories: [],
      endpoints: []
    }
  };

  // Create lookup maps
  const oldCategories = new Map(oldSpec.categories.map(c => [c.name, c]));
  const newCategories = new Map(newSpec.categories.map(c => [c.name, c]));

  // Find new and modified categories
  newSpec.categories.forEach(newCat => {
    const oldCat = oldCategories.get(newCat.name);

    if (!oldCat) {
      // New category
      diff.added.categories.push(newCat);
    } else {
      // Existing category - compare endpoints
      diff.unchanged.categories.push(newCat.name);

      const oldEndpoints = new Map(
        oldCat.endpoints.map(e => [`${e.method} ${e.path}`, e])
      );
      const newEndpoints = new Map(
        newCat.endpoints.map(e => [`${e.method} ${e.path}`, e])
      );

      // Find new and modified endpoints
      newCat.endpoints.forEach(newEndpoint => {
        const key = `${newEndpoint.method} ${newEndpoint.path}`;
        const oldEndpoint = oldEndpoints.get(key);

        if (!oldEndpoint) {
          // New endpoint
          diff.added.endpoints.push({
            category: newCat.name,
            ...newEndpoint
          });
        } else {
          // Check if modified
          const changes = detectChanges(oldEndpoint, newEndpoint);

          if (changes.length > 0) {
            diff.modified.endpoints.push({
              category: newCat.name,
              endpoint: key,
              changes
            });
          } else {
            diff.unchanged.endpoints.push({
              category: newCat.name,
              endpoint: key
            });
          }
        }
      });

      // Find removed endpoints
      oldCat.endpoints.forEach(oldEndpoint => {
        const key = `${oldEndpoint.method} ${oldEndpoint.path}`;
        if (!newEndpoints.has(key)) {
          diff.removed.endpoints.push({
            category: oldCat.name,
            ...oldEndpoint
          });
        }
      });
    }
  });

  // Find removed categories
  oldSpec.categories.forEach(oldCat => {
    if (!newCategories.has(oldCat.name)) {
      diff.removed.categories.push(oldCat);
    }
  });

  return diff;
}

/**
 * Detect changes between two endpoints
 * @param {Object} oldEndpoint - Old endpoint
 * @param {Object} newEndpoint - New endpoint
 * @returns {Array} Array of change descriptions
 */
function detectChanges(oldEndpoint, newEndpoint) {
  const changes = [];

  // Check description
  if (oldEndpoint.description !== newEndpoint.description) {
    changes.push({
      field: 'description',
      old: oldEndpoint.description,
      new: newEndpoint.description
    });
  }

  // Check path parameters
  const pathParamChanges = compareParameters(
    oldEndpoint.pathParameters,
    newEndpoint.pathParameters
  );
  if (pathParamChanges.length > 0) {
    changes.push({
      field: 'pathParameters',
      changes: pathParamChanges
    });
  }

  // Check query parameters
  const queryParamChanges = compareParameters(
    oldEndpoint.queryParameters,
    newEndpoint.queryParameters
  );
  if (queryParamChanges.length > 0) {
    changes.push({
      field: 'queryParameters',
      changes: queryParamChanges
    });
  }

  // Check request body
  if (JSON.stringify(oldEndpoint.requestBody) !== JSON.stringify(newEndpoint.requestBody)) {
    changes.push({
      field: 'requestBody',
      old: oldEndpoint.requestBody,
      new: newEndpoint.requestBody
    });
  }

  // Check response body
  if (JSON.stringify(oldEndpoint.responseBody) !== JSON.stringify(newEndpoint.responseBody)) {
    changes.push({
      field: 'responseBody',
      old: oldEndpoint.responseBody,
      new: newEndpoint.responseBody
    });
  }

  return changes;
}

/**
 * Compare two parameter arrays
 * @param {Array} oldParams - Old parameters
 * @param {Array} newParams - New parameters
 * @returns {Array} Array of changes
 */
function compareParameters(oldParams = [], newParams = []) {
  const changes = [];
  const oldParamMap = new Map(oldParams.map(p => [p.name, p]));
  const newParamMap = new Map(newParams.map(p => [p.name, p]));

  // Find added parameters
  newParams.forEach(newParam => {
    if (!oldParamMap.has(newParam.name)) {
      changes.push({
        type: 'added',
        parameter: newParam
      });
    }
  });

  // Find removed parameters
  oldParams.forEach(oldParam => {
    if (!newParamMap.has(oldParam.name)) {
      changes.push({
        type: 'removed',
        parameter: oldParam
      });
    }
  });

  // Find modified parameters
  newParams.forEach(newParam => {
    const oldParam = oldParamMap.get(newParam.name);
    if (oldParam) {
      const paramChanges = [];

      if (oldParam.type !== newParam.type) {
        paramChanges.push(`type: ${oldParam.type} → ${newParam.type}`);
      }

      if (oldParam.required !== newParam.required) {
        paramChanges.push(`required: ${oldParam.required} → ${newParam.required}`);
      }

      if (oldParam.description !== newParam.description) {
        paramChanges.push('description changed');
      }

      if (paramChanges.length > 0) {
        changes.push({
          type: 'modified',
          parameter: newParam.name,
          changes: paramChanges
        });
      }
    }
  });

  return changes;
}

/**
 * Print diff summary
 * @param {Object} diff - Diff object
 */
function printDiffSummary(diff) {
  console.log(chalk.bold.blue('\n📊 API Diff Summary\n'));

  console.log(chalk.gray(`Version: ${diff.version.old} → ${diff.version.new}`));
  console.log(chalk.gray(`Date: ${diff.lastUpdated.old} → ${diff.lastUpdated.new}\n`));

  // Categories
  if (diff.added.categories.length > 0) {
    console.log(chalk.green(`✚ ${diff.added.categories.length} new categories:`));
    diff.added.categories.forEach(cat => {
      console.log(chalk.green(`  + ${cat.name}`));
    });
    console.log();
  }

  if (diff.removed.categories.length > 0) {
    console.log(chalk.red(`✖ ${diff.removed.categories.length} removed categories:`));
    diff.removed.categories.forEach(cat => {
      console.log(chalk.red(`  - ${cat.name}`));
    });
    console.log();
  }

  // Endpoints
  if (diff.added.endpoints.length > 0) {
    console.log(chalk.green(`✚ ${diff.added.endpoints.length} new endpoints:`));
    diff.added.endpoints.forEach(ep => {
      console.log(chalk.green(`  + [${ep.category}] ${ep.method} ${ep.path}`));
    });
    console.log();
  }

  if (diff.removed.endpoints.length > 0) {
    console.log(chalk.red(`✖ ${diff.removed.endpoints.length} removed endpoints:`));
    diff.removed.endpoints.forEach(ep => {
      console.log(chalk.red(`  - [${ep.category}] ${ep.method} ${ep.path}`));
    });
    console.log();
  }

  if (diff.modified.endpoints.length > 0) {
    console.log(chalk.yellow(`⚠ ${diff.modified.endpoints.length} modified endpoints:`));
    diff.modified.endpoints.forEach(ep => {
      console.log(chalk.yellow(`  ~ [${ep.category}] ${ep.endpoint}`));
      ep.changes.forEach(change => {
        console.log(chalk.gray(`    - ${change.field} changed`));
      });
    });
    console.log();
  }

  console.log(chalk.gray(`${diff.unchanged.endpoints.length} endpoints unchanged\n`));
}

/**
 * Main function
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log(chalk.yellow('\nUsage: node diff-api-specs.js <old-spec.json> <new-spec.json>\n'));
    console.log('Or use default naming convention:');
    console.log(chalk.gray('  node diff-api-specs.js 10.0.160 10.1.68\n'));
    process.exit(1);
  }

  let oldSpecPath = args[0];
  let newSpecPath = args[1];

  // Handle version shorthand
  if (!oldSpecPath.endsWith('.json')) {
    oldSpecPath = path.join(__dirname, `../scraped-api-spec-v${oldSpecPath}.json`);
  }

  if (!newSpecPath.endsWith('.json')) {
    newSpecPath = path.join(__dirname, `../scraped-api-spec-v${newSpecPath}.json`);
  }

  try {
    // Load specifications
    console.log(chalk.gray(`Loading ${path.basename(oldSpecPath)}...`));
    const oldSpec = JSON.parse(await fs.readFile(oldSpecPath, 'utf-8'));

    console.log(chalk.gray(`Loading ${path.basename(newSpecPath)}...`));
    const newSpec = JSON.parse(await fs.readFile(newSpecPath, 'utf-8'));

    // Compare
    console.log(chalk.gray('Comparing specifications...'));
    const diff = compareAPISpecs(oldSpec, newSpec);

    // Print summary
    printDiffSummary(diff);

    // Save diff to file
    const outputPath = path.join(
      __dirname,
      `../api-diff-v${diff.version.old}-to-v${diff.version.new}.json`
    );

    await fs.writeFile(outputPath, JSON.stringify(diff, null, 2));

    console.log(chalk.green(`✓ Diff saved to: ${path.basename(outputPath)}\n`));

  } catch (error) {
    console.error(chalk.red('\nError:'), error.message);
    process.exit(1);
  }
}

main();
