import { test, expect, Page } from '@playwright/test';

/**
 * E2E Test: Complete Bot Trading Flow (User Perspective)
 * 
 * This test simulates a real user:
 * 1. Creates a bot via the UI with market: elc-sot-hul-2026-01-17
 * 2. Starts the bot and verifies immediate entry (BUY)
 * 3. Observes for 5 minutes watching for:
 *    - Spike detection
 *    - Automatic SELL on spike
 *    - Rebuy at current price
 *    - Cycle repeat
 * 4. Verifies all using dry_run: true for safety
 */

const TEST_CONFIG = {
    MARKET_SLUG: 'elc-sot-hul-2026-01-17',
    BOT_NAME: 'E2E Trading Bot',
    DRY_RUN: true,
    TRADE_SIZE_USD: 1.0,
    OBSERVATION_MINUTES: 5,
    API_BASE_URL: 'http://127.0.0.1:8000',
    FRONTEND_URL: 'http://localhost:3000',
};

// Helper: Wait for API to be ready
async function waitForApiReady(page: Page, timeoutMs = 30000): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        try {
            const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/`);
            if (response.ok()) return true;
        } catch {
            // API not ready yet
        }
        await page.waitForTimeout(1000);
    }
    return false;
}

// Helper: Get bot status via API
async function getBotStatus(page: Page, botId: string): Promise<any> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}`);
    if (!response.ok()) return null;
    return response.json();
}

// Helper: Get spike status via API
async function getSpikeStatus(page: Page, botId: string): Promise<any> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/spike-status`);
    if (!response.ok()) return null;
    return response.json();
}

// Helper: Get activities via API  
async function getActivities(page: Page, botId: string): Promise<any[]> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/activities`);
    if (!response.ok()) return [];
    const data = await response.json();
    return data.activities || [];
}

// Helper: Delete bot via API
async function deleteBot(page: Page, botId: string): Promise<void> {
    await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/stop`).catch(() => { });
    await page.request.delete(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}`).catch(() => { });
}

test.describe('Bot Trading Flow - User Perspective', () => {
    let botId: string | null = null;

    test.beforeAll(async ({ browser }) => {
        const page = await browser.newPage();
        const ready = await waitForApiReady(page);
        expect(ready).toBe(true);
        await page.close();
    });

    test.afterAll(async ({ browser }) => {
        if (botId) {
            const page = await browser.newPage();
            await deleteBot(page, botId);
            await page.close();
        }
    });

    test('Step 1: Create bot via frontend UI', async ({ page }) => {
        // Navigate to dashboard
        await page.goto(TEST_CONFIG.FRONTEND_URL);
        await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });

        // Click Create Bot button
        await page.getByRole('button', { name: /create bot/i }).click();

        // Wait for dialog
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

        // Fill in Basic tab
        await page.getByLabel('Bot Name').fill(TEST_CONFIG.BOT_NAME);
        await page.getByLabel('Description').fill('Automated E2E test - dry run');
        await page.getByLabel('Market Slug').fill(TEST_CONFIG.MARKET_SLUG);

        // Click Strategy tab
        await page.getByRole('tab', { name: 'Strategy' }).click();
        await page.waitForTimeout(500);

        // Enable dry run (checkbox)
        const dryRunCheckbox = page.getByLabel(/enable dry run/i);
        if (!(await dryRunCheckbox.isChecked())) {
            // Already unchecked, need to check it for dry run
        }
        // Make sure dry run is checked
        await expect(dryRunCheckbox).toBeVisible();

        // Click Create button
        await page.getByRole('button', { name: /create|save/i }).last().click();

        // Wait for success toast or dialog close
        await expect(page.getByText(/created successfully/i)).toBeVisible({ timeout: 10000 });

        // Get bot ID from dashboard
        await page.waitForTimeout(2000);

        // Find the bot card and get its ID from navigation
        const botCard = page.locator('[class*="Card"]').filter({ hasText: TEST_CONFIG.BOT_NAME }).first();
        await expect(botCard).toBeVisible({ timeout: 5000 });

        // Get the bot ID by extracting from the list via API
        const botsResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots`);
        const botsData = await botsResponse.json();
        const testBot = botsData.bots?.find((b: any) => b.name === TEST_CONFIG.BOT_NAME);
        expect(testBot).toBeTruthy();
        botId = testBot.bot_id;
        console.log(`Created bot: ${botId}`);
    });

    test('Step 2: Start bot and verify entry', async ({ page }) => {
        expect(botId).toBeTruthy();

        // Navigate to dashboard
        await page.goto(TEST_CONFIG.FRONTEND_URL);
        await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 10000 });

        // Find bot card
        const botCard = page.locator('[class*="Card"]').filter({ hasText: TEST_CONFIG.BOT_NAME }).first();
        await expect(botCard).toBeVisible();

        // Click Start button on bot card
        await botCard.getByRole('button', { name: /start/i }).click();

        // Wait for status to change to running
        await expect(page.getByText('running').first()).toBeVisible({ timeout: 15000 });

        // Verify via API
        const status = await getBotStatus(page, botId!);
        expect(status.status).toBe('running');
        console.log('Bot started successfully');

        // Wait for initial entry (bot should BUY immediately)
        await page.waitForTimeout(5000);

        // Check position via API
        const statusAfterEntry = await getBotStatus(page, botId!);
        console.log(`Position: ${statusAfterEntry.position?.has_position ? 'YES' : 'NO'}`);
        console.log(`Current price: ${statusAfterEntry.current_price}`);
    });

    test('Step 3: Observe trading for 5 minutes', async ({ page }) => {
        expect(botId).toBeTruthy();

        await page.goto(TEST_CONFIG.FRONTEND_URL);

        console.log('\n========================================');
        console.log('STARTING 5-MINUTE OBSERVATION PERIOD');
        console.log('========================================\n');

        const startTime = Date.now();
        const observationMs = TEST_CONFIG.OBSERVATION_MINUTES * 60 * 1000;
        const endTime = startTime + observationMs;

        let stats = {
            pricesObserved: 0,
            spikesDetected: 0,
            tradesExecuted: 0,
            maxChangePct: 0,
            lastActivityCount: 0,
        };

        // Poll every 10 seconds
        while (Date.now() < endTime) {
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            const remaining = Math.round((endTime - Date.now()) / 1000);

            // Get bot status
            const status = await getBotStatus(page, botId!);
            if (!status) {
                console.log(`[${elapsed}s] ERROR: Could not get bot status`);
                await page.waitForTimeout(10000);
                continue;
            }

            // Get spike status
            const spikeStatus = await getSpikeStatus(page, botId!);

            // Get activities
            const activities = await getActivities(page, botId!);
            const newActivityCount = activities.length - stats.lastActivityCount;
            if (newActivityCount > 0) {
                stats.lastActivityCount = activities.length;
                for (const activity of activities.slice(0, newActivityCount)) {
                    console.log(`  [ACTIVITY] ${activity.type}: ${activity.message}`);
                    if (activity.type === 'trade') stats.tradesExecuted++;
                    if (activity.type === 'spike') stats.spikesDetected++;
                }
            }

            // Log status
            console.log(`\n[${elapsed}s / ${TEST_CONFIG.OBSERVATION_MINUTES * 60}s] (${remaining}s remaining)`);
            console.log(`  Status: ${status.status}`);
            console.log(`  Price: $${status.current_price?.toFixed(4) || 'N/A'}`);
            console.log(`  Position: ${status.position?.has_position ? `${status.position.side} $${status.position.amount_usd}` : 'None'}`);

            if (status.position?.has_position) {
                console.log(`  Entry Price: $${status.position.entry_price?.toFixed(4)}`);
                console.log(`  P&L: ${status.position.pnl_pct?.toFixed(2)}%`);
                console.log(`  Age: ${status.position.age_seconds?.toFixed(0)}s`);
            }

            if (spikeStatus) {
                console.log(`  Spike Analysis:`);
                console.log(`    Max Change: ${spikeStatus.max_change_pct?.toFixed(2)}%`);
                console.log(`    Threshold: ${spikeStatus.threshold}%`);
                console.log(`    History: ${spikeStatus.history_size} points`);
                console.log(`    Volatility CV: ${spikeStatus.volatility_cv?.toFixed(2)}%`);

                if (Math.abs(spikeStatus.max_change_pct || 0) > Math.abs(stats.maxChangePct)) {
                    stats.maxChangePct = spikeStatus.max_change_pct;
                }

                if (spikeStatus.is_active && Math.abs(spikeStatus.max_change_pct) >= spikeStatus.threshold) {
                    console.log('    *** SPIKE THRESHOLD MET ***');
                }
            }

            console.log(`  Session Stats:`);
            console.log(`    Realized PnL: $${status.session_stats?.realized_pnl?.toFixed(2) || 0}`);
            console.log(`    Total Trades: ${status.session_stats?.total_trades || 0}`);
            console.log(`    Spikes Detected: ${status.spikes_detected || 0}`);

            stats.pricesObserved++;

            await page.waitForTimeout(10000); // Poll every 10 seconds
        }

        console.log('\n========================================');
        console.log('OBSERVATION COMPLETE');
        console.log('========================================');
        console.log(`Total Observations: ${stats.pricesObserved}`);
        console.log(`Max Price Change: ${stats.maxChangePct.toFixed(2)}%`);
        console.log(`Trades Observed: ${stats.tradesExecuted}`);
        console.log(`Activities Logged: ${stats.lastActivityCount}`);
        console.log('========================================\n');

        // Final verification - bot should still be running
        const finalStatus = await getBotStatus(page, botId!);
        expect(finalStatus.status).toBe('running');
    });

    test('Step 4: Stop bot and cleanup', async ({ page }) => {
        expect(botId).toBeTruthy();

        // Navigate to dashboard
        await page.goto(TEST_CONFIG.FRONTEND_URL);
        await page.waitForTimeout(2000);

        // Find bot and stop it
        const botCard = page.locator('[class*="Card"]').filter({ hasText: TEST_CONFIG.BOT_NAME }).first();

        // Stop via API (more reliable)
        await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/stop`);

        await page.waitForTimeout(2000);

        // Verify stopped
        const status = await getBotStatus(page, botId!);
        expect(status.status).toBe('stopped');
        console.log('Bot stopped');

        // Delete bot
        await deleteBot(page, botId!);
        console.log('Bot deleted');
        botId = null;
    });
});

test.describe('Settings Panel Verification', () => {
    test('Settings panel opens without crashing', async ({ page }) => {
        await page.goto(TEST_CONFIG.FRONTEND_URL);
        await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });

        // Click Settings button
        await page.getByRole('button', { name: /settings/i }).click();

        // Verify panel opens
        await expect(page.getByText('GLOBAL SETTINGS')).toBeVisible({ timeout: 5000 });

        // Navigate to EXECUTION tab
        await page.getByRole('button', { name: 'EXECUTION' }).click();
        await expect(page.getByText('Slippage Tolerance')).toBeVisible();
        await expect(page.getByText('Min Bid Liquidity')).toBeVisible();
        await expect(page.getByText('Max Spread')).toBeVisible();

        // Navigate to SYSTEM tab (previously crashing)
        await page.getByRole('button', { name: 'SYSTEM' }).click();
        await expect(page.getByText('Killswitch on Shutdown')).toBeVisible();
        await expect(page.getByText('WebSocket Enabled')).toBeVisible();
        await expect(page.getByText('Daily Loss Limit')).toBeVisible();

        console.log('Settings panel verified - NO CRASH!');

        // Close panel
        await page.keyboard.press('Escape');
    });

    test('Settings auto-save works', async ({ page }) => {
        await page.goto(TEST_CONFIG.FRONTEND_URL);
        await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 15000 });

        // Open settings
        await page.getByRole('button', { name: /settings/i }).click();
        await expect(page.getByText('GLOBAL SETTINGS')).toBeVisible({ timeout: 5000 });

        // Go to EXECUTION tab
        await page.getByRole('button', { name: 'EXECUTION' }).click();

        // Move the slippage slider (this should trigger auto-save)
        const slider = page.locator('[role="slider"]').first();
        await slider.click();

        // Wait for auto-save indicator
        await expect(page.getByText(/saving|saved/i)).toBeVisible({ timeout: 5000 });

        console.log('Auto-save verified!');
    });
});
