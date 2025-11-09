/** Local Playwright config for the frontend subpackage
 *  Ensures tests are discovered when running from `app/frontend`.
 */
module.exports = {
  testDir: '../../tests/playwright',
  timeout: 30_000,
  reporter: [['list'], ['junit', { outputFile: 'test-results/results.xml' }]],
  retries: 1,
};
