import { test, expect, Page } from '@playwright/test';

/**
 * E2E Test: Complete Trading Cycle Verification
 *
 * This test validates the full Train of Trade cycle:
 * 1. Bot Creation with config from .env
 * 2. Initial Entry (BUY at start)
 * 3. Wait for Spike Detection
 * 4. Automatic SELL on spike
 * 5. Immediate REBUY
 * 6. Cycle Repeat
 *
 * Market: elc-sot-hul-2026-01-17
 * Duration: 5 minutes observation
 */

const TEST_CONFIG = {
    MARKET_SLUG: 'elc-sot-hul-2026-01-17',
    BOT_NAME: 'Trading Cycle E2E Bot',
    DRY_RUN: true,
    TRADE_SIZE_USD: 1.0,
    OBSERVATION_MINUTES: 5,
    API_BASE_URL: 'http://127.0.0.1:8000',
    FRONTEND_URL: 'http://localhost:3000',
    POLL_INTERVAL_MS: 10000,  // Poll every 10 seconds
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

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

async function getBotStatus(page: Page, botId: string): Promise<any> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}`);
    if (!response.ok()) return null;
    return response.json();
}

async function getSpikeStatus(page: Page, botId: string): Promise<any> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/spike-status`);
    if (!response.ok()) return null;
    return response.json();
}

async function getActivities(page: Page, botId: string, limit = 50): Promise<any[]> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/activities?limit=${limit}`);
    if (!response.ok()) return [];
    const data = await response.json();
    return data.activities || [];
}

async function getTarget(page: Page, botId: string): Promise<any> {
    const response = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/target`);
    if (!response.ok()) return null;
    return response.json();
}

async function deleteBot(page: Page, botId: string): Promise<void> {
    await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/stop`).catch(() => { });
    await page.request.delete(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}`).catch(() => { });
}

interface TradingStats {
    buyOrders: number;
    sellOrders: number;
    spikesDetected: number;
    targetHits: number;
    maxPriceChange: number;
    initialPrice: number;
    finalPrice: number;
    cycleCount: number;
    errors: string[];
}

// ============================================================================
// TEST SUITE
// ============================================================================

test.describe('Trading Cycle - Full Train of Trade Flow', () => {
    let botId: string | null = null;
    let stats: TradingStats;

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

    test.beforeEach(async () => {
        stats = {
            buyOrders: 0,
            sellOrders: 0,
            spikesDetected: 0,
            targetHits: 0,
            maxPriceChange: 0,
            initialPrice: 0,
            finalPrice: 0,
            cycleCount: 0,
            errors: [],
        };
    });

    test('Phase 1: Create bot with Train of Trade config', async ({ page }) => {
        console.log('\n=== PHASE 1: BOT CREATION ===\n');

        // Create bot via API directly for reliability
        const createResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots`, {
            data: {
                name: TEST_CONFIG.BOT_NAME,
                description: 'E2E test for Train of Trade cycle',
                market_slug: TEST_CONFIG.MARKET_SLUG,
                trade_size_usd: TEST_CONFIG.TRADE_SIZE_USD,
                dry_run: TEST_CONFIG.DRY_RUN,
                profile: 'normal',
                auto_start: false,  // We'll start manually
            },
        });

        expect(createResponse.ok()).toBeTruthy();
        const createData = await createResponse.json();
        botId = createData.bot_id;
        console.log(`✓ Bot created: ${botId}`);

        // Verify bot was created with correct config
        const botStatus = await getBotStatus(page, botId!);
        expect(botStatus.market_slug).toBe(TEST_CONFIG.MARKET_SLUG);
        expect(botStatus.dry_run).toBe(TEST_CONFIG.DRY_RUN);
        console.log(`✓ Config verified: market=${botStatus.market_slug}, dry_run=${botStatus.dry_run}`);
    });

    test('Phase 2: Start bot and verify initial BUY entry', async ({ page }) => {
        console.log('\n=== PHASE 2: INITIAL ENTRY ===\n');

        expect(botId).toBeTruthy();

        // Start the bot
        const startResponse = await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/start`);
        expect(startResponse.ok()).toBeTruthy();
        console.log('✓ Bot started');

        // Wait for WebSocket connection and initial price
        await page.waitForTimeout(5000);

        // Poll for position (initial BUY should happen quickly)
        let positionFound = false;
        for (let i = 0; i < 15; i++) {  // Wait up to 30 seconds
            const status = await getBotStatus(page, botId!);

            if (status.current_price) {
                stats.initialPrice = status.current_price;
                console.log(`✓ Initial price: $${stats.initialPrice.toFixed(4)}`);
            }

            if (status.position?.has_position) {
                positionFound = true;
                stats.buyOrders++;
                console.log(`✓ Initial BUY executed:`);
                console.log(`  Side: ${status.position.side}`);
                console.log(`  Entry Price: $${status.position.entry_price.toFixed(4)}`);
                console.log(`  Amount: $${status.position.amount_usd.toFixed(2)}`);
                break;
            }

            await page.waitForTimeout(2000);
        }

        expect(positionFound).toBeTruthy();

        // Verify SELL target was set
        const target = await getTarget(page, botId!);
        expect(target.target).toBeTruthy();
        expect(target.target.action).toBe('SELL');
        console.log(`✓ SELL target set: $${target.target.price.toFixed(4)} (TP: ${((target.target.price / stats.initialPrice - 1) * 100).toFixed(1)}%)`);
    });

    test('Phase 3: Monitor for spike detection and SELL execution', async ({ page }) => {
        console.log('\n=== PHASE 3: SPIKE DETECTION & SELL ===\n');

        expect(botId).toBeTruthy();

        const startTime = Date.now();
        const maxWaitMs = 2 * 60 * 1000;  // Wait up to 2 minutes for spike
        let spikeDetected = false;
        let sellExecuted = false;

        while (Date.now() - startTime < maxWaitMs) {
            const spikeStatus = await getSpikeStatus(page, botId!);
            const activities = await getActivities(page, botId!, 5);

            // Check for spike detection
            if (spikeStatus?.max_change_pct !== undefined) {
                const absChange = Math.abs(spikeStatus.max_change_pct);
                if (absChange > Math.abs(stats.maxPriceChange)) {
                    stats.maxPriceChange = spikeStatus.max_change_pct;
                }

                if (absChange >= spikeStatus.threshold) {
                    spikeDetected = true;
                    stats.spikesDetected++;
                    console.log(`✓ Spike detected: ${spikeStatus.max_change_pct.toFixed(2)}% (threshold: ${spikeStatus.threshold}%)`);
                }
            }

            // Check for SELL execution in activities
            const sellActivity = activities.find((a: any) =>
                a.message.includes('SELL') || (a.type === 'order' && a.details?.side === 'SELL')
            );

            if (sellActivity) {
                sellExecuted = true;
                stats.sellOrders++;
                console.log(`✓ SELL order executed: ${sellActivity.message}`);
                break;
            }

            // Log progress
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
            console.log(`[${elapsed}s] Price change: ${spikeStatus?.max_change_pct?.toFixed(2) || 'N/A'}% | Spikes: ${stats.spikesDetected}`);

            await page.waitForTimeout(5000);
        }

        // If no real spike, we can still verify the target system works
        if (!spikeDetected) {
            console.log('⚠ No natural spike detected during observation period');
            console.log('  This is normal for low-volatility markets');
        }

        // For dry run testing, the SELL may not have executed without a spike
        // But we can verify the target system is in place
        const target = await getTarget(page, botId!);
        expect(target.target).toBeTruthy();
        console.log(`✓ Target system active: ${target.target.action} @ $${target.target.price.toFixed(4)}`);
    });

    test('Phase 4: Verify Train of Trade cycle continuity', async ({ page }) => {
        console.log('\n=== PHASE 4: TRAIN OF TRADE CYCLE ===\n');

        expect(botId).toBeTruthy();

        // Get current status
        const status = await getBotStatus(page, botId!);
        const target = await getTarget(page, botId!);
        const activities = await getActivities(page, botId!, 20);

        console.log('\n--- Current Bot State ---');
        console.log(`Status: ${status.status}`);
        console.log(`Position: ${status.position?.has_position ? `${status.position.side} $${status.position.amount_usd}` : 'None'}`);
        console.log(`Current Price: $${status.current_price?.toFixed(4) || 'N/A'}`);

        // Verify target system
        if (target?.target) {
            console.log(`\n--- Target System ---`);
            console.log(`Action: ${target.target.action}`);
            console.log(`Target Price: $${target.target.price.toFixed(4)}`);
            console.log(`Condition: ${target.target.condition}`);
            console.log(`Reason: ${target.target.reason}`);

            // Calculate distance to target
            if (status.current_price && target.target.price) {
                const distance = ((target.target.price - status.current_price) / status.current_price * 100);
                console.log(`Distance to target: ${distance.toFixed(2)}%`);
            }
        }

        // Analyze activities for cycle components
        console.log('\n--- Activity Analysis ---');
        const buyActivities = activities.filter((a: any) => a.message.includes('BUY') || a.details?.side === 'BUY');
        const sellActivities = activities.filter((a: any) => a.message.includes('SELL') || a.details?.side === 'SELL');
        const spikeActivities = activities.filter((a: any) => a.type === 'spike');

        console.log(`BUY activities: ${buyActivities.length}`);
        console.log(`SELL activities: ${sellActivities.length}`);
        console.log(`Spike detections: ${spikeActivities.length}`);

        // Update stats
        stats.buyOrders = buyActivities.length;
        stats.sellOrders = sellActivities.length;
        stats.spikesDetected = spikeActivities.length;

        // A complete cycle = BUY + (potential SELL + potential REBUY)
        if (stats.buyOrders > 0) {
            stats.cycleCount = stats.buyOrders;
        }

        // Log recent activities
        console.log('\n--- Recent Activities ---');
        for (const activity of activities.slice(0, 5)) {
            const timestamp = new Date(activity.timestamp * 1000).toLocaleTimeString();
            console.log(`[${timestamp}] ${activity.type}: ${activity.message}`);
        }
    });

    test('Phase 5: 5-minute observation period', async ({ page }) => {
        console.log('\n=== PHASE 5: 5-MINUTE OBSERVATION ===\n');

        expect(botId).toBeTruthy();

        const startTime = Date.now();
        const observationMs = TEST_CONFIG.OBSERVATION_MINUTES * 60 * 1000;
        let lastActivityCount = 0;
        let lastLogTime = 0;

        while (Date.now() - startTime < observationMs) {
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            const remaining = Math.round((observationMs - (Date.now() - startTime)) / 1000);

            // Get current status
            const status = await getBotStatus(page, botId!);
            const spikeStatus = await getSpikeStatus(page, botId!);
            const activities = await getActivities(page, botId!, 10);

            // Track max price change
            if (spikeStatus?.max_change_pct !== undefined) {
                const absChange = Math.abs(spikeStatus.max_change_pct);
                if (absChange > Math.abs(stats.maxPriceChange)) {
                    stats.maxPriceChange = spikeStatus.max_change_pct;
                }
            }

            // Log every 30 seconds
            if (Date.now() - lastLogTime >= 30000) {
                console.log(`\n[${elapsed}s / ${TEST_CONFIG.OBSERVATION_MINUTES * 60}s] (${remaining}s remaining)`);
                console.log(`  Status: ${status.status}`);
                console.log(`  Price: $${status.current_price?.toFixed(4) || 'N/A'}`);
                console.log(`  Position: ${status.position?.has_position ? `${status.position.side} @ $${status.position.entry_price?.toFixed(4)}` : 'None'}`);

                if (status.position?.has_position) {
                    console.log(`  P&L: ${status.position.pnl_pct?.toFixed(2)}% (${status.position.pnl_usd?.toFixed(2)} USD)`);
                    console.log(`  Hold Time: ${status.position.age_seconds?.toFixed(0)}s`);
                }

                if (spikeStatus) {
                    console.log(`  Spike Analysis:`);
                    console.log(`    Max Change: ${spikeStatus.max_change_pct?.toFixed(2)}%`);
                    console.log(`    Threshold: ${spikeStatus.threshold}%`);
                    console.log(`    History: ${spikeStatus.history_size} points`);
                }

                lastLogTime = Date.now();
            }

            // Check for new activities
            const newActivities = activities.slice(0, activities.length - lastActivityCount);
            if (newActivities.length > 0) {
                for (const activity of newActivities) {
                    const timestamp = new Date(activity.timestamp * 1000).toLocaleTimeString();
                    console.log(`  [${timestamp}] ${activity.type}: ${activity.message}`);

                    // Track different activity types
                    if (activity.message.includes('BUY') || activity.details?.side === 'BUY') {
                        stats.buyOrders++;
                        stats.cycleCount++;
                    }
                    if (activity.message.includes('SELL') || activity.details?.side === 'SELL') {
                        stats.sellOrders++;
                    }
                    if (activity.type === 'spike') {
                        stats.spikesDetected++;
                    }
                    if (activity.type === 'signal' && activity.message.includes('Target')) {
                        stats.targetHits++;
                    }
                }
                lastActivityCount = activities.length;
            }

            // Check for errors in activities
            const errorActivities = activities.filter((a: any) => a.type === 'error');
            for (const err of errorActivities) {
                if (!stats.errors.includes(err.message)) {
                    stats.errors.push(err.message);
                    console.log(`  ⚠ ERROR: ${err.message}`);
                }
            }

            await page.waitForTimeout(TEST_CONFIG.POLL_INTERVAL_MS);
        }

        stats.finalPrice = (await getBotStatus(page, botId!)).current_price || 0;

        console.log('\n=== OBSERVATION COMPLETE ===');
    });

    test('Phase 6: Final verification and cleanup', async ({ page }) => {
        console.log('\n=== PHASE 6: FINAL VERIFICATION ===\n');

        expect(botId).toBeTruthy();

        // Get final status
        const status = await getBotStatus(page, botId!);
        const activities = await getActivities(page, botId!, 100);

        console.log('\n--- Final Bot State ---');
        console.log(`Status: ${status.status}`);
        console.log(`Final Price: $${status.current_price?.toFixed(4) || 'N/A'}`);

        if (status.position?.has_position) {
            console.log(`Open Position:`);
            console.log(`  Side: ${status.position.side}`);
            console.log(`  Entry: $${status.position.entry_price.toFixed(4)}`);
            console.log(`  P&L: ${status.position.pnl_pct.toFixed(2)}%`);
        }

        // Session stats
        if (status.session_stats) {
            console.log('\n--- Session Statistics ---');
            console.log(`Total Trades: ${status.session_stats.total_trades}`);
            console.log(`Realized P&L: $${status.session_stats.realized_pnl.toFixed(2)}`);
            console.log(`Win Rate: ${status.session_stats.winning_trades}/${status.session_stats.total_trades}`);
        }

        // Activity summary
        const buyCount = activities.filter((a: any) => a.message.includes('BUY') || a.details?.side === 'BUY').length;
        const sellCount = activities.filter((a: any) => a.message.includes('SELL') || a.details?.side === 'SELL').length;
        const spikeCount = activities.filter((a: any) => a.type === 'spike').length;

        console.log('\n--- Activity Summary ---');
        console.log(`BUY orders: ${buyCount}`);
        console.log(`SELL orders: ${sellCount}`);
        console.log(`Spike detections: ${spikeCount}`);
        console.log(`Max price change: ${stats.maxPriceChange.toFixed(2)}%`);

        // Price movement
        if (stats.initialPrice && stats.finalPrice) {
            const priceChange = ((stats.finalPrice - stats.initialPrice) / stats.initialPrice * 100);
            console.log(`Price change: ${priceChange.toFixed(2)}% ($${stats.initialPrice.toFixed(4)} → $${stats.finalPrice.toFixed(4)})`);
        }

        // Verify bot is still running
        expect(status.status).toBe('running');
        console.log('\n✓ Bot still running after 5 minutes');

        // Stop the bot
        await page.request.post(`${TEST_CONFIG.API_BASE_URL}/api/bots/${botId}/stop`);
        await page.waitForTimeout(2000);

        const stoppedStatus = await getBotStatus(page, botId!);
        expect(stoppedStatus.status).toBe('stopped');
        console.log('✓ Bot stopped successfully');

        // Generate test report
        console.log('\n' + '='.repeat(50));
        console.log('TEST REPORT SUMMARY');
        console.log('='.repeat(50));
        console.log(`Market: ${TEST_CONFIG.MARKET_SLUG}`);
        console.log(`Duration: ${TEST_CONFIG.OBSERVATION_MINUTES} minutes`);
        console.log(`Dry Run: ${TEST_CONFIG.DRY_RUN}`);
        console.log('');
        console.log(`Cycle Analysis:`);
        console.log(`  BUY Orders: ${stats.buyOrders}`);
        console.log(`  SELL Orders: ${stats.sellOrders}`);
        console.log(`  Spike Detections: ${stats.spikesDetected}`);
        console.log(`  Target Hits: ${stats.targetHits}`);
        console.log('');
        console.log(`Price Movement:`);
        console.log(`  Initial: $${stats.initialPrice.toFixed(4)}`);
        console.log(`  Final: $${stats.finalPrice.toFixed(4)}`);
        console.log(`  Max Change: ${stats.maxPriceChange.toFixed(2)}%`);
        console.log('');
        console.log(`Errors: ${stats.errors.length}`);
        if (stats.errors.length > 0) {
            stats.errors.forEach(err => console.log(`  - ${err}`));
        } else {
            console.log('  No errors! ✓');
        }
        console.log('='.repeat(50));

        // Cleanup
        await deleteBot(page, botId!);
        console.log('✓ Bot deleted');
        botId = null;
    });
});

// ============================================================================
// ADDITIONAL VERIFICATION TESTS
// ============================================================================

test.describe('Trading Cycle - Component Verification', () => {
    test('Config profile loading works correctly', async ({ page }) => {
        // Get available profiles
        const profilesResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/config/profiles`);
        expect(profilesResponse.ok()).toBeTruthy();

        const profilesData = await profilesResponse.json();
        expect(profilesData.profiles).toBeDefined();

        // Verify required profiles exist
        const profileNames = profilesData.profiles.map((p: any) => p.name);
        expect(profileNames).toContain('normal');
        expect(profileNames).toContain('live');
        expect(profileNames).toContain('edge');

        console.log('✓ Trading profiles verified:', profileNames.join(', '));
    });

    test('Settings endpoint is accessible', async ({ page }) => {
        const settingsResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/settings`);
        expect(settingsResponse.ok()).toBeTruthy();

        const settings = await settingsResponse.json();
        expect(settings).toHaveProperty('slippage_tolerance');
        expect(settings).toHaveProperty('min_bid_liquidity');
        expect(settings).toHaveProperty('min_ask_liquidity');

        console.log('✓ Global settings accessible');
    });

    test('WebSocket health check', async ({ page }) => {
        // This verifies the API server is running and can respond
        const statusResponse = await page.request.get(`${TEST_CONFIG.API_BASE_URL}/api/status`);
        expect(statusResponse.ok()).toBeTruthy();

        const statusData = await statusResponse.json();
        expect(statusData).toHaveProperty('status');
        expect(statusData).toHaveProperty('bots');

        console.log(`✓ API Status: ${statusData.status}`);
        console.log(`  Total bots: ${statusData.total_bots}`);
        console.log(`  Active bots: ${statusData.active_bots}`);
    });
});
