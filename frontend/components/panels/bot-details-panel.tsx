"use client"

import { Bot, Activity, TrendingUp, Clock, Wallet, Target, ShieldAlert, Zap } from "lucide-react"
import { cn } from "@/lib/utils"
import type { BotStatus } from "@/lib/api-client"

interface BotDetailsPanelProps {
  bot: BotStatus | null
}

export function BotDetailsPanel({ bot }: BotDetailsPanelProps) {
  if (!bot) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <Bot className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Select a Bot</p>
          <p className="text-sm mt-2">Choose a bot from the list to view details</p>
        </div>
      </div>
    )
  }

  const isRunning = bot.status === "running"
  const hasPosition = bot.position?.has_position

  return (
    <div className="h-full p-4 overflow-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{bot.name}</h2>
          <p className="text-sm text-muted-foreground mt-1">{bot.description || "No description"}</p>
        </div>
        <div className={cn(
          "px-2 py-1 text-xs font-medium rounded",
          isRunning ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
        )}>
          {bot.status.toUpperCase()}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Wallet */}
        <div className="p-3 bg-secondary/50 rounded-md">
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">WALLET</span>
          </div>
          <p className="text-sm font-mono text-foreground truncate" title={bot.wallet_address}>
            {bot.wallet_address.slice(0, 10)}...{bot.wallet_address.slice(-6)}
          </p>
          <p className="text-lg font-mono font-semibold text-primary mt-1">
            ${bot.usdc_balance.toFixed(2)}
          </p>
        </div>

        {/* Uptime */}
        <div className="p-3 bg-secondary/50 rounded-md">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">UPTIME</span>
          </div>
          <p className="text-lg font-mono font-semibold text-foreground">
            {formatUptime(bot.uptime_seconds || 0)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {bot.dry_run ? "DRY RUN" : "LIVE"}
          </p>
        </div>

        {/* Session Stats */}
        <div className="p-3 bg-secondary/50 rounded-md">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">SESSION P&L</span>
          </div>
          <p className={cn(
            "text-lg font-mono font-semibold",
            (bot.session_stats?.realized_pnl || 0) >= 0 ? "text-primary" : "text-destructive"
          )}>
            {(bot.session_stats?.realized_pnl || 0) >= 0 ? "+" : ""}
            ${(bot.session_stats?.realized_pnl || 0).toFixed(2)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {bot.session_stats?.total_trades || 0} trades
          </p>
        </div>

        {/* Win Rate */}
        <div className="p-3 bg-secondary/50 rounded-md">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">WIN RATE</span>
          </div>
          <p className="text-lg font-mono font-semibold text-foreground">
            {calculateWinRate(bot)}%
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {bot.session_stats?.winning_trades || 0} / {bot.session_stats?.total_trades || 0}
          </p>
        </div>
      </div>

      {/* Current Position */}
      {hasPosition && bot.position && (
        <div className="mb-6">
          <h3 className="text-xs text-muted-foreground font-medium tracking-wide mb-3">CURRENT POSITION</h3>
          <div className={cn(
            "p-4 rounded-md",
            bot.position.side === "BUY" ? "bg-primary/10" : "bg-destructive/10"
          )}>
            <div className="flex items-center justify-between mb-3">
              <span className={cn(
                "px-2 py-1 text-xs font-bold rounded",
                bot.position.side === "BUY" ? "bg-primary/20 text-primary" : "bg-destructive/20 text-destructive"
              )}>
                {bot.position.side === "BUY" ? "LONG" : "SHORT"}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatTime(bot.position.age_seconds || 0)} held
              </span>
            </div>
            
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <span className="text-xs text-muted-foreground block">Entry</span>
                <span className="text-sm font-mono font-semibold">${bot.position.entry_price?.toFixed(4)}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Current</span>
                <span className="text-sm font-mono font-semibold">${bot.position.current_price?.toFixed(4)}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Size</span>
                <span className="text-sm font-mono font-semibold">${bot.position.amount_usd?.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">P&L</span>
                <span className={cn(
                  "text-sm font-mono font-semibold",
                  (bot.position.pnl_pct || 0) >= 0 ? "text-primary" : "text-destructive"
                )}>
                  {(bot.position.pnl_pct || 0) >= 0 ? "+" : ""}{bot.position.pnl_pct?.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Strategy Settings */}
      <div className="mb-6">
        <h3 className="text-xs text-muted-foreground font-medium tracking-wide mb-3">STRATEGY SETTINGS</h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Spike Threshold</span>
            </div>
            <span className="text-xs font-mono text-foreground">{bot.spike_threshold_pct || 8}%</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <div className="flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs text-muted-foreground">Take Profit</span>
            </div>
            <span className="text-xs font-mono text-primary">+{bot.take_profit_pct || 3}%</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-destructive" />
              <span className="text-xs text-muted-foreground">Stop Loss</span>
            </div>
            <span className="text-xs font-mono text-destructive">-{bot.stop_loss_pct || 2.5}%</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-secondary/30 rounded">
            <div className="flex items-center gap-2">
              <Wallet className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Trade Size</span>
            </div>
            <span className="text-xs font-mono text-foreground">${bot.trade_size_usd || 1}</span>
          </div>
        </div>
      </div>

      {/* Market Info */}
      {bot.token_id && (
        <div>
          <h3 className="text-xs text-muted-foreground font-medium tracking-wide mb-3">MARKET</h3>
          <div className="p-3 bg-secondary/30 rounded-md">
            <p className="text-sm text-foreground mb-1">{bot.market_slug || "Unknown Market"}</p>
            <code className="text-xs font-mono text-muted-foreground break-all">
              {bot.token_id}
            </code>
          </div>
        </div>
      )}

      {/* Error Display */}
      {bot.error && (
        <div className="mt-4 p-3 bg-destructive/10 rounded-md">
          <h3 className="text-xs text-destructive font-medium mb-1">ERROR</h3>
          <p className="text-xs text-destructive">{bot.error}</p>
        </div>
      )}
    </div>
  )
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

function calculateWinRate(bot: BotStatus): string {
  const total = bot.session_stats?.total_trades || 0
  const wins = bot.session_stats?.winning_trades || 0
  if (total === 0) return "0"
  return ((wins / total) * 100).toFixed(0)
}
