"use client"

import { Zap, TrendingUp, TrendingDown, Activity, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { SpikeDetection as SpikeDetectionType, SpikeWindow } from "@/lib/types"

interface SpikeDetectionProps {
  data: SpikeDetectionType
}

function windowLabelSeconds(sec: number): string {
  if (!sec) return "-"
  if (sec % 3600 === 0) return `${sec / 3600}h`
  if (sec % 60 === 0) return `${sec / 60}m`
  return `${sec}s`
}

export function SpikeDetection({ data }: SpikeDetectionProps) {
  const isActive = data.is_active

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-warning" />
            <span>SPIKE DETECTION</span>
          </div>
          <div className={cn("px-2 py-0.5 text-xs font-medium rounded", isActive ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground")}>
            {isActive ? "ACTIVE" : "STANDBY"}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="border border-border rounded overflow-hidden">
          <div className="grid grid-cols-4 gap-px bg-border text-xs">
            <div className="bg-card p-1.5 text-muted-foreground font-medium">WINDOW</div>
            <div className="bg-card p-1.5 text-muted-foreground font-medium">BASE</div>
            <div className="bg-card p-1.5 text-muted-foreground font-medium">CURRENT</div>
            <div className="bg-card p-1.5 text-muted-foreground font-medium">CHANGE</div>
          </div>

          {(!data.windows || data.windows.length === 0) ? (
            <div className="p-3 text-center text-xs text-muted-foreground">Collecting price data...</div>
          ) : (
            data.windows.map((w: SpikeWindow) => {
              const isUp = w.change_pct > 0
              return (
                <div key={w.window_sec} className="grid grid-cols-4 gap-px bg-border text-xs">
                  <div className="bg-background p-1.5 font-mono">{windowLabelSeconds(w.window_sec)}</div>
                  <div className="bg-background p-1.5 font-mono">${w.base_price.toFixed(4)}</div>
                  <div className="bg-background p-1.5 font-mono">${w.current_price.toFixed(4)}</div>
                  <div className={cn("bg-background p-1.5 font-mono flex items-center gap-1", isUp ? "text-primary" : "text-destructive")}>
                    {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {isUp ? "+" : ""}{w.change_pct.toFixed(2)}%
                  </div>
                </div>
              )
            })
          )}
        </div>

        <div className="flex items-center justify-between text-xs bg-secondary/50 p-2 rounded">
          <span className="text-muted-foreground">
            THRESHOLD: <span className="text-foreground font-mono">±{data.threshold.toFixed(1)}%</span>
          </span>
          <span className="text-muted-foreground">
            MAX: <span className={cn("font-mono", Math.abs(data.max_change_pct) >= data.threshold ? "text-warning" : "text-foreground")}>
              {data.max_change_pct >= 0 ? "+" : ""}{data.max_change_pct.toFixed(2)}% ({windowLabelSeconds(data.max_change_window_sec)})
            </span>
          </span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium">VOLATILITY</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">CV:</span>
            <span className="font-mono text-foreground">{data.volatility_cv.toFixed(2)}%</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Max CV:</span>
            <span className="font-mono text-foreground">{data.max_volatility_cv.toFixed(2)}%</span>
          </div>

          <div className={cn("flex items-center gap-2 px-2 py-1 text-xs rounded", data.is_volatility_filtered ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary")}>
            {data.is_volatility_filtered ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5" />
                HIGH VOLATILITY (filtered)
              </>
            ) : (
              <>
                <Activity className="w-3.5 h-3.5" />
                OK
              </>
            )}
          </div>
        </div>

        <div className="pt-2 border-t border-border">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">HISTORY BUFFER:</span>
            <span className="font-mono text-foreground">{data.history_size.toLocaleString()} / {data.max_history_size.toLocaleString()}</span>
          </div>
          <div className="h-1 bg-secondary mt-1 rounded">
            <div className="h-full bg-info rounded transition-all duration-300" style={{ width: `${Math.min((data.history_size / Math.max(data.max_history_size, 1)) * 100, 100)}%` }} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
