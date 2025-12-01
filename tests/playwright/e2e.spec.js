const { test, expect } = require('@playwright/test');

function rnd() { return Math.random().toString(36).slice(2,9); }

test('register -> login -> add to cart -> checkout flow', async ({ page }) => {
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  // ensure page loads - check main heading to avoid matching footer text
  await expect(page.locator('h1')).toBeVisible();

  // Open auth modal and register
  // wait for login button to be visible before clicking
  await page.waitForSelector('#btnLogin', { state: 'visible', timeout: 10000 });
  await page.click('#btnLogin');
  await expect(page.locator('#ovAuth')).toBeVisible();
  // Ensure modal inputs are visible before filling to avoid timing flakes
  await page.waitForSelector('#authEmail', { state: 'visible', timeout: 10000 });
  await page.waitForSelector('#authPass', { state: 'visible', timeout: 10000 });
  // The register name field lives inside a <details> (collapsed by default).
  // Open it before waiting for the input to avoid timing/visibility issues.
  await page.click('details summary');
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

  // Click confirm and wait for backend checkout response before asserting UI
  // success overlay. This avoids flakes when the client sends the request but
  // the UI doesn't immediately show the overlay.
  const [resp] = await Promise.all([
    page.waitForResponse(resp => /\/checkout$/.test(resp.url()) && resp.status() === 200, { timeout: 20000 }),
    page.click('#btnConfirmarResumen'),
  ]);
  // ensure server responded OK
  if (!resp || resp.status() !== 200) {
    throw new Error('Checkout request failed or did not return 200');
  }

  // Wait for success overlay
  await page.waitForSelector('#ovDone', { state: 'visible', timeout: 15000 });
  await expect(page.locator('#doneTotal')).not.toHaveText('—');
});
