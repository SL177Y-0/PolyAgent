
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BotStatus } from "@/lib/types"
import { Activity, ArrowUpRight, ArrowDownRight, Wallet } from "lucide-react"

interface DashboardSummaryProps {
  bots: BotStatus[]
}

export function DashboardSummary({ bots }: DashboardSummaryProps) {
  // Calculate aggregate stats
  const totalPnl = bots.reduce((sum, bot) => sum + (bot.session_stats?.realized_pnl || 0), 0)
  const activeBots = bots.filter(b => b.status === "running").length
  const totalTrades = bots.reduce((sum, bot) => sum + (bot.session_stats?.total_trades || 0), 0)
  const totalBalance = bots.reduce((sum, bot) => sum + (bot.usdc_balance || 0), 0)
  
  // Calculate aggregate win rate
  const totalWins = bots.reduce((sum, bot) => sum + (bot.session_stats?.winning_trades || 0), 0)
  const winRate = totalTrades > 0 ? (totalWins / totalTrades) * 100 : 0

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
          {totalPnl >= 0 ? (
            <ArrowUpRight className="h-4 w-4 text-green-500" />
          ) : (
            <ArrowDownRight className="h-4 w-4 text-red-500" />
          )}
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${totalPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
            ${Math.abs(totalPnl).toFixed(2)}
          </div>
          <p className="text-xs text-muted-foreground">
            Across {bots.length} bots
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Active Bots</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{activeBots} / {bots.length}</div>
          <p className="text-xs text-muted-foreground">
            Running sessions
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
          <div className="h-4 w-4 text-muted-foreground">%</div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{winRate.toFixed(1)}%</div>
          <p className="text-xs text-muted-foreground">
            {totalWins} wins / {totalTrades} trades
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
          <Wallet className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">${totalBalance.toFixed(2)}</div>
          <p className="text-xs text-muted-foreground">
            USDC Available
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
