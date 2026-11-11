const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({
  testDir:'./tests/visual',
  testMatch:'website-responsive.spec.cjs',
  timeout:90000,
  expect:{timeout:12000},
  reporter:'list',
  outputDir:'test-results/playwright',
  use:{browserName:'chromium',headless:true,baseURL:'http://127.0.0.1:4173',viewport:{width:1440,height:900},trace:'retain-on-failure'},
  webServer:{command:'node scripts/serve_assessment_site.cjs assessment-public',url:'http://127.0.0.1:4173/',reuseExistingServer:!process.env.CI,timeout:15000}
});
