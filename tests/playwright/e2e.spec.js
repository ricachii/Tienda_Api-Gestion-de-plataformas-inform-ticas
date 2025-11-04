const { test, expect } = require('@playwright/test');

function rnd() { return Math.random().toString(36).slice(2,9); }

test('register -> login -> add to cart -> checkout flow', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/');
  // ensure page loads - check main heading to avoid matching footer text
  await expect(page.locator('h1')).toBeVisible();

  // Open auth modal and register
  await page.click('#btnLogin');
  await expect(page.locator('#ovAuth')).toBeVisible();
  // Ensure modal inputs are visible before filling to avoid timing flakes
  await page.waitForSelector('#authEmail', { state: 'visible', timeout: 10000 });
  await page.waitForSelector('#authPass', { state: 'visible', timeout: 10000 });
  await page.waitForSelector('#authName', { state: 'visible', timeout: 10000 });

  const email = `e2e+${rnd()}@example.com`;
  const name = `E2E ${rnd()}`;
  await page.fill('#authEmail', email);
  await page.fill('#authPass', 'Password123!');
  await page.fill('#authName', name);
  await page.click('#btnDoRegister');
  // wait for success alert
  await page.waitForTimeout(600);

  // Now login
  await page.fill('#authEmail', email);
  await page.fill('#authPass', 'Password123!');
  await page.click('#btnDoLogin');
  await page.waitForTimeout(800);
  await expect(page.locator('#whoami')).toHaveText(new RegExp(name.split(' ')[0]));

  // Add first product if available
  const addBtn = page.locator('.card .addbtn').first();
  await expect(addBtn).toBeVisible();
  await addBtn.click();
  await expect(page.locator('#cartCount')).toHaveText(/\d+/);

  // Open summary and perform checkout
  await page.click('#resumen');
  await expect(page.locator('#ovSummary')).toBeVisible();
  await page.fill('#inpNombre', name);
  await page.fill('#inpEmail', email);
  await page.click('#btnConfirmarResumen');

  // Wait for success overlay
  await page.waitForSelector('#ovDone', { state: 'visible', timeout: 5000 });
  await expect(page.locator('#doneTotal')).not.toHaveText('—');
});
