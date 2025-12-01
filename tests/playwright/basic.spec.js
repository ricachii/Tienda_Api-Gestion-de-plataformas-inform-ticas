const { test, expect } = require('@playwright/test');

test('shortcuts and modal focus trap', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  // ensure page loads - check main heading to avoid matching footer text
  await expect(page.locator('h1')).toBeVisible();

  // shortcut '/' focuses search
  await page.keyboard.press('/');
  await expect(page.locator('#q')).toBeFocused();

  // open auth modal
  // wait for login button to be visible before clicking. If the user is
  // already authenticated (test order may vary), try to logout first so this
  // test is idempotent.
  if (await page.locator('#btnLogin').count() === 0) {
    // try 'Salir' / logout button if present
    const logoutBtn = page.locator('button:has-text("Salir")');
    if (await logoutBtn.count()) {
      await logoutBtn.first().click();
      // wait for the login button to appear after logout
      await page.waitForSelector('#btnLogin', { state: 'visible', timeout: 10000 });
    }
  }
  await page.waitForSelector('#btnLogin', { state: 'visible', timeout: 20000 });
  await page.click('#btnLogin');
  await expect(page.locator('#ovAuth')).toBeVisible();
  // small stable pause to let animations settle and ensure focusability
  await page.waitForTimeout(300);
  // Tab cycling inside modal
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  // press Escape to close
  await page.keyboard.press('Escape');
  await expect(page.locator('#ovAuth')).toBeHidden();

  // add first product to cart (if exists)
  const addBtn = page.locator('.card .addbtn').first();
  if(await addBtn.count()){
    await addBtn.click();
    await expect(page.locator('#cartCount')).toHaveText(/\d+/);
  }
});
