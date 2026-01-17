"use client"

import { useState, useEffect } from "react"
import { Settings, Power, Wallet, Activity, AlertTriangle, ArrowLeft, OctagonAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ThemeToggle } from "@/components/theme-toggle"
import type { BotStatus } from "@/lib/types"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

type BotState = {
  connectionStatus: { websocket: boolean; rest: boolean }
  wallet: { address: string; usdcBalance: number }
  status: "running" | "stopped" | "paused" | "error"
  uptime: number
  market: { name: string }
  selectedBotId?: string | null
  bots?: BotStatus[]
}

interface HeaderBarProps {
  /**
   * Optional legacy/compat prop. When not provided, HeaderBar derives wallet/status from currentBot.
   */
  botState?: BotState
  currentBot?: BotStatus
  onSettingsClick?: () => void
  onMarketClick?: () => void
  onKill?: () => void
  onBack?: () => void
}

export function HeaderBar({ botState, currentBot, onSettingsClick, onMarketClick, onKill, onBack }: HeaderBarProps) {
  const connectionStatus = botState?.connectionStatus ?? { websocket: true, rest: true }
  const wallet = botState?.wallet ?? { address: currentBot?.wallet_address ?? "", usdcBalance: currentBot?.usdc_balance ?? 0 }
  const status = botState?.status ?? (currentBot?.status ?? "stopped")
  const uptime = botState?.uptime ?? (currentBot?.uptime_seconds ?? 0)
  const [showKillConfirm, setShowKillConfirm] = useState(false)
  
  // Fix hydration mismatch - only render time on client
  const [currentTime, setCurrentTime] = useState<string>("--:--:--")
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const updateTime = () => {
      setCurrentTime(new Date().toLocaleTimeString("en-US", { hour12: false, timeZone: "UTC" }))
    }
    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [])

  // Use bot-specific data if available, otherwise fallback to global state
  const displayStatus = currentBot?.status || status
  const displayWallet = currentBot ? {
    address: currentBot.wallet_address,
    balance: currentBot.usdc_balance
  } : {
    address: wallet.address,
    balance: wallet.usdcBalance
  }
  
  const displayMarket = currentBot?.market_name || botState?.market.name || "Select Market"
  const displayUptime = currentBot?.uptime_seconds || uptime

  return (
    <header className="h-12 border-b border-border bg-card flex items-center px-4 gap-4 shrink-0">
      {onBack && (
        <Button variant="ghost" size="icon" className="h-8 w-8 -ml-2" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
      )}

      {/* Logo / Bot Name */}
      <div className="flex items-center gap-2">
        {!onBack && (
          <div className="w-6 h-6 bg-primary flex items-center justify-center">
            <span className="text-primary-foreground text-xs font-bold">P</span>
          </div>
        )}
        <span className="text-sm font-bold tracking-[0.1em] text-foreground">
          {currentBot ? currentBot.name : "POLYAGENT"}
        </span>
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-border" />

      {/* Connection Status */}
      <div className="flex items-center gap-3">
        <ConnectionIndicator label="WSS" connected={connectionStatus.websocket} />
        <ConnectionIndicator label="REST" connected={connectionStatus.rest} />
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-border" />

      {/* Market Quick View */}
      <div className="flex items-center gap-2 px-2 py-1">
        <Activity className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">MARKET:</span>
        <span className="text-xs font-medium text-foreground truncate max-w-[200px]">
          {displayMarket}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Wallet */}
      <div className="flex items-center gap-2 bg-secondary px-3 py-1.5">
        <Wallet className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs font-mono text-muted-foreground">
          {displayWallet.address ? `${displayWallet.address.slice(0, 6)}...${displayWallet.address.slice(-4)}` : "Not Connected"}
        </span>
        <div className="w-px h-4 bg-border" />
        <span className="text-xs font-mono text-primary font-medium">${displayWallet.balance.toFixed(2)}</span>
      </div>

      {/* Time & Session */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-mono">
          {mounted ? currentTime : "--:--:--"} UTC
        </span>
        <div className="w-px h-4 bg-border" />
        <span className="font-mono">{formatUptime(displayUptime)}</span>
      </div>

      {/* Bot Status */}
      <BotStatusBadge status={displayStatus} />

      {/* Theme Toggle */}
      <ThemeToggle />

      {/* Settings */}
      {onSettingsClick && (
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onSettingsClick}>
          <Settings className="w-4 h-4" />
        </Button>
      )}

      {/* Kill Switch (only active if bot is running) */}
      {(displayStatus === "running" || displayStatus === "paused") && (
        <Button variant="destructive" size="sm" className="h-8 px-3 gap-1.5" onClick={() => setShowKillConfirm(true)}>
          <Power className="w-3.5 h-3.5" />
          <span className="text-xs font-medium">KILL</span>
        </Button>
      )}

      {/* Kill Switch Confirmation */}
      <AlertDialog open={showKillConfirm} onOpenChange={setShowKillConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              Emergency Kill Switch
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will immediately stop {currentBot ? currentBot.name : "the selected bot"}. 
              Any open positions will remain open until manually closed.
              <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <p className="text-sm text-destructive font-medium">
                  This action does NOT close positions - it only stops the bot from executing new trades.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={() => {
                onKill?.()
                setShowKillConfirm(false)
              }} 
              className="bg-destructive hover:bg-destructive/90"
            >
              Stop Bot
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </header>
  )
}

function ConnectionIndicator({ label, connected }: { label: string; connected: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={cn("w-2 h-2", connected ? "bg-primary pulse-live" : "bg-destructive")} />
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

function BotStatusBadge({ status }: { status: "running" | "stopped" | "error" | "paused" }) {
  const config = {
    running: { label: "RUNNING", className: "bg-primary/20 text-primary border-primary/30" },
    stopped: { label: "STOPPED", className: "bg-muted text-muted-foreground border-border" },
    paused: { label: "PAUSED", className: "bg-warning/20 text-warning border-warning/30" },
    error: { label: "ERROR", className: "bg-destructive/20 text-destructive border-destructive/30" },
  }

  const { label, className } = config[status] || config.stopped

  return (
    <div className={cn("px-2 py-1 text-xs font-medium border flex items-center gap-1.5", className)}>
      {status === "error" && <AlertTriangle className="w-3 h-3" />}
      {label}
    </div>
  )
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}
