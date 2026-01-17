"use client"

import { useRef, useEffect, useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { PricePoint, Trade, Position, TradeTarget } from "@/lib/types"

interface PriceChartProps {
  priceHistory: PricePoint[]
  trades: Trade[]
  position: Position | null
  target?: TradeTarget | null
}

// Timeframe windows in milliseconds
const TIMEFRAME_MS: Record<string, number> = {
  "1m": 60 * 1000,
  "5m": 5 * 60 * 1000,
  "15m": 15 * 60 * 1000,
  "1h": 60 * 60 * 1000,
}

export function PriceChart({ priceHistory, trades, position, target }: PriceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [timeframe, setTimeframe] = useState<"1m" | "5m" | "15m" | "1h">("5m")
  const [hoveredPoint, setHoveredPoint] = useState<PricePoint | null>(null)

  // Filter price history based on selected timeframe
  const filteredHistory = useMemo(() => {
    if (priceHistory.length === 0) return []
    
    const now = Date.now()
    const cutoffTime = now - TIMEFRAME_MS[timeframe]
    
    // Filter points within the timeframe window
    const filtered = priceHistory.filter(p => p.time >= cutoffTime)
    
    // If we have very few points, show all available data (better UX)
    if (filtered.length < 2 && priceHistory.length >= 2) {
      return priceHistory.slice(-Math.min(priceHistory.length, 50))
    }
    
    return filtered
  }, [priceHistory, timeframe])

  // Filter trades within the timeframe
  const filteredTrades = useMemo(() => {
    if (trades.length === 0 || filteredHistory.length === 0) return []
    
    const minTime = filteredHistory[0]?.time || 0
    return trades.filter(t => t.timestamp >= minTime)
  }, [trades, filteredHistory])

  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Set canvas size
    const rect = container.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    canvas.style.width = `${rect.width}px`
    canvas.style.height = `${rect.height}px`
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height
    const padding = { top: 20, right: 60, bottom: 30, left: 10 }

    // Clear canvas
    ctx.fillStyle = "oklch(0.08 0.01 270)"
    ctx.fillRect(0, 0, width, height)

    if (filteredHistory.length < 2) {
      // Draw "waiting for data" message
      ctx.fillStyle = "oklch(0.6 0 0)"
      ctx.font = "12px 'Space Grotesk', sans-serif"
      ctx.textAlign = "center"
      ctx.fillText("Waiting for price data...", width / 2, height / 2)
      ctx.font = "10px 'Space Grotesk', sans-serif"
      ctx.fillText(`(${timeframe} window)`, width / 2, height / 2 + 16)
      return
    }

    // Calculate bounds
    const prices = filteredHistory.map((p) => p.price)
    const minPrice = Math.min(...prices) * 0.998
    const maxPrice = Math.max(...prices) * 1.002
    const priceRange = maxPrice - minPrice

    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    // Scale functions
    const scaleX = (i: number) => padding.left + (i / (filteredHistory.length - 1)) * chartWidth
    const scaleY = (price: number) => padding.top + chartHeight - ((price - minPrice) / priceRange) * chartHeight

    // Draw grid lines
    ctx.strokeStyle = "oklch(0.18 0.01 270)"
    ctx.lineWidth = 1
    const gridLines = 5
    for (let i = 0; i <= gridLines; i++) {
      const y = padding.top + (i / gridLines) * chartHeight
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(width - padding.right, y)
      ctx.stroke()

      // Price labels
      const price = maxPrice - (i / gridLines) * priceRange
      ctx.fillStyle = "oklch(0.5 0 0)"
      ctx.font = "10px 'JetBrains Mono', monospace"
      ctx.textAlign = "right"
      ctx.fillText(`$${price.toFixed(4)}`, width - 5, y + 3)
    }

    // Draw price line
    ctx.beginPath()
    ctx.moveTo(scaleX(0), scaleY(filteredHistory[0].price))

    for (let i = 1; i < filteredHistory.length; i++) {
      ctx.lineTo(scaleX(i), scaleY(filteredHistory[i].price))
    }

    ctx.strokeStyle = "oklch(0.7 0.15 220)"
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Draw area fill
    ctx.lineTo(scaleX(filteredHistory.length - 1), height - padding.bottom)
    ctx.lineTo(scaleX(0), height - padding.bottom)
    ctx.closePath()

    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom)
    gradient.addColorStop(0, "oklch(0.7 0.15 220 / 0.3)")
    gradient.addColorStop(1, "oklch(0.7 0.15 220 / 0)")
    ctx.fillStyle = gradient
    ctx.fill()

    // Draw spike markers
    filteredHistory.forEach((point, i) => {
      if (point.spike) {
        const x = scaleX(i)
        const isUp = point.spike === "up"

        ctx.strokeStyle = isUp ? "oklch(0.6 0.25 25 / 0.5)" : "oklch(0.85 0.25 145 / 0.5)"
        ctx.lineWidth = 1
        ctx.setLineDash([2, 2])
        ctx.beginPath()
        ctx.moveTo(x, padding.top)
        ctx.lineTo(x, height - padding.bottom)
        ctx.stroke()
        ctx.setLineDash([])
      }
    })

    // Draw trade markers
    filteredTrades.forEach((trade) => {
      const index = filteredHistory.findIndex((p) => p.time >= trade.timestamp)
      if (index === -1) return

      const x = scaleX(index)
      const y = scaleY(trade.price)

      ctx.beginPath()
      ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fillStyle = trade.side === "BUY" ? "oklch(0.85 0.25 145)" : "oklch(0.6 0.25 25)"
      ctx.fill()
      ctx.strokeStyle = "oklch(0.08 0.01 270)"
      ctx.lineWidth = 2
      ctx.stroke()
    })

    // Draw current price marker
    if (filteredHistory.length > 0) {
      const lastPrice = filteredHistory[filteredHistory.length - 1].price
      const y = scaleY(lastPrice)

      ctx.fillStyle = "oklch(0.7 0.15 220)"
      ctx.beginPath()
      ctx.arc(width - padding.right, y, 4, 0, Math.PI * 2)
      ctx.fill()
    }

    // Draw position entry line if exists
    if (position) {
      const entryY = scaleY(position.entry_price)
      ctx.strokeStyle = position.side === "BUY" ? "oklch(0.85 0.25 145 / 0.7)" : "oklch(0.6 0.25 25 / 0.7)"
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(padding.left, entryY)
      ctx.lineTo(width - padding.right, entryY)
      ctx.stroke()
      ctx.setLineDash([])

      // Entry label
      ctx.fillStyle = position.side === "BUY" ? "oklch(0.85 0.25 145)" : "oklch(0.6 0.25 25)"
      ctx.font = "9px 'Space Grotesk', sans-serif"
      ctx.textAlign = "left"
      ctx.fillText("ENTRY", padding.left + 5, entryY - 5)
    }

    // Draw target price line if exists (Train of Trade strategy)
    if (target && target.price > 0) {
      // Check if target price is within visible range
      const targetInRange = target.price >= minPrice && target.price <= maxPrice
      
      if (targetInRange) {
        const targetY = scaleY(target.price)
        const isBuyTarget = target.action === "BUY"
        
        // Draw target line with distinct style (dotted, gold/orange color)
        ctx.strokeStyle = isBuyTarget ? "oklch(0.75 0.18 85 / 0.9)" : "oklch(0.65 0.2 30 / 0.9)"
        ctx.lineWidth = 1.5
        ctx.setLineDash([2, 3])
        ctx.beginPath()
        ctx.moveTo(padding.left, targetY)
        ctx.lineTo(width - padding.right, targetY)
        ctx.stroke()
        ctx.setLineDash([])

        // Target label with background
        const labelText = `TARGET ${target.action} @ $${target.price.toFixed(4)}`
        ctx.font = "9px 'Space Grotesk', sans-serif"
        const textWidth = ctx.measureText(labelText).width
        
        // Draw label background
        ctx.fillStyle = isBuyTarget ? "oklch(0.75 0.18 85 / 0.2)" : "oklch(0.65 0.2 30 / 0.2)"
        ctx.fillRect(width - padding.right - textWidth - 10, targetY - 12, textWidth + 8, 14)
        
        // Draw label text
        ctx.fillStyle = isBuyTarget ? "oklch(0.75 0.18 85)" : "oklch(0.65 0.2 30)"
        ctx.textAlign = "right"
        ctx.fillText(labelText, width - padding.right - 5, targetY - 2)
      }
    }

    // Draw time labels at bottom
    if (filteredHistory.length >= 2) {
      ctx.fillStyle = "oklch(0.5 0 0)"
      ctx.font = "9px 'JetBrains Mono', monospace"
      ctx.textAlign = "center"
      
      // Start time
      const startTime = new Date(filteredHistory[0].time)
      ctx.fillText(startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), padding.left, height - 5)
      
      // End time
      const endTime = new Date(filteredHistory[filteredHistory.length - 1].time)
      ctx.fillText(endTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), width - padding.right, height - 5)
    }
  }, [filteredHistory, filteredTrades, position, target, timeframe])

  // Get current price for display
  const currentPrice = filteredHistory.length > 0 ? filteredHistory[filteredHistory.length - 1].price : 0

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-4">
          <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide">PRICE CHART</CardTitle>
          <span className="text-xs text-muted-foreground">·</span>
          <span className="text-sm font-mono text-foreground">${currentPrice.toFixed(4)}</span>
          <span className="text-xs text-muted-foreground">·</span>
          <span className="text-xs text-muted-foreground">{filteredHistory.length} pts</span>
        </div>
        <div className="flex gap-1">
          {(["1m", "5m", "15m", "1h"] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={cn(
                "px-2 py-1 text-xs font-medium transition-colors rounded",
                timeframe === tf
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent",
              )}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>
      </CardHeader>

      {/* Chart Canvas */}
      <CardContent className="flex-1 p-0">
        <div ref={containerRef} className="h-full w-full relative">
          <canvas ref={canvasRef} className="absolute inset-0" />
        </div>
      </CardContent>
    </Card>
  )
}
