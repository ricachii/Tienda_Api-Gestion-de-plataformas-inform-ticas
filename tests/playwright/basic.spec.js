const { test, expect } = require('@playwright/test');

test('shortcuts and modal focus trap', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/');
  // ensure page loads - check main heading to avoid matching footer text
  await expect(page.locator('h1')).toBeVisible();

  // shortcut '/' focuses search
  await page.keyboard.press('/');
  await expect(page.locator('#q')).toBeFocused();

  // open auth modal
  await page.click('#btnLogin');
  await expect(page.locator('#ovAuth')).toBeVisible();
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
