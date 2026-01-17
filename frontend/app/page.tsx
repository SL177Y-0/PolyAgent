"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { getApiClient } from "@/lib/api-client"
import type { BotStatus, CreateBotRequest, TradingProfile } from "@/lib/types"
import { DashboardSummary } from "@/components/dashboard-summary"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Plus, Play, Pause, Square, Settings, Eye, EyeOff, Loader2, Edit2, Trash2, OctagonAlert } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from "@/components/ui/dialog"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "sonner"
import { ThemeToggle } from "@/components/theme-toggle"
import { SettingsPanel } from "@/components/settings-panel"

// Default profiles fallback
const DEFAULT_PROFILES: TradingProfile[] = [
  {
    name: "normal",
    description: "Balanced strategy for most markets",
    spike_threshold_pct: 8.0,
    take_profit_pct: 3.0,
    stop_loss_pct: 2.5,
    default_trade_size_usd: 2.0,
    max_hold_seconds: 3600,
    cooldown_seconds: 30,
    min_spike_strength: 0.5,
    use_volatility_filter: true,
    max_volatility_cv: 10.0,
    rebuy_delay_seconds: 2.0,
    rebuy_strategy: "immediate",
    rebuy_drop_pct: 0.1,
  },
  {
    name: "aggressive",
    description: "Higher risk, higher reward",
    spike_threshold_pct: 5.0,
    take_profit_pct: 5.0,
    stop_loss_pct: 3.0,
    default_trade_size_usd: 5.0,
    max_hold_seconds: 1800,
    cooldown_seconds: 15,
    min_spike_strength: 0.3,
    use_volatility_filter: false,
    max_volatility_cv: 15.0,
    rebuy_delay_seconds: 1.0,
    rebuy_strategy: "immediate",
    rebuy_drop_pct: 0.05,
  },
  {
    name: "conservative",
    description: "Lower risk, steady gains",
    spike_threshold_pct: 12.0,
    take_profit_pct: 2.0,
    stop_loss_pct: 1.5,
    default_trade_size_usd: 1.0,
    max_hold_seconds: 7200,
    cooldown_seconds: 60,
    min_spike_strength: 0.7,
    use_volatility_filter: true,
    max_volatility_cv: 5.0,
    rebuy_delay_seconds: 5.0,
    rebuy_strategy: "wait_for_drop",
    rebuy_drop_pct: 0.2,
  },
]

export default function DashboardHome() {
  const router = useRouter()
  const [bots, setBots] = useState<BotStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editingBot, setEditingBot] = useState<BotStatus | null>(null)
  const [deleteConfirmBot, setDeleteConfirmBot] = useState<BotStatus | null>(null)
  const api = getApiClient()
  const [settingsOpen, setSettingsOpen] = useState(false)

  const fetchBots = useCallback(async () => {
    try {
      const res = await api.getBots()
      setBots(res.bots)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    fetchBots()
    api.connectWebSocket()
    api.on("init", fetchBots)
    api.on("bot_created", fetchBots)
    api.on("bot_updated", fetchBots)
    api.on("bot_started", fetchBots)
    api.on("bot_stopped", fetchBots)
    api.on("bot_deleted", fetchBots)

    const interval = setInterval(fetchBots, 5000)
    return () => {
      clearInterval(interval)
      api.off("init")
      api.off("bot_created")
      api.off("bot_updated")
      api.off("bot_started")
      api.off("bot_stopped")
      api.off("bot_deleted")
    }
  }, [api, fetchBots])

  const handleBotAction = async (e: React.MouseEvent, botId: string, action: "start" | "stop" | "pause" | "resume") => {
    e.stopPropagation()
    try {
      if (action === "start") await api.startBot(botId)
      if (action === "stop") await api.stopBot(botId)
      if (action === "pause") await api.pauseBot(botId)
      if (action === "resume") await api.resumeBot(botId)
      toast.success(`Bot ${action}ed successfully`)
      fetchBots()
    } catch (err) {
      console.error(err)
      // Extract actual error message from the API response
      const errorMessage = err instanceof Error ? err.message : `Failed to ${action} bot`
      toast.error(errorMessage)
    }
  }

  const handleBotCreated = () => {
    setCreateDialogOpen(false)
    setEditingBot(null)
    fetchBots()
  }

  const handleEditBot = (e: React.MouseEvent, bot: BotStatus) => {
    e.stopPropagation()
    setEditingBot(bot)
    setCreateDialogOpen(true)
  }

  const handleDeleteBot = (e: React.MouseEvent, bot: BotStatus) => {
    e.stopPropagation()
    setDeleteConfirmBot(bot)
  }

  const confirmDeleteBot = async () => {
    if (!deleteConfirmBot) return
    try {
      await api.deleteBot(deleteConfirmBot.bot_id)
      toast.success("Bot deleted successfully")
      fetchBots()
    } catch (err) {
      console.error(err)
      toast.error("Failed to delete bot")
    } finally {
      setDeleteConfirmBot(null)
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button variant="outline" onClick={() => setSettingsOpen(true)}>
            <Settings className="w-4 h-4 mr-1" /> Settings
          </Button>
          <Button
            variant="destructive"
            onClick={async () => {
              try {
                await fetch("/api/kill", { method: "POST" })
                toast.success("Kill switch activated")
                fetchBots()
              } catch (e) {
                console.error(e)
                toast.error("Kill switch failed")
              }
            }}
            className="gap-1"
          >
            <OctagonAlert className="w-4 h-4" /> Kill All
          </Button>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Create Bot
          </Button>
        </div>
      </div>

      <DashboardSummary bots={bots} />

      {/* Global Settings Panel */}
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        config={{
          slippageTolerance: 0.06,
          minBidLiquidity: 5,
          minAskLiquidity: 5,
          maxSpreadPct: 1,
          wssEnabled: true,
          wssReconnectDelay: 1,
          killswitchOnShutdown: true,
          logLevel: "INFO",
        }}
      />

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {bots.map((bot) => (
          <Card
            key={bot.bot_id}
            className="cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => router.push(`/bots/${bot.bot_id}`)}
          >
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg">{bot.name}</CardTitle>
                <Badge variant={
                  bot.status === "running" ? "default" :
                    bot.status === "paused" ? "secondary" :
                      bot.status === "error" ? "destructive" : "outline"
                }>
                  {bot.status}
                </Badge>
              </div>
              <CardDescription className="line-clamp-1">
                {bot.market_slug || "No market selected"}
              </CardDescription>
            </CardHeader>

            <CardContent className="pb-2">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">P&L</p>
                  <p className={`font-medium ${(bot.session_stats?.realized_pnl || 0) >= 0 ? "text-green-500" : "text-red-500"
                    }`}>
                    ${(bot.session_stats?.realized_pnl || 0).toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Trades</p>
                  <p className="font-medium">{bot.session_stats?.total_trades || 0}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Balance</p>
                  <p className="font-medium">${(bot.usdc_balance || 0).toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Position</p>
                  <p className="font-medium">
                    {bot.position?.has_position
                      ? `${bot.position.side} $${bot.position.amount_usd.toFixed(0)}`
                      : "None"}
                  </p>
                </div>
              </div>
            </CardContent>

            <CardFooter className="pt-4 flex justify-between">
              <div className="flex gap-2">
                {bot.status === "running" ? (
                  <>
                    <Button size="sm" variant="outline" onClick={(e) => handleBotAction(e, bot.bot_id, "pause")}>
                      <Pause className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="destructive" onClick={(e) => handleBotAction(e, bot.bot_id, "stop")}>
                      <Square className="h-4 w-4" />
                    </Button>
                  </>
                ) : bot.status === "paused" ? (
                  <>
                    <Button size="sm" variant="outline" onClick={(e) => handleBotAction(e, bot.bot_id, "resume")}>
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="destructive" onClick={(e) => handleBotAction(e, bot.bot_id, "stop")}>
                      <Square className="h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <Button size="sm" variant="default" onClick={(e) => handleBotAction(e, bot.bot_id, "start")}>
                    <Play className="h-4 w-4 mr-2" /> Start
                  </Button>
                )}
              </div>
              <div className="flex gap-1">
                {bot.status !== "running" && (
                  <Button size="sm" variant="ghost" onClick={(e) => handleEditBot(e, bot)} title="Edit Bot">
                    <Edit2 className="h-4 w-4" />
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={(e) => handleDeleteBot(e, bot)} title="Delete Bot">
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </CardFooter>
          </Card>
        ))}

        {bots.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 text-muted-foreground">
            No bots found. Create one to get started.
          </div>
        )}
      </div>

      {/* Create/Edit Bot Dialog */}
      <CreateBotDialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          setCreateDialogOpen(open)
          if (!open) setEditingBot(null)
        }}
        onSuccess={handleBotCreated}
        editBot={editingBot}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirmBot} onOpenChange={(open) => !open && setDeleteConfirmBot(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Bot</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <span className="font-semibold">{deleteConfirmBot?.name}</span>?
              {deleteConfirmBot?.position?.has_position && (
                <span className="block mt-2 text-destructive">
                  Warning: This bot has an open position that will NOT be closed automatically.
                </span>
              )}
              {!deleteConfirmBot?.dry_run && (
                <span className="block mt-2 text-orange-500">
                  This bot is using REAL money. Make sure any positions are closed first.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteBot} className="bg-destructive hover:bg-destructive/90">
              Delete Bot
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// Standalone Create/Edit Bot Dialog Component
interface CreateBotDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
  editBot?: BotStatus | null
}

function CreateBotDialog({ open, onOpenChange, onSuccess, editBot }: CreateBotDialogProps) {
  const api = getApiClient()
  const [activeTab, setActiveTab] = useState<"basic" | "wallet" | "strategy">("basic")
  const [isLoading, setIsLoading] = useState(false)
  const [profiles, setProfiles] = useState<TradingProfile[]>(DEFAULT_PROFILES)
  const [profilesLoading, setProfilesLoading] = useState(false)

  // Form state
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [marketSlug, setMarketSlug] = useState("")
  const [marketTokenId, setMarketTokenId] = useState("")

  const [privateKey, setPrivateKey] = useState("")
  const [showPrivateKey, setShowPrivateKey] = useState(false)
  const [signatureType, setSignatureType] = useState<"0" | "2">("0")
  const [funderAddress, setFunderAddress] = useState("")

  const [profile, setProfile] = useState("normal")
  const [tradeSize, setTradeSize] = useState("1.0")
  const [maxBalance, setMaxBalance] = useState("10.0")
  const [dryRun, setDryRun] = useState(true)
  const [spikeThreshold, setSpikeThreshold] = useState("8.0")
  const [takeProfit, setTakeProfit] = useState("3.0")
  const [stopLoss, setStopLoss] = useState("2.5")
  const [maxHold, setMaxHold] = useState("3600")
  const [rebuyDelay, setRebuyDelay] = useState("2.0")
  const [rebuyStrategy, setRebuyStrategy] = useState<"immediate" | "wait_for_drop">("immediate")
  const [rebuyDrop, setRebuyDrop] = useState("0.1")

  // Startup Entry Mode
  const [entryMode, setEntryMode] = useState<"immediate_buy" | "wait_for_spike" | "delayed_buy">("wait_for_spike")
  const [entryDelay, setEntryDelay] = useState("0")

  const isEditMode = !!editBot

  // Load profiles when dialog opens
  useEffect(() => {
    if (open) {
      if (editBot) {
        // Edit mode - populate fields from existing bot
        setName(editBot.name)
        setDescription(editBot.description || "")
        setMarketSlug(editBot.market_slug || "")
        setMarketTokenId(editBot.token_id || "")
        setSignatureType(editBot.signature_type === "Proxy" ? "2" : "0")
        setProfile(editBot.trading_profile || "normal")
        setTradeSize(editBot.trade_size_usd?.toString() || "1.0")
        setMaxBalance(editBot.max_balance_per_bot?.toString() || "10.0")
        setDryRun(editBot.dry_run)
        setSpikeThreshold(editBot.spike_threshold_pct?.toString() || "8.0")
        setTakeProfit(editBot.take_profit_pct?.toString() || "3.0")
        setStopLoss(editBot.stop_loss_pct?.toString() || "2.5")
        setMaxHold("3600")
        setRebuyDelay(editBot.rebuy_delay_seconds?.toString() || "2.0")
        setRebuyStrategy(editBot.rebuy_strategy || "immediate")
        setRebuyDrop(editBot.rebuy_drop_pct?.toString() || "0.1")
        // Don't populate private key for security
        setPrivateKey("")
        setFunderAddress("")
      } else {
        // Create mode - reset form
        setName("")
        setDescription("")
        setMarketSlug("")
        setMarketTokenId("")
        setPrivateKey("")
        setSignatureType("0")
        setFunderAddress("")
        setProfile("normal")
        setTradeSize("1.0")
        setMaxBalance("10.0")
        setDryRun(true)
        // Reset entry mode
        setEntryMode("wait_for_spike")
        setEntryDelay("0")
      }
      setActiveTab("basic")

      // Load profiles
      setProfilesLoading(true)
      api.getProfiles()
        .then(res => {
          if (res.profiles?.length > 0) {
            setProfiles(res.profiles)
          }
        })
        .catch(console.error)
        .finally(() => setProfilesLoading(false))
    }
  }, [open, api, editBot])

  // Apply profile values when profile changes
  const handleProfileChange = (newProfile: string) => {
    setProfile(newProfile)
    const selected = profiles.find(p => p.name === newProfile)
    if (selected) {
      setTradeSize(selected.default_trade_size_usd?.toString() || "1.0")
      setSpikeThreshold(selected.spike_threshold_pct?.toString() || "8.0")
      setTakeProfit(selected.take_profit_pct?.toString() || "3.0")
      setStopLoss(selected.stop_loss_pct?.toString() || "2.5")
      setMaxHold(selected.max_hold_seconds?.toString() || "3600")
      setRebuyDelay(selected.rebuy_delay_seconds?.toString() || "2.0")
      setRebuyStrategy(selected.rebuy_strategy || "immediate")
      setRebuyDrop(selected.rebuy_drop_pct?.toString() || "0.1")
      toast.success(`Applied "${selected.name}" profile`)
    }
  }

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Bot name is required")
      setActiveTab("basic")
      return
    }

    setIsLoading(true)
    try {
      if (isEditMode && editBot) {
        // Update existing bot
        const request: CreateBotRequest = {
          name: name.trim(),
          description: description.trim(),
          market_slug: marketSlug.trim() || undefined,
          market_token_id: marketTokenId.trim() || undefined,
          profile: profile,
          trade_size_usd: parseFloat(tradeSize) || 1.0,
          max_balance_per_bot: parseFloat(maxBalance) || 10.0,
          dry_run: dryRun,
          spike_threshold_pct: parseFloat(spikeThreshold),
          take_profit_pct: parseFloat(takeProfit),
          stop_loss_pct: parseFloat(stopLoss),
          max_hold_seconds: parseInt(maxHold),
          rebuy_delay_seconds: parseFloat(rebuyDelay),
          rebuy_strategy: rebuyStrategy,
          rebuy_drop_pct: parseFloat(rebuyDrop),
          entry_mode: entryMode,
          entry_delay_seconds: parseInt(entryDelay) || 0,
        }

        await api.updateBot(editBot.bot_id, request)
        toast.success("Bot updated successfully!")
      } else {
        // Create new bot
        const request: CreateBotRequest = {
          name: name.trim(),
          description: description.trim(),
          market_slug: marketSlug.trim() || undefined,
          market_token_id: marketTokenId.trim() || undefined,
          profile: profile,
          trade_size_usd: parseFloat(tradeSize) || 1.0,
          max_balance_per_bot: parseFloat(maxBalance) || 10.0,
          dry_run: dryRun,
          spike_threshold_pct: parseFloat(spikeThreshold),
          take_profit_pct: parseFloat(takeProfit),
          stop_loss_pct: parseFloat(stopLoss),
          max_hold_seconds: parseInt(maxHold),
          rebuy_delay_seconds: parseFloat(rebuyDelay),
          rebuy_strategy: rebuyStrategy,
          rebuy_drop_pct: parseFloat(rebuyDrop),
          entry_mode: entryMode,
          entry_delay_seconds: parseInt(entryDelay) || 0,
        }

        if (privateKey.trim()) {
          request.private_key = privateKey.trim()
          request.signature_type = parseInt(signatureType)
          if (signatureType === "2" && funderAddress.trim()) {
            request.funder_address = funderAddress.trim()
          }
        }

        await api.createBot(request)
        toast.success("Bot created successfully!")
      }
      onSuccess()
    } catch (error) {
      console.error("Failed to save bot:", error)
      toast.error(isEditMode ? "Failed to update bot" : "Failed to create bot")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "Edit Trading Bot" : "Create Trading Bot"}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update configuration for this bot session."
              : "Configure your new trading bot with wallet and strategy settings."
            }
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)} className="mt-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic">Basic</TabsTrigger>
            <TabsTrigger value="wallet">Wallet</TabsTrigger>
            <TabsTrigger value="strategy">Strategy</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label htmlFor="name">Bot Name *</Label>
              <Input
                id="name"
                placeholder="My Trading Bot"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Optional description..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="marketSlug">Market Slug</Label>
              <Input
                id="marketSlug"
                placeholder="e.g., will-btc-hit-100k"
                value={marketSlug}
                onChange={(e) => setMarketSlug(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="marketTokenId">Token ID (optional)</Label>
              <Input
                id="marketTokenId"
                placeholder="0x..."
                value={marketTokenId}
                onChange={(e) => setMarketTokenId(e.target.value)}
              />
            </div>
          </TabsContent>

          <TabsContent value="wallet" className="space-y-4 mt-4">
            <div className="bg-secondary/50 p-3 rounded-md text-xs text-muted-foreground">
              <p className="font-medium mb-1">Wallet Configuration</p>
              {isEditMode ? (
                <p>Private keys are not displayed for security. Enter a new key only if you want to change it.</p>
              ) : (
                <p>Leave empty to use the default wallet from .env file.</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Wallet Type</Label>
              <Select value={signatureType} onValueChange={(v: "0" | "2") => setSignatureType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Standard Wallet (EOA)</SelectItem>
                  <SelectItem value="2">Smart Wallet (Gnosis Proxy)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Private Key</Label>
              <div className="flex gap-1">
                <Input
                  type={showPrivateKey ? "text" : "password"}
                  placeholder="64 hex characters (optional)"
                  value={privateKey}
                  onChange={(e) => setPrivateKey(e.target.value)}
                  className="flex-1 font-mono text-xs"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowPrivateKey(!showPrivateKey)}
                >
                  {showPrivateKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </Button>
              </div>
            </div>

            {signatureType === "2" && (
              <div className="space-y-2">
                <Label>Funder Address</Label>
                <Input
                  placeholder="0x..."
                  value={funderAddress}
                  onChange={(e) => setFunderAddress(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>
            )}
          </TabsContent>

          <TabsContent value="strategy" className="space-y-4 mt-4">
            <div className="space-y-2">

              {profilesLoading ? (
                <div className="flex items-center gap-2 h-10 px-3 border rounded-md bg-muted">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading...</span>
                </div>
              ) : (
                <Select value={profile} onValueChange={handleProfileChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {profiles.map((p) => (
                      <SelectItem key={p.name} value={p.name}>
                        <div>
                          <div className="font-medium">{p.name}</div>
                          <div className="text-xs text-muted-foreground">{p.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-2">
                <Label>Trade Size (USD)</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={tradeSize}
                  onChange={(e) => setTradeSize(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Balance (USD)</Label>
                <Input
                  type="number"
                  step="1"
                  value={maxBalance}
                  onChange={(e) => setMaxBalance(e.target.value)}
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="dryRun"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="dryRun" className="cursor-pointer">
                Enable dry run (no real trades)
              </Label>
            </div>

            <div className="border-t pt-3">

              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px]">Spike %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={spikeThreshold}
                    onChange={(e) => setSpikeThreshold(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Take Profit %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Stop Loss %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="border-t pt-3">

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-[10px]">Rebuy Strategy</Label>
                  <Select value={rebuyStrategy} onValueChange={(v: "immediate" | "wait_for_drop") => setRebuyStrategy(v)}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="immediate">Immediate</SelectItem>
                      <SelectItem value="wait_for_drop">Wait for Drop</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Rebuy Delay (sec)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={rebuyDelay}
                    onChange={(e) => setRebuyDelay(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Startup Entry Mode */}
            <div className="border-t pt-3">

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-[10px]">Startup Entry Mode</Label>
                  <Select value={entryMode} onValueChange={(v: "immediate_buy" | "wait_for_spike" | "delayed_buy") => setEntryMode(v)}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="wait_for_spike">Wait for Spike</SelectItem>
                      <SelectItem value="immediate_buy">Immediate Buy</SelectItem>
                      <SelectItem value="delayed_buy">Delayed Buy</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Entry Delay (sec)</Label>
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    value={entryDelay}
                    onChange={(e) => setEntryDelay(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isEditMode ? "Updating..." : "Creating..."}
              </>
            ) : (
              isEditMode ? "Update Bot" : "Create Bot"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
