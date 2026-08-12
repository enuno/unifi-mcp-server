#!/usr/bin/env node
/**
 * Main scraper entry point
 * Orchestrates authentication, extraction, and parsing of UniFi API documentation
 */

import puppeteer from 'puppeteer';
import dotenv from 'dotenv';
import prompts from 'prompts';
import chalk from 'chalk';
import ora from 'ora';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

import { authenticateUniFi, clearSessionCookies } from './auth/unifi-login.js';
import { extractNavigationStructure } from './extractors/navigation-extractor.js';
import { extractAllEndpoints } from './extractors/endpoint-extractor.js';
import { APISpecification, parseNavigation, mergeEndpointDetails } from './parsers/api-spec-parser.js';
import { delay } from './utils/delay.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables
dotenv.config({ path: path.join(__dirname, '../.env') });

/**
 * Parse command line arguments
 */
function parseArgs() {
  const args = process.argv.slice(2);
  return {
    headed: args.includes('--headed'),
    debug: args.includes('--debug'),
    clearSession: args.includes('--clear-session'),
    version: args.find(arg => arg.startsWith('--version='))?.split('=')[1] || '10.1.68'
  };
}

/**
 * Get credentials from environment or prompt
 */
async function getCredentials() {
  let email = process.env.UNIFI_EMAIL;
  let password = process.env.UNIFI_PASSWORD;

  if (!email || !password) {
    console.log(chalk.yellow('\nUniFi account credentials required'));

    const response = await prompts([
      {
        type: 'text',
        name: 'email',
        message: 'UniFi email:',
        validate: value => value.includes('@') || 'Please enter a valid email'
      },
      {
        type: 'password',
        name: 'password',
        message: 'UniFi password:',
        validate: value => value.length > 0 || 'Password cannot be empty'
      }
    ]);

    email = response.email;
    password = response.password;

    if (!email || !password) {
      console.log(chalk.red('\nCredentials required. Exiting.'));
      process.exit(1);
    }
  }

  return { email, password };
}

/**
 * Main scraping function
 */
async function main() {
  const options = parseArgs();

  console.log(chalk.bold.blue('\n🔍 UniFi API Documentation Scraper\n'));
  console.log(chalk.gray(`Target version: ${options.version}\n`));

  // Clear session if requested
  if (options.clearSession) {
    console.log(chalk.yellow('Clearing saved session cookies...'));
    await clearSessionCookies();
  }

  // Get credentials
  const credentials = await getCredentials();

  let browser;
  let spinner = ora();

  try {
    // Launch browser
    spinner.start('Launching browser...');
    browser = await puppeteer.launch({
      headless: !options.headed,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage'
      ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    // Set user agent
    await page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    );

    spinner.succeed('Browser launched');

    // Authenticate
    spinner.start('Authenticating to UniFi portal...');
    await authenticateUniFi(page, credentials);
    spinner.succeed('Authentication successful');

    // Navigate to API docs
    spinner.start('Loading API documentation...');
    await page.goto('https://unifi.ui.com/settings/api-docs', {
      waitUntil: 'networkidle2',
      timeout: 30000
    });
    await delay(2000);
    spinner.succeed('API documentation loaded');

    // Extract navigation structure
    spinner.start('Extracting navigation structure...');
    const navigation = await extractNavigationStructure(page, { debug: options.debug });
    spinner.succeed(`Extracted ${navigation.categories.length} categories`);

    // Create API specification
    const apiSpec = new APISpecification();
    apiSpec.setVersion(options.version);

    // Parse navigation into categories
    parseNavigation(navigation, apiSpec);

    // Extract endpoint details
    console.log(chalk.bold('\nExtracting endpoint details:\n'));

    for (const category of navigation.categories) {
      spinner.start(`${category.name} (${category.endpoints.length} endpoints)`);

      const endpointDetails = await extractAllEndpoints(
        page,
        category.endpoints,
        { debug: options.debug }
      );

      mergeEndpointDetails(apiSpec, endpointDetails, category.name);

      spinner.succeed(
        `${category.name} (${endpointDetails.length}/${category.endpoints.length} extracted)`
      );
    }

    // Validate specification
    console.log(chalk.bold('\nValidating specification...\n'));
    const validation = apiSpec.validate();

    if (validation.issues.length > 0) {
      console.log(chalk.red('Issues found:'));
      validation.issues.forEach(issue => console.log(chalk.red(`  ✗ ${issue}`)));
    }

    if (validation.warnings.length > 0) {
      console.log(chalk.yellow('\nWarnings:'));
      validation.warnings.forEach(warning => console.log(chalk.yellow(`  ⚠ ${warning}`)));
    }

    if (validation.valid) {
      console.log(chalk.green('✓ Specification is valid'));
    }

    // Display statistics
    const stats = apiSpec.getStats();
    console.log(chalk.bold('\nStatistics:\n'));
    console.log(`  Total categories: ${stats.totalCategories}`);
    console.log(`  Total endpoints: ${stats.totalEndpoints}`);
    console.log('\n  Endpoints by method:');
    Object.entries(stats.endpointsByMethod).forEach(([method, count]) => {
      console.log(`    ${method}: ${count}`);
    });

    // Save to file
    const outputPath = path.join(__dirname, `../scraped-api-spec-v${options.version}.json`);
    await fs.writeFile(
      outputPath,
      JSON.stringify(apiSpec.toJSON(), null, 2)
    );

    console.log(chalk.green(`\n✓ Saved to: ${path.basename(outputPath)}\n`));

  } catch (error) {
    spinner.fail('Error occurred');
    console.error(chalk.red('\nError:'), error.message);

    if (options.debug) {
      console.error(chalk.gray('\nStack trace:'));
      console.error(chalk.gray(error.stack));
    }

    process.exit(1);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// Run main function
main().catch(error => {
  console.error(chalk.red('Fatal error:'), error);
  process.exit(1);
});
