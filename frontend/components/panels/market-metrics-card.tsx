
"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getApiClient, MarketMetrics } from "@/lib/api-client"
import { Activity, AlertCircle } from "lucide-react"

interface MarketMetricsCardProps {
  botId: string
  botStatus?: string
}

export function MarketMetricsCard({ botId, botStatus }: MarketMetricsCardProps) {
  const [metrics, setMetrics] = useState<MarketMetrics | null>(null)
  const api = getApiClient()

  const fetchMetrics = async () => {
    const data = await api.getMarketMetrics(botId)
    setMetrics(data)
  }

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 3000)
    return () => clearInterval(interval)
  }, [botId])

  // Show "Bot not running" state
  const isBotStopped = botStatus === "stopped" || metrics?.not_running

  if (!metrics) return null
  
  if (isBotStopped) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Market Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center h-[120px] text-muted-foreground">
          <AlertCircle className="h-6 w-6 mb-2 opacity-50" />
          <p className="text-xs">Start bot to view metrics</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Market Metrics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Best Bid</p>
            <p className="font-mono font-medium text-green-500">${metrics.best_bid.toFixed(3)}</p>
          </div>
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Best Ask</p>
            <p className="font-mono font-medium text-red-500">${metrics.best_ask.toFixed(3)}</p>
          </div>
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Spread</p>
            <p className="font-mono font-medium">{metrics.spread_pct.toFixed(2)}%</p>
          </div>
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs">Mid Price</p>
            <p className="font-mono font-medium">${metrics.mid_price.toFixed(3)}</p>
          </div>
          <div className="col-span-2 pt-2 border-t flex justify-between text-xs">
            <div>
              <span className="text-muted-foreground">Bid Liq: </span>
              <span className="font-mono">${metrics.bid_liquidity.toFixed(0)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Ask Liq: </span>
              <span className="font-mono">${metrics.ask_liquidity.toFixed(0)}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
