import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

test('session cookies are stored owner-only and symlinks are rejected', async () => {
  const tempDir = await fs.mkdtemp(path.join('/tmp', 'unifi-cookie-test-'));
  const cookiePath = path.join(tempDir, 'session-cookies.json');
  const previousUmask = process.umask(0o000);
  const moduleUrl = new URL('../scraper/auth/unifi-login.js', import.meta.url);
  moduleUrl.searchParams.set('test', Date.now().toString());
  const { clearSessionCookies, loadSessionCookies, saveSessionCookies } = await import(moduleUrl);

  try {
    await saveSessionCookies([{ name: 'session', value: 'dummy-test-value' }], cookiePath);
    const stat = await fs.lstat(cookiePath);
    assert.equal(stat.mode & 0o077, 0);
    assert.deepEqual(await loadSessionCookies(cookiePath), [
      { name: 'session', value: 'dummy-test-value' }
    ]);

    await fs.chmod(cookiePath, 0o644);
    assert.equal(await loadSessionCookies(cookiePath), null);
    await saveSessionCookies([{ name: 'session', value: 'replacement' }], cookiePath);
    const repairedStat = await fs.lstat(cookiePath);
    assert.equal(repairedStat.mode & 0o077, 0);

    await fs.unlink(cookiePath);
    await fs.symlink(path.join(tempDir, 'attacker-target'), cookiePath);
    await assert.rejects(
      saveSessionCookies([{ name: 'session', value: 'replacement' }], cookiePath),
      /symbolic link|symlink/i
    );
    assert.equal(await loadSessionCookies(cookiePath), null);
  } finally {
    process.umask(previousUmask);
    await clearSessionCookies(cookiePath);
    await fs.rm(tempDir, { recursive: true, force: true });
  }
});
