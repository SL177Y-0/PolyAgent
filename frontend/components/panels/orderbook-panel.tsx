
"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getApiClient, Orderbook } from "@/lib/api-client"
import { Loader2, AlertCircle } from "lucide-react"

interface OrderbookPanelProps {
  botId: string
  botStatus?: string
}

export function OrderbookPanel({ botId, botStatus }: OrderbookPanelProps) {
  const [orderbook, setOrderbook] = useState<Orderbook | null>(null)
  const [loading, setLoading] = useState(true)
  const api = getApiClient()

  const fetchOrderbook = async () => {
    const data = await api.getOrderbook(botId, 5) // Depth 5
    setOrderbook(data)
    setLoading(false)
  }

  useEffect(() => {
    fetchOrderbook()
    const interval = setInterval(fetchOrderbook, 2000) // 2s refresh
    return () => clearInterval(interval)
  }, [botId])

  // Show "Bot not running" state
  const isBotStopped = botStatus === "stopped" || orderbook?.not_running
  
  if (loading && !orderbook) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Orderbook</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[200px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  // Show stopped state
  if (isBotStopped || (orderbook?.bids.length === 0 && orderbook?.asks.length === 0)) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex justify-between">
            <span>Orderbook</span>
            <span className="text-xs text-muted-foreground font-normal">Spread: -</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center h-[180px] text-muted-foreground">
          <AlertCircle className="h-8 w-8 mb-2 opacity-50" />
          <p className="text-sm">Start bot to view orderbook</p>
        </CardContent>
      </Card>
    )
  }

  // Calculate max size for visual depth bars
  const maxSize = orderbook ? Math.max(
    ...orderbook.bids.map(b => b.size),
    ...orderbook.asks.map(a => a.size),
    1 // avoid div/0
  ) : 1

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex justify-between">
          <span>Orderbook</span>
          <span className="text-xs text-muted-foreground font-normal">
            Spread: {orderbook && orderbook.bids[0] && orderbook.asks[0] 
              ? `$${(orderbook.asks[0].price - orderbook.bids[0].price).toFixed(3)}` 
              : "-"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="flex flex-col text-xs">
          {/* Asks (Sell Orders) - Red, displayed descending */}
          <div className="flex flex-col-reverse">
            {orderbook?.asks.map((ask, i) => (
              <div key={`ask-${i}`} className="relative flex justify-between px-3 py-1 hover:bg-muted/50">
                <div 
                  className="absolute top-0 right-0 bottom-0 bg-red-500/10 transition-all duration-300"
                  style={{ width: `${(ask.size / maxSize) * 100}%` }}
                />
                <span className="text-red-500 font-mono z-10">{ask.price.toFixed(3)}</span>
                <span className="text-muted-foreground font-mono z-10">{ask.size.toFixed(0)}</span>
              </div>
            ))}
          </div>

          <div className="border-t border-border my-1" />

          {/* Bids (Buy Orders) - Green */}
          <div className="flex flex-col">
            {orderbook?.bids.map((bid, i) => (
              <div key={`bid-${i}`} className="relative flex justify-between px-3 py-1 hover:bg-muted/50">
                <div 
                  className="absolute top-0 right-0 bottom-0 bg-green-500/10 transition-all duration-300"
                  style={{ width: `${(bid.size / maxSize) * 100}%` }}
                />
                <span className="text-green-500 font-mono z-10">{bid.price.toFixed(3)}</span>
                <span className="text-muted-foreground font-mono z-10">{bid.size.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
