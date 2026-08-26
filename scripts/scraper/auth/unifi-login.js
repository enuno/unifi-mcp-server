/**
 * UniFi Authentication Module
 * Handles authentication to the UniFi API documentation portal
 */

import fs from 'fs/promises';
import { constants as fsConstants } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { delay } from '../utils/delay.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const COOKIES_FILE = path.join(__dirname, '../../session-cookies.json');

async function rejectCookieSymlink(cookiesFile) {
  try {
    const stat = await fs.lstat(cookiesFile);
    if (stat.isSymbolicLink()) {
      throw new Error('Session cookie file must not be a symbolic link');
    }
    return stat;
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

// Configurable timeouts (can be overridden by environment variables)
const PASSKEY_TIMEOUT = parseInt(process.env.AUTH_PASSKEY_TIMEOUT || '120000'); // 2 minutes
const TWO_FA_TIMEOUT = parseInt(process.env.AUTH_2FA_TIMEOUT || '90000');       // 90 seconds
const PASSWORD_TIMEOUT = parseInt(process.env.AUTH_PASSWORD_TIMEOUT || '15000'); // 15 seconds

/**
 * Load existing session cookies if available
 * @returns {Promise<Array|null>} Cookies or null if not found
 */
export async function loadSessionCookies(cookiesFile = COOKIES_FILE) {
  let cookieFile;
  try {
    const flags = fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW || 0);
    cookieFile = await fs.open(cookiesFile, flags);
    const stat = await cookieFile.stat();
    if (!stat.isFile() || (stat.mode & 0o077) !== 0) {
      throw new Error('Session cookie file must have owner-only permissions');
    }
    const cookiesData = await cookieFile.readFile('utf-8');
    const cookies = JSON.parse(cookiesData);
    console.log('✓ Loaded existing session cookies');
    return cookies;
  } catch (error) {
    console.log('No existing session cookies found');
    return null;
  } finally {
    await cookieFile?.close();
  }
}

/**
 * Save session cookies to file
 * @param {Array} cookies - Browser cookies
 */
export async function saveSessionCookies(cookies, cookiesFile = COOKIES_FILE) {
  await rejectCookieSymlink(cookiesFile);
  const flags =
    fsConstants.O_WRONLY |
    fsConstants.O_CREAT |
    (fsConstants.O_NOFOLLOW || 0);
  let cookieFile;
  try {
    cookieFile = await fs.open(cookiesFile, flags, 0o600);
    await cookieFile.chmod(0o600);
    await cookieFile.truncate(0);
    await cookieFile.writeFile(JSON.stringify(cookies, null, 2), 'utf-8');
  } finally {
    await cookieFile?.close();
  }
  console.log('✓ Session cookies saved');
}

/**
 * Check if session cookies are still valid
 * @param {Page} page - Puppeteer page instance
 * @param {Array} cookies - Cookies to check
 * @returns {Promise<boolean>} True if cookies are valid
 */
export async function validateSessionCookies(page, cookies) {
  try {
    // Set cookies
    await page.setCookie(...cookies);

    // Navigate to API docs page
    await page.goto('https://unifi.ui.com/settings/api-docs', {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    // Wait a bit for redirects
    await delay(2000);

    // Check if we're still authenticated (not redirected to login)
    const currentUrl = page.url();

    if (currentUrl.includes('login') || currentUrl.includes('auth')) {
      console.log('Session cookies expired or invalid');
      return false;
    }

    console.log('✓ Session cookies are valid');
    return true;
  } catch (error) {
    console.error('Error validating cookies:', error.message);
    return false;
  }
}

/**
 * Perform interactive login to UniFi portal
 * @param {Page} page - Puppeteer page instance
 * @param {Object} credentials - {email, password}
 * @returns {Promise<Array>} Session cookies
 */
export async function performLogin(page, credentials) {
  console.log('Starting authentication process...');

  // Navigate to API docs (will redirect to login if not authenticated)
  await page.goto('https://unifi.ui.com/settings/api-docs', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  const currentUrl = page.url();

  // Check if already authenticated
  if (!currentUrl.includes('login') && !currentUrl.includes('auth')) {
    console.log('✓ Already authenticated');
    const cookies = await page.cookies();
    await saveSessionCookies(cookies);
    return cookies;
  }

  console.log('Authentication required...');

  // Wait for username/email input field (UniFi uses id="user")
  try {
    await page.waitForSelector('#user, input[autocomplete="username"], input[type="email"], input[name="email"]', {
      timeout: 10000
    });
  } catch (error) {
    throw new Error('Could not find username/email input field. Page structure may have changed.');
  }

  // Find and fill username/email field
  const emailSelector = await page.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input'));
    const emailInput = inputs.find(input =>
      input.id === 'user' ||
      input.autocomplete === 'username' ||
      input.type === 'email' ||
      input.name?.toLowerCase().includes('email') ||
      input.name?.toLowerCase().includes('user') ||
      input.placeholder?.toLowerCase().includes('email') ||
      input.ariaLabel?.toLowerCase().includes('user')
    );
    if (!emailInput) return null;

    // Create unique selector
    if (emailInput.id) return `#${emailInput.id}`;
    if (emailInput.autocomplete === 'username') return 'input[autocomplete="username"]';
    if (emailInput.name) return `input[name="${emailInput.name}"]`;
    return 'input[type="email"]';
  });

  if (!emailSelector) {
    throw new Error('Could not determine username/email input selector');
  }

  // Fill in email/username
  await page.type(emailSelector, credentials.email);
  console.log('✓ Email/username entered');

  // Wait a moment for the page to react
  await delay(1000);

  // Click continue/forward button (required before password/passkey prompt appears)
  // Try multiple strategies to click the button
  let buttonClicked = false;

  // Strategy 1: Find and click button directly in page context
  try {
    const clicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'));

      // Look for button with arrow icon or continue text
      const continueBtn = buttons.find(btn => {
        const text = btn.textContent?.toLowerCase() || '';
        const ariaLabel = btn.getAttribute('aria-label')?.toLowerCase() || '';
        const svg = btn.querySelector('svg');

        return text.includes('continue') ||
               text.includes('next') ||
               ariaLabel.includes('continue') ||
               ariaLabel.includes('next') ||
               svg !== null; // Has an icon (likely the arrow)
      });

      if (continueBtn) {
        continueBtn.click();
        return true;
      }
      return false;
    });

    if (clicked) {
      buttonClicked = true;
      console.log('✓ Continue button clicked');
      await delay(3000); // Wait for next screen to load
    }
  } catch (error) {
    console.log('Strategy 1 failed:', error.message);
  }

  // Strategy 2: Try clicking submit button if Strategy 1 failed
  if (!buttonClicked) {
    try {
      await page.click('button[type="submit"]', { timeout: 2000 });
      buttonClicked = true;
      console.log('✓ Submit button clicked');
      await delay(3000);
    } catch (error) {
      // Try next strategy
    }
  }

  // Strategy 3: Press Enter key as fallback
  if (!buttonClicked) {
    try {
      await page.keyboard.press('Enter');
      buttonClicked = true;
      console.log('✓ Enter key pressed');
      await delay(3000);
    } catch (error) {
      console.log('⚠️  Could not submit form, proceeding anyway...');
      await delay(2000);
    }
  }

  // Wait and detect which auth method appears: passkey OR password
  // Check multiple times as the page may still be loading
  let hasPasskey = false;
  let hasPassword = false;
  let authType = null;
  let alreadyAuthenticated = false;

  console.log('Detecting authentication method...');

  for (let i = 0; i < 10; i++) { // Check for up to 10 seconds
    // Check if we've already navigated away from login (fast passkey completion)
    const currentUrl = page.url();
    if (!currentUrl.includes('login') && !currentUrl.includes('auth')) {
      console.log('✓ Already authenticated (navigated away from login)');
      alreadyAuthenticated = true;
      break;
    }

    try {
      // Check for passkey prompt
      hasPasskey = await page.evaluate(() => {
        const text = document.body.textContent?.toLowerCase() || '';
        return text.includes('passkey') ||
               text.includes('security key') ||
               text.includes('authenticator') ||
               text.includes('biometric') ||
               text.includes('touch id') ||
               text.includes('face id') ||
               text.includes('use your passkey');
      }).catch(err => {
        // Navigation error means page changed - likely successful auth
        if (err.message.includes('Execution context was destroyed')) {
          return false; // Will check URL in next iteration
        }
        throw err;
      });

      // Check for password field
      hasPassword = await page.evaluate(() => {
        const passwordInput = document.querySelector('input[type="password"]');
        return passwordInput !== null && passwordInput.offsetParent !== null; // Visible
      }).catch(err => {
        // Navigation error means page changed - likely successful auth
        if (err.message.includes('Execution context was destroyed')) {
          return false; // Will check URL in next iteration
        }
        throw err;
      });

      if (hasPasskey) {
        authType = 'passkey';
        break;
      } else if (hasPassword) {
        authType = 'password';
        break;
      }
    } catch (error) {
      // If execution context was destroyed, check if we've navigated away
      if (error.message.includes('Execution context was destroyed')) {
        console.log('Page navigated during detection, checking if authenticated...');
        await delay(1000);
        const urlAfterNav = page.url();
        if (!urlAfterNav.includes('login') && !urlAfterNav.includes('auth')) {
          console.log('✓ Authentication successful (navigation detected)');
          alreadyAuthenticated = true;
          break;
        }
      } else {
        throw error;
      }
    }

    await delay(1000); // Wait 1 second before checking again
  }

  // If already authenticated, skip the auth flow entirely
  if (alreadyAuthenticated) {
    console.log('✓ Skipping auth flow - already logged in');
    // Jump to the end where we navigate to API docs
  } else if (!authType) {
    console.warn('⚠️  Could not detect auth method, assuming passkey...');
    authType = 'passkey';
    hasPasskey = true;
  } else {
    console.log(`✓ Detected authentication method: ${authType}`);
  }

  if (!alreadyAuthenticated && authType === 'passkey') {
    console.warn('\n🔑 Passkey/WebAuthn authentication detected!');
    console.warn('Please complete passkey authentication in the browser window.');
    console.warn('This may include:');
    console.warn('  - Touch ID / Face ID');
    console.warn('  - Security key (YubiKey, etc.)');
    console.warn('  - Phone/device confirmation');
    console.warn(`\nWaiting up to ${PASSKEY_TIMEOUT / 1000} seconds for completion...\n`);

    // Wait for user to complete passkey auth
    // Check every 5 seconds if authentication succeeded
    let authenticated = false;
    const maxIterations = Math.ceil(PASSKEY_TIMEOUT / 5000);
    for (let i = 0; i < maxIterations; i++) {
      await delay(5000);

      const currentUrl = page.url();
      if (!currentUrl.includes('login') && !currentUrl.includes('auth')) {
        authenticated = true;
        console.log('✓ Passkey authentication successful');
        break;
      }
    }

    if (!authenticated) {
      throw new Error('Passkey authentication timed out. Please try again.');
    }
  } else if (authType === 'password') {
    // Traditional password flow
    // Password field should already be visible since we detected it
    try {
      // Fill in password
      await page.type('input[type="password"]', credentials.password);
      console.log('✓ Password entered');

      // Find and click submit button
      const submitButton = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'));
        const submitBtn = buttons.find(btn =>
          btn.type === 'submit' ||
          btn.textContent?.toLowerCase().includes('sign in') ||
          btn.textContent?.toLowerCase().includes('log in') ||
          btn.textContent?.toLowerCase().includes('continue')
        );
        if (!submitBtn) return null;

        // Create unique selector
        if (submitBtn.id) return `#${submitBtn.id}`;
        if (submitBtn.className) return `.${submitBtn.className.split(' ').join('.')}`;
        return 'button[type="submit"]';
      });

      if (!submitButton) {
        throw new Error('Could not find submit button');
      }

      // Click submit
      await page.click(submitButton);
      console.log('✓ Login submitted');

      // Wait for navigation after login
      await page.waitForNavigation({
        waitUntil: 'networkidle2',
        timeout: 30000
      }).catch(() => {
        console.log('Navigation timeout - checking if login succeeded anyway');
      });
    } catch (error) {
      if (error.message.includes('waiting for selector')) {
        throw new Error('Could not find password field. If using passkeys, run in headed mode.');
      }
      throw error;
    }
  }

  // Check if login succeeded (skip if already authenticated during detection)
  if (!alreadyAuthenticated) {
    const finalUrl = page.url();
    if (finalUrl.includes('login') || finalUrl.includes('auth')) {
      throw new Error('Login failed - still on login page. Check credentials.');
    }
  }

  // Handle potential 2FA or additional verification (skip if passkey was used or already authenticated)
  if (!alreadyAuthenticated && !hasPasskey) {
    await delay(3000);

    // Check for traditional 2FA prompts (SMS, authenticator app codes)
    const has2FA = await page.evaluate(() => {
      const text = document.body.textContent?.toLowerCase() || '';
      return (text.includes('verification code') ||
              text.includes('two-factor') ||
              text.includes('2fa') ||
              text.includes('enter code') ||
              text.includes('authenticator app')) &&
             !text.includes('passkey'); // Exclude passkey-related text
    });

    if (has2FA) {
      console.warn('\n⚠️  Two-factor authentication detected!');
      console.warn('Please enter your verification code in the browser window.');
      console.warn(`Waiting up to ${TWO_FA_TIMEOUT / 1000} seconds for completion...\n`);

      // Wait for user to complete 2FA, checking every 5 seconds
      let twoFAComplete = false;
      const maxIterations = Math.ceil(TWO_FA_TIMEOUT / 5000);
      for (let i = 0; i < maxIterations; i++) {
        await delay(5000);

        const currentUrl = page.url();
        if (!currentUrl.includes('verification') && !currentUrl.includes('2fa')) {
          twoFAComplete = true;
          console.log('✓ 2FA completed');
          break;
        }
      }

      if (!twoFAComplete) {
        console.warn('⚠️  2FA timeout - continuing anyway...');
      }
    }
  }

  // Navigate to API docs to confirm access
  await page.goto('https://unifi.ui.com/settings/api-docs', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  const cookies = await page.cookies();
  await saveSessionCookies(cookies);

  console.log('✓ Authentication successful');
  return cookies;
}

/**
 * Authenticate to UniFi portal with session management
 * @param {Page} page - Puppeteer page instance
 * @param {Object} credentials - {email, password}
 * @returns {Promise<Array>} Session cookies
 */
export async function authenticateUniFi(page, credentials) {
  // Try to load existing cookies
  const existingCookies = await loadSessionCookies();

  if (existingCookies && existingCookies.length > 0) {
    // Validate existing cookies
    const isValid = await validateSessionCookies(page, existingCookies);

    if (isValid) {
      return existingCookies;
    }
  }

  // Perform fresh login
  return await performLogin(page, credentials);
}

/**
 * Clear saved session cookies
 */
export async function clearSessionCookies(cookiesFile = COOKIES_FILE) {
  try {
    await fs.unlink(cookiesFile);
    console.log('✓ Session cookies cleared');
  } catch (error) {
    // File doesn't exist, nothing to clear
  }
}
