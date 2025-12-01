/** Playwright config used when running tests from the frontend subpackage
 *  Points testDir to the repository tests/playwright folder so tests are
 *  discoverable even when tooling runs from app/frontend.
 */
module.exports = {
  testDir: './tests/playwright',
  // aumentar timeout global para pruebas E2E (ms)
  // tiempo mayor para navegaciones en runners lentos
  timeout: 120_000,
  reporter: [['list'], ['junit', { outputFile: 'test-results/results.xml' }]],
  retries: 1,
  // webServer: Playwright puede levantar el backend si no está activo.
  // reuseExistingServer=true evita intentar levantar otro proceso si ya hay uno.
  webServer: {
    command: 'python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000',
    port: 8000,
    timeout: 120_000,
    reuseExistingServer: true,
  },
};
