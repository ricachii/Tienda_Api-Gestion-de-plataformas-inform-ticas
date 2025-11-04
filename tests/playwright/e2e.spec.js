const { test, expect } = require('@playwright/test');

function rnd() { return Math.random().toString(36).slice(2,9); }

test('register -> login -> add to cart -> checkout flow', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/');
  await expect(page.locator('text=VitaZone')).toBeVisible();

  // Open auth modal and register
  await page.click('#btnLogin');
  await expect(page.locator('#ovAuth')).toBeVisible();
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
