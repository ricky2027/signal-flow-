import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: '.', testMatch: '*.spec.ts', timeout: 30000, fullyParallel: false, workers: 1, use: { baseURL: process.env.SIGNALFLOW_TEST_BASE_URL || 'http://localhost:3000', headless: true, trace: 'retain-on-failure' }, reporter: [['list'], ['html', { open: 'never' }]] });
