"use client"

import { TrendingUp, TrendingDown, Trophy, Target } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { SessionStats as SessionStatsType } from "@/lib/types"

interface SessionStatsProps {
  stats: SessionStatsType
}

export function SessionStats({ stats }: SessionStatsProps) {
  const pnlPositive = (stats.realized_pnl ?? 0) >= 0
  const totalTrades = stats.total_trades ?? 0
  const winningTrades = stats.winning_trades ?? 0
  const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide">SESSION PERFORMANCE</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className={cn("p-2 rounded", pnlPositive ? "bg-primary/10" : "bg-destructive/10")}>
          <span className="text-xs text-muted-foreground block mb-1">REALIZED P&L</span>
          <div className="flex items-center gap-2">
            {pnlPositive ? (
              <TrendingUp className="w-4 h-4 text-primary" />
            ) : (
              <TrendingDown className="w-4 h-4 text-destructive" />
            )}
            <span className={cn("text-xl font-mono font-bold", pnlPositive ? "text-primary" : "text-destructive")}>
              {pnlPositive ? "+" : ""}${(stats.realized_pnl ?? 0).toFixed(2)}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <StatBox icon={<Trophy className="w-3.5 h-3.5" />} label="TOTAL TRADES" value={totalTrades.toString()} />
          <StatBox
            icon={<Target className="w-3.5 h-3.5" />}
            label="WIN RATE"
            value={`${winRate.toFixed(1)}%`}
            highlight={winRate >= 50}
          />
        </div>

        <div className="pt-2 border-t border-border text-xs text-muted-foreground flex justify-between">
          <span className="font-mono">{winningTrades}W</span>
          <span className="font-mono">{Math.max(totalTrades - winningTrades, 0)}L</span>
        </div>
      </CardContent>
    </Card>
  )
}

function StatBox({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className="bg-secondary/50 p-2 rounded">
      <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
        {icon}
        <span className="text-[10px]">{label}</span>
      </div>
      <span className={cn("text-lg font-mono font-semibold", highlight ? "text-primary" : "text-foreground")}>
        {value}
      </span>
    </div>
  )
}
