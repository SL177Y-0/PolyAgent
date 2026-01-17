import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// Load .env from parent directory
dotenv.config({ path: path.resolve(__dirname, '../.env') });

export default defineConfig({
    testDir: './e2e',
    fullyParallel: false, // Run tests sequentially for trading flow
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: 1, // Single worker for sequential trading tests
    reporter: 'html',

    // Global timeout for tests (5 minutes observation + buffer)
    timeout: 10 * 60 * 1000, // 10 minutes

    use: {
        baseURL: 'http://localhost:3000',
        trace: 'on-first-retry',
        video: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    // Run frontend dev server automatically if not running
    webServer: [
        {
            command: 'npm run dev',
            url: 'http://localhost:3000',
            reuseExistingServer: true,
            timeout: 60 * 1000,
        },
    ],
});
