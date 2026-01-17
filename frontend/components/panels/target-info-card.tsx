
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TradeTarget } from "@/lib/types"
import { Target } from "lucide-react"

interface TargetInfoCardProps {
  target: TradeTarget | null
  currentPrice?: number
}

export function TargetInfoCard({ target, currentPrice = 0 }: TargetInfoCardProps) {
  if (!target) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Target className="h-4 w-4" /> Target Info
          </CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm py-6 text-center">
          No active target
        </CardContent>
      </Card>
    )
  }

  // Safe access with defaults
  const targetPrice = target.price ?? 0
  const safeCurrentPrice = currentPrice ?? 0
  
  const distance = safeCurrentPrice > 0 && targetPrice > 0
    ? ((safeCurrentPrice - targetPrice) / targetPrice * 100) 
    : 0
    
  const isClose = Math.abs(distance) < 1.0

  return (
    <Card className="h-full border-l-4 border-l-blue-500">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Target className="h-4 w-4 text-blue-500" />
          Active Target
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex justify-between items-end mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`font-bold ${target.action === "BUY" ? "text-green-500" : "text-red-500"}`}>
                {target.action || "BUY"}
              </span>
              <span className="text-muted-foreground">@</span>
              <span className="font-mono text-lg font-bold">${targetPrice.toFixed(3)}</span>
            </div>
            <p className="text-xs text-muted-foreground">{target.reason || "Target set"}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Current</p>
            <p className="font-mono font-medium">${safeCurrentPrice.toFixed(3)}</p>
          </div>
        </div>
        
        <div className="mt-3 pt-2 border-t flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Distance:</span>
          <span className={`font-mono font-medium ${isClose ? "text-yellow-500 animate-pulse" : ""}`}>
            {distance > 0 ? "+" : ""}{distance.toFixed(2)}%
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
