"use client"

import { useState } from "react"
import { ArrowUp, ArrowDown, Clock, Target, ShieldAlert, Crosshair } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { Position, TradeTarget } from "@/lib/types"
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

interface PositionCardProps {
  position: Position | null
  target?: TradeTarget | null
  currentPrice?: number
  onClosePosition?: () => void
  onManualBuy?: () => void
  onManualSell?: () => void
  tradeSizeUsd?: number
}

export function PositionCard({ position, target, currentPrice, onClosePosition, onManualBuy, onManualSell, tradeSizeUsd = 1.0 }: PositionCardProps) {
  // Check both if position exists AND if it actually has an active position
  if (!position || !position.has_position) {
    return <FlatState target={target} currentPrice={currentPrice} onManualBuy={onManualBuy} onManualSell={onManualSell} tradeSizeUsd={tradeSizeUsd} />
  }

  return <ActivePosition position={position} onClosePosition={onClosePosition} />
}

function ActivePosition({ position, onClosePosition }: { position: Position; onClosePosition?: () => void }) {
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)
  const isLong = position.side === "BUY"
  const pnlPositive = position.pnl_pct >= 0
  const holdProgress = Math.min(((position.age_seconds || 0) / (position.max_hold_seconds || 1)) * 100, 100)

  // Calculate distance to TP/SL
  const distanceToTP = (position.take_profit_pct || 0) - (position.pnl_pct || 0)
  const distanceToSL = (position.pnl_pct || 0) - -(position.stop_loss_pct || 0)

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide flex items-center justify-between">
          <span>CURRENT POSITION</span>
          <div
            className={cn(
              "flex items-center gap-1.5 px-2 py-1",
              isLong ? "bg-primary/20 text-primary" : "bg-destructive/20 text-destructive",
            )}
          >
            {isLong ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />}
            <span className="text-xs font-bold">{isLong ? "LONG" : "SHORT"}</span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Entry & Current */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-xs text-muted-foreground block mb-0.5">ENTRY</span>
            <span className="font-mono font-semibold text-foreground">${position.entry_price.toFixed(4)}</span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground block mb-0.5">SIZE</span>
            <span className="font-mono font-semibold text-foreground">${position.amount_usd.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground block mb-0.5">CURRENT</span>
            <span className="font-mono font-semibold text-foreground">${position.current_price.toFixed(4)}</span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground block mb-0.5">SHARES</span>
            <span className="font-mono font-semibold text-foreground">{(position.shares ?? 0).toFixed(0)}</span>
          </div>
        </div>

        {/* P&L Display */}
        <div className={cn("p-2 rounded", pnlPositive ? "bg-primary/10" : "bg-destructive/10")}>
          <span className="text-xs text-muted-foreground block mb-1">UNREALIZED P&L</span>
          <div className="flex items-baseline gap-2">
            <span className={cn("text-xl font-mono font-bold", pnlPositive ? "text-primary" : "text-destructive")}>
              {pnlPositive ? "+" : ""}${position.pnl_usd.toFixed(2)}
            </span>
            <span className={cn("text-sm font-mono font-medium", pnlPositive ? "text-primary" : "text-destructive")}>
              ({pnlPositive ? "+" : ""}
              {position.pnl_pct.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* Hold Time */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">HOLD TIME</span>
            </div>
            <span className="text-xs font-mono text-foreground">
              {formatTime(position.age_seconds || 0)} / {formatTime(position.max_hold_seconds || 0)}
            </span>
          </div>
          <div className="h-1.5 bg-secondary rounded">
            <div
              className={cn("h-full rounded transition-all duration-300", holdProgress > 80 ? "bg-warning" : "bg-info")}
              style={{ width: `${holdProgress}%` }}
            />
          </div>
        </div>

        {/* Actions */}
        <Button variant="destructive" className="w-full h-8" onClick={() => setShowCloseConfirm(true)}>
          CLOSE POSITION
        </Button>
      </CardContent>

      {/* Close Position Confirmation */}
      <AlertDialog open={showCloseConfirm} onOpenChange={setShowCloseConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Close Position</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to close this {isLong ? "LONG" : "SHORT"} position?
              <div className="mt-3 p-3 bg-secondary/50 rounded-md space-y-1">
                <div className="flex justify-between text-sm">
                  <span>Entry:</span>
                  <span className="font-mono">${position.entry_price.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Current:</span>
                  <span className="font-mono">${position.current_price.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Size:</span>
                  <span className="font-mono">${position.amount_usd.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm font-semibold">
                  <span>Unrealized P&L:</span>
                  <span className={cn("font-mono", pnlPositive ? "text-success" : "text-destructive")}>
                    {pnlPositive ? "+" : ""}${position.pnl_usd.toFixed(2)} ({pnlPositive ? "+" : ""}{position.pnl_pct.toFixed(2)}%)
                  </span>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onClosePosition} className="bg-destructive hover:bg-destructive/90">
              Close Position
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  )
}

function FlatState({ target, currentPrice, onManualBuy, onManualSell, tradeSizeUsd }: { target?: TradeTarget | null; currentPrice?: number; onManualBuy?: () => void; onManualSell?: () => void; tradeSizeUsd?: number }) {
  // Calculate distance to target if available
  const distanceToTarget = target && currentPrice && currentPrice > 0
    ? ((target.price - currentPrice) / currentPrice * 100)
    : null

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide">CURRENT POSITION</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center justify-center py-4">
        {target ? (
          <>
            <div className={cn(
              "w-10 h-10 flex items-center justify-center mb-3",
              target.action === "BUY" ? "bg-primary/20 text-primary" : "bg-destructive/20 text-destructive"
            )}>
              <Crosshair className="w-5 h-5" />
            </div>
            <h3 className="text-base font-medium text-foreground mb-1">
              WAITING TO {target.action}
            </h3>
            <div className="text-center mb-2">
              <span className="text-xl font-mono font-bold text-foreground">
                @ ${target.price.toFixed(4)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground text-center mb-2">
              {target.condition === "<=" ? "When price drops to" : "When price rises to"} target
            </p>
            {distanceToTarget !== null && (
              <div className={cn(
                "px-2 py-0.5 text-xs font-mono",
                distanceToTarget > 0 ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"
              )}>
                {distanceToTarget > 0 ? "+" : ""}{distanceToTarget.toFixed(2)}% away
              </div>
            )}
          </>
        ) : (
          <>
            <div className="w-10 h-10 border border-dashed border-border flex items-center justify-center mb-3">
              <span className="text-xl text-muted-foreground">∅</span>
            </div>
            <h3 className="text-base font-medium text-foreground mb-1">NO POSITION</h3>
            <p className="text-xs text-muted-foreground text-center mb-4">Waiting for spike signal...</p>
          </>
        )}

        {/* Manual Actions */}
        <div className="flex gap-2 w-full mt-3">
          <Button className="flex-1 h-8 bg-primary text-primary-foreground hover:bg-primary/90" onClick={onManualBuy}>
            MANUAL BUY{tradeSizeUsd ? ` $${tradeSizeUsd}` : ""}
          </Button>
          <Button variant="destructive" className="flex-1 h-8" onClick={onManualSell}>
            MANUAL SELL{tradeSizeUsd ? ` $${tradeSizeUsd}` : ""}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs.toString().padStart(2, "0")}s`
}
