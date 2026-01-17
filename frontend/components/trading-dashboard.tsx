
"use client"

import { useState } from "react"
import { toast } from "sonner"
import { useBotState } from "@/hooks/use-bot-state"
import { PositionCard } from "@/components/panels/position-card"
import { SessionStats } from "@/components/panels/session-stats"
import { PriceChart } from "@/components/panels/price-chart"
import { SpikeDetection } from "@/components/panels/spike-detection"
import { ActivityFeed } from "@/components/panels/activity-feed"
import { SettingsPanel } from "@/components/settings-panel"
import { OrderbookPanel } from "@/components/panels/orderbook-panel"
import { TargetInfoCard } from "@/components/panels/target-info-card"
import { BotControls } from "@/components/panels/bot-controls"
import { getApiClient } from "@/lib/api-client"

export function TradingDashboard() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { selectedBotId, position, sessionStats, spikeDetection, priceHistory, target, activities, bots, refresh } = useBotState()
  const api = getApiClient()

  if (!selectedBotId) return null

  const currentBot = bots.find(b => b.bot_id === selectedBotId)
  
  const handleClosePosition = async () => {
    try {
      const res = await api.closePosition(selectedBotId)
      if (res.success) {
        toast.success("Position closed")
        refresh()
      } else {
        toast.error(res.error || "Failed to close position")
      }
    } catch (err) {
      toast.error("Failed to close position")
    }
  }

  const handleManualTrade = async (side: "BUY" | "SELL", amount: number) => {
    try {
      const res = await api.trade(selectedBotId, side, amount)
      if (res.success) {
        toast.success(`${side} order executed`)
        refresh()
      } else {
        toast.error(res.error || "Trade failed")
      }
    } catch (err) {
      toast.error("Trade failed")
    }
  }

  return (
    <div className="flex-1 p-4 overflow-auto">
      <div className="space-y-4">
        
        {/* Row 1: Position + Session Stats + Target Info (3 columns on desktop) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <PositionCard
            position={position}
            target={target}
            currentPrice={currentBot?.current_price || position.current_price || 0}
            onClosePosition={handleClosePosition}
            onManualBuy={() => handleManualTrade("BUY", currentBot?.trade_size_usd || 1)}
            onManualSell={() => handleManualTrade("SELL", currentBot?.trade_size_usd || 1)}
            tradeSizeUsd={currentBot?.trade_size_usd || 1}
          />
          <SessionStats stats={sessionStats} />
          <TargetInfoCard target={target} currentPrice={currentBot?.current_price || position.current_price || 0} />
        </div>

        {/* Row 2: Price Chart (left 2/3) + Orderbook (right 1/3) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 min-h-[350px]">
            <PriceChart priceHistory={priceHistory} trades={[]} position={position} target={target} />
          </div>
          <div className="min-h-[350px]">
            <OrderbookPanel botId={selectedBotId} botStatus={currentBot?.status} />
          </div>
        </div>

        {/* Row 3: Spike Detection + Bot Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <SpikeDetection data={spikeDetection} />
          </div>
          <div>
            {currentBot && (
              <BotControls 
                botId={selectedBotId} 
                status={currentBot.status} 
                onUpdate={refresh}
                onSettingsClick={() => setSettingsOpen(true)}
              />
            )}
          </div>
        </div>

        {/* Row 4: Activity Feed (full width) */}
        <div className="min-h-[250px]">
          <ActivityFeed activities={activities} />
        </div>

      </div>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        config={{
          slippageTolerance: 0.06,
          minBidLiquidity: 5,
          minAskLiquidity: 5,
          maxSpreadPct: 1,
          wssEnabled: true,
          wssReconnectDelay: 1,
          killswitchOnShutdown: true,
          logLevel: "INFO",
        }}
      />
    </div>
  )
}
