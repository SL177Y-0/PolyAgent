"use client"

import { useState, useEffect, useCallback } from "react"
import { Plus, Wallet, Trash2, Settings, Play, Square, Edit2, Eye, EyeOff, Key, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { getApiClient } from "@/lib/api-client"
import type { BotStatus, CreateBotRequest, UpdateBotRequest, TradingProfile } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

// Default profile when none are loaded from backend
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

interface BotManagerPanelProps {
  onSelectBot?: (botId: string) => void
  selectedBotId?: string | null
  /** Called after create/update/delete operations so parents can refresh */
  onUpdate?: () => void | Promise<void>
}

export function BotManagerPanel({ onSelectBot, selectedBotId, onUpdate }: BotManagerPanelProps = {}) {
  const [bots, setBots] = useState<BotStatus[]>([])
  const [profiles, setProfiles] = useState<TradingProfile[]>(DEFAULT_PROFILES)
  const [profilesLoading, setProfilesLoading] = useState(true)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [editingBot, setEditingBot] = useState<BotStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [deleteConfirmBot, setDeleteConfirmBot] = useState<BotStatus | null>(null)

  const api = getApiClient()

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const result = await api.getBots()
      setBots(result.bots)

      setProfilesLoading(true)
      try {
        const profilesResult = await api.getProfiles()
        if (profilesResult.profiles && profilesResult.profiles.length > 0) {
          setProfiles(profilesResult.profiles)
        }
      } catch (profileError) {
        console.warn("Failed to fetch profiles, using defaults:", profileError)
        // Keep default profiles
      } finally {
        setProfilesLoading(false)
      }

      await onUpdate?.()
    } catch (error) {
      console.error("Failed to fetch data:", error)
      toast.error("Failed to connect to backend")
    }
  }, [api, onUpdate])

  useEffect(() => {
    fetchData()

    // Set up WebSocket for real-time updates
    const handlers = {
      init: () => fetchData(),
      bot_created: () => fetchData(),
      bot_updated: () => fetchData(),
      bot_deleted: () => fetchData(),
      bot_started: () => fetchData(),
      bot_stopped: () => fetchData(),
    }

    Object.entries(handlers).forEach(([event, handler]) => {
      api.on(event, handler)
    })

    return () => {
      Object.keys(handlers).forEach(event => {
        api.off(event)
      })
    }
  }, [api, fetchData])

  // Handle open dialog for create
  const handleCreateOpen = () => {
    setEditingBot(null)
    setIsCreateDialogOpen(true)
  }

  // Handle open dialog for edit
  const handleEditBot = (bot: BotStatus) => {
    setEditingBot(bot)
    setIsCreateDialogOpen(true)
  }

  // Start/Stop bot handler
  const handleToggleBot = async (botId: string, isRunning: boolean) => {
    try {
      if (isRunning) {
        await api.stopBot(botId)
        toast.success("Bot stopped successfully")
      } else {
        await api.startBot(botId)
        toast.success("Bot started successfully")
      }
      await fetchData()
    } catch (error) {
      console.error("Failed to toggle bot:", error)
      toast.error(isRunning ? "Failed to stop bot" : "Failed to start bot")
    }
  }

  // Delete bot handler
  const handleDeleteBot = async (bot: BotStatus) => {
    setDeleteConfirmBot(bot)
  }

  const confirmDeleteBot = async () => {
    if (!deleteConfirmBot) return

    try {
      await api.deleteBot(deleteConfirmBot.bot_id)
      toast.success("Bot deleted successfully")
      await fetchData()
    } catch (error) {
      console.error("Failed to delete bot:", error)
      toast.error("Failed to delete bot")
    } finally {
      setDeleteConfirmBot(null)
    }
  }

  return (
    <div className="h-full p-4 flex flex-col gap-4 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xs text-muted-foreground font-medium tracking-wide">BOT MANAGER</h2>
        <BotDialog
          isOpen={isCreateDialogOpen}
          onOpenChange={setIsCreateDialogOpen}
          onCreate={fetchData}
          profiles={profiles}
          profilesLoading={profilesLoading}
          isLoading={isLoading}
          setIsLoading={setIsLoading}
          bot={editingBot}
        />
        <Button size="sm" className="gap-1" onClick={handleCreateOpen}>
          <Plus className="w-4 h-4" />
          New Bot
        </Button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-secondary/50 p-2 rounded-md text-center">
          <span className="text-2xl font-mono font-semibold">{bots.length}</span>
          <p className="text-[10px] text-muted-foreground">TOTAL BOTS</p>
        </div>
        <div className="bg-secondary/50 p-2 rounded-md text-center">
          <span className="text-2xl font-mono font-semibold text-success">
            {bots.filter(b => b.status === "running").length}
          </span>
          <p className="text-[10px] text-muted-foreground">RUNNING</p>
        </div>
      </div>

      {/* Bot List */}
      <div className="space-y-2">
        {bots.length === 0 ? (
          <div className="text-center text-muted-foreground text-sm py-8">
            No bots created yet.<br />Create one to get started.
          </div>
        ) : (
          bots.map((bot) => (
            <BotCard
              key={bot.bot_id}
              bot={bot}
              onToggle={handleToggleBot}
              onDelete={handleDeleteBot}
              onEdit={handleEditBot}
              onSelect={onSelectBot}
              isSelected={selectedBotId === bot.bot_id}
            />
          ))
        )}
      </div>

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
                <span className="block mt-2 text-warning">
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

interface BotDialogProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  onCreate: () => void
  profiles: TradingProfile[]
  profilesLoading: boolean
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  bot: BotStatus | null
}

function BotDialog({
  isOpen,
  onOpenChange,
  onCreate,
  profiles,
  profilesLoading,
  isLoading,
  setIsLoading,
  bot,
}: BotDialogProps) {
  const [activeTab, setActiveTab] = useState<"basic" | "wallet" | "strategy">("basic")

  // Basic info
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [marketSlug, setMarketSlug] = useState("")
  const [marketTokenId, setMarketTokenId] = useState("")

  // Wallet
  const [privateKey, setPrivateKey] = useState("")
  const [showPrivateKey, setShowPrivateKey] = useState(false)
  const [signatureType, setSignatureType] = useState<"0" | "2">("0")
  const [funderAddress, setFunderAddress] = useState("")

  // Strategy
  const [profile, setProfile] = useState("normal")
  const [tradeSize, setTradeSize] = useState("2.0")
  const [maxBalance, setMaxBalance] = useState("10.0")
  const [dryRun, setDryRun] = useState(true)
  const [spikeThreshold, setSpikeThreshold] = useState("8.0")
  const [takeProfit, setTakeProfit] = useState("3.0")
  const [stopLoss, setStopLoss] = useState("2.5")
  const [maxHold, setMaxHold] = useState("3600")
  const [rebuyDelay, setRebuyDelay] = useState("2.0")
  const [rebuyStrategy, setRebuyStrategy] = useState<"immediate" | "wait_for_drop">("immediate")
  const [entryMode, setEntryMode] = useState<"immediate_buy" | "wait_for_spike" | "delayed_buy">("wait_for_spike")
  const [entryDelay, setEntryDelay] = useState("0")
  const [maxTrades, setMaxTrades] = useState("0")
  const [sessionLossLimit, setSessionLossLimit] = useState("0")
  const [rebuyDrop, setRebuyDrop] = useState("0.1")

  const api = getApiClient()

  // Auto-fill form fields when profile changes
  const applyProfile = useCallback((profileName: string) => {
    const selectedProfile = profiles.find(p => p.name === profileName)
    if (selectedProfile) {
      setTradeSize(selectedProfile.default_trade_size_usd?.toString() || "2.0")
      setSpikeThreshold(selectedProfile.spike_threshold_pct?.toString() || "8.0")
      setTakeProfit(selectedProfile.take_profit_pct?.toString() || "3.0")
      setStopLoss(selectedProfile.stop_loss_pct?.toString() || "2.5")
      setMaxHold(selectedProfile.max_hold_seconds?.toString() || "3600")
      setRebuyDelay(selectedProfile.rebuy_delay_seconds?.toString() || "2.0")
      setRebuyStrategy(selectedProfile.rebuy_strategy || "immediate")
      setRebuyDrop(selectedProfile.rebuy_drop_pct?.toString() || "0.1")
      toast.success(`Applied "${selectedProfile.name}" profile settings`)
    }
  }, [profiles])

  // Handle profile selection change
  const handleProfileChange = (newProfile: string) => {
    setProfile(newProfile)
    applyProfile(newProfile)
  }

  // Reset or populate form when dialog opens
  useEffect(() => {
    if (isOpen) {
      if (bot) {
        // Edit mode - populate fields
        setName(bot.name)
        setDescription(bot.description)
        setMarketSlug(bot.market_slug || "")
        setMarketTokenId(bot.token_id || "")
        setSignatureType(bot.signature_type === "Proxy" ? "2" : "0")
        // Don't populate sensitive wallet info like private key

        setProfile(bot.trading_profile || "normal")
        setTradeSize(bot.trade_size_usd?.toString() || "2.0")
        setMaxBalance(bot.max_balance_per_bot?.toString() || "10.0")
        setDryRun(bot.dry_run)
        setSpikeThreshold(bot.spike_threshold_pct?.toString() || "8.0")
        setTakeProfit(bot.take_profit_pct?.toString() || "3.0")
        setStopLoss(bot.stop_loss_pct?.toString() || "2.5")
        setMaxHold("3600")
        setRebuyDelay(bot.rebuy_delay_seconds?.toString() || "2.0")
        setRebuyStrategy(bot.rebuy_strategy || "immediate")
        setRebuyDrop(bot.rebuy_drop_pct?.toString() || "0.1")

        // Startup entry mode
        setEntryMode(bot.entry_mode || "wait_for_spike")
        setEntryDelay(bot.entry_delay_seconds?.toString() || "0")

        // Session limits
        setMaxTrades(bot.max_trades_per_session?.toString() || "0")
        setSessionLossLimit(bot.session_loss_limit_usd?.toString() || "0")
      } else {
        // Create mode - reset fields and apply default profile
        setName("")
        setDescription("")
        setMarketSlug("")
        setMarketTokenId("")
        setPrivateKey("")
        setSignatureType("0")
        setFunderAddress("")
        setProfile("normal")
        setMaxBalance("10.0")
        setDryRun(true)
        // Apply normal profile defaults
        const normalProfile = profiles.find(p => p.name === "normal") || profiles[0]
        if (normalProfile) {
          setTradeSize(normalProfile.default_trade_size_usd?.toString() || "2.0")
          setSpikeThreshold(normalProfile.spike_threshold_pct?.toString() || "8.0")
          setTakeProfit(normalProfile.take_profit_pct?.toString() || "3.0")
          setStopLoss(normalProfile.stop_loss_pct?.toString() || "2.5")
          setMaxHold(normalProfile.max_hold_seconds?.toString() || "3600")
          setRebuyDelay(normalProfile.rebuy_delay_seconds?.toString() || "2.0")
          setRebuyStrategy(normalProfile.rebuy_strategy || "immediate")
          setRebuyDrop(normalProfile.rebuy_drop_pct?.toString() || "0.1")
        }

        // Reset startup entry mode defaults
        setEntryMode("wait_for_spike")
        setEntryDelay("0")

        // Reset session limits
        setMaxTrades("0")
        setSessionLossLimit("0")
      }
      setActiveTab("basic")
    }
  }, [isOpen, bot, profiles])

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Bot name is required")
      return
    }

    setIsLoading(true)
    try {
      if (bot) {
        // Update existing bot
        const request: UpdateBotRequest = {
          entry_mode: entryMode,
          entry_delay_seconds: parseInt(entryDelay) || 0,
          max_trades_per_session: parseInt(maxTrades) || 0,
          session_loss_limit_usd: parseFloat(sessionLossLimit) || 0,
          name: name.trim(),
          description: description.trim(),
          market_slug: marketSlug.trim() || undefined,
          market_token_id: marketTokenId.trim() || undefined,
          profile: profile,
          trade_size_usd: parseFloat(tradeSize) || undefined,
          max_balance_per_bot: parseFloat(maxBalance) || undefined,
          dry_run: dryRun,
          spike_threshold_pct: parseFloat(spikeThreshold) || undefined,
          take_profit_pct: parseFloat(takeProfit) || undefined,
          stop_loss_pct: parseFloat(stopLoss) || undefined,
          max_hold_seconds: parseInt(maxHold) || undefined,
          rebuy_delay_seconds: parseFloat(rebuyDelay),
          rebuy_strategy: rebuyStrategy,
          rebuy_drop_pct: parseFloat(rebuyDrop),
        }

        await api.updateBot(bot.bot_id, request)
        toast.success("Bot updated successfully")
      } else {
        // Create new bot
        const request: CreateBotRequest = {
          entry_mode: entryMode,
          entry_delay_seconds: parseInt(entryDelay) || 0,
          max_trades_per_session: parseInt(maxTrades) || 0,
          session_loss_limit_usd: parseFloat(sessionLossLimit) || 0,
          name: name.trim(),
          description: description.trim(),
          market_slug: marketSlug.trim() || undefined,
          market_token_id: marketTokenId.trim() || undefined,
          profile: profile || undefined,
          trade_size_usd: parseFloat(tradeSize) || undefined,
          max_balance_per_bot: parseFloat(maxBalance) || undefined,
          dry_run: dryRun,
          spike_threshold_pct: parseFloat(spikeThreshold) || undefined,
          take_profit_pct: parseFloat(takeProfit) || undefined,
          stop_loss_pct: parseFloat(stopLoss) || undefined,
          max_hold_seconds: parseInt(maxHold) || undefined,
          rebuy_delay_seconds: parseFloat(rebuyDelay),
          rebuy_strategy: rebuyStrategy,
          rebuy_drop_pct: parseFloat(rebuyDrop),
        }

        // Add wallet config if provided
        if (privateKey.trim()) {
          request.private_key = privateKey.trim()
          request.signature_type = parseInt(signatureType)
          if (signatureType === "2" && funderAddress.trim()) {
            request.funder_address = funderAddress.trim()
          }
        }

        await api.createBot(request)
        toast.success("Bot created successfully")
      }

      onOpenChange(false)
      onCreate()
    } catch (error) {
      console.error("Failed to save bot:", error)
      toast.error(bot ? "Failed to update bot" : "Failed to create bot")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{bot ? "Edit Trading Bot" : "Create Trading Bot"}</DialogTitle>
          <DialogDescription>
            {bot ? "Update configuration for this bot session." : "Create a completely isolated bot with its own wallet and configuration."}
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)} className="mt-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic">Basic</TabsTrigger>
            <TabsTrigger value="wallet">Wallet</TabsTrigger>
            <TabsTrigger value="strategy">Strategy</TabsTrigger>
          </TabsList>

          {/* Basic Tab */}
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
              <p className="text-xs text-muted-foreground">
                Use token ID instead of slug if you know it
              </p>
            </div>
          </TabsContent>

          {/* Wallet Tab */}
          <TabsContent value="wallet" className="space-y-4 mt-4">
            <div className="bg-secondary/50 p-3 rounded-md text-xs text-muted-foreground">
              <p className="font-medium mb-1">Wallet Configuration</p>
              {bot ? (
                <p>Private keys are not displayed for security. Enter a new key only if you want to change it.</p>
              ) : (
                <>
                  <p>Leave empty to use the default wallet from .env file.</p>
                  <p className="mt-2">Each bot can have its own isolated wallet for independent trading.</p>
                </>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="signatureType">Wallet Type</Label>
              <Select value={signatureType} onValueChange={(v: "0" | "2") => setSignatureType(v)}>
                <SelectTrigger id="signatureType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Standard Wallet (EOA)</SelectItem>
                  <SelectItem value="2">Smart Wallet (Gnosis Proxy)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="privateKey">Private Key</Label>
              <div className="flex gap-1">
                <Input
                  id="privateKey"
                  type={showPrivateKey ? "text" : "password"}
                  placeholder={bot ? "Enter new key to update (optional)" : "64 hex characters (optional)"}
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
              <p className="text-xs text-muted-foreground">
                64 hex characters without 0x prefix.
              </p>
            </div>

            {signatureType === "2" && (
              <div className="space-y-2">
                <Label htmlFor="funderAddress">Funder Address *</Label>
                <Input
                  id="funderAddress"
                  placeholder="0x..."
                  value={funderAddress}
                  onChange={(e) => setFunderAddress(e.target.value)}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">
                  Required for Gnosis Safe Proxy mode
                </p>
              </div>
            )}

            {/* Startup Entry Mode */}
            <div className="space-y-3 border-t pt-4 mt-4">
              <div>
                <h4 className="text-sm font-semibold text-foreground">Startup Entry Mode</h4>
                <p className="text-xs text-muted-foreground">Choose when the bot should enter its first position</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="entryMode">Entry Mode</Label>
                <Select value={entryMode} onValueChange={(v: "immediate_buy" | "wait_for_spike" | "delayed_buy") => setEntryMode(v)}>
                  <SelectTrigger id="entryMode">
                    <SelectValue placeholder="Select entry mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="wait_for_spike">Wait for Spike (default)</SelectItem>
                    <SelectItem value="immediate_buy">Immediate Buy</SelectItem>
                    <SelectItem value="delayed_buy">Delayed Buy</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="entryDelay">Entry Delay (seconds)</Label>
                <Input
                  id="entryDelay"
                  type="number"
                  step="1"
                  min="0"
                  value={entryDelay}
                  onChange={(e) => setEntryDelay(e.target.value)}
                  placeholder="0"
                />
                <p className="text-xs text-muted-foreground">
                  {entryMode === "immediate_buy" && "Bot will buy immediately when started"}
                  {entryMode === "wait_for_spike" && "Bot waits for price spike before entering"}
                  {entryMode === "delayed_buy" && "Bot waits for specified delay, then buys"}
                </p>
              </div>
            </div>
          </TabsContent>

          {/* Strategy Tab */}
          <TabsContent value="strategy" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label htmlFor="profile">Trading Profile</Label>
              {profilesLoading ? (
                <div className="flex items-center gap-2 h-10 px-3 border rounded-md bg-muted">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading profiles...</span>
                </div>
              ) : (
                <Select value={profile} onValueChange={handleProfileChange}>
                  <SelectTrigger id="profile">
                    <SelectValue placeholder="Select a profile" />
                  </SelectTrigger>
                  <SelectContent>
                    {profiles.length === 0 ? (
                      <div className="p-2 text-sm text-muted-foreground">No profiles available</div>
                    ) : (
                      profiles.map((p) => (
                        <SelectItem key={p.name} value={p.name}>
                          <div className="flex flex-col">
                            <div className="font-medium">{p.name}</div>
                            <div className="text-xs text-muted-foreground">{p.description}</div>
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              Spike: {p.spike_threshold_pct}% | TP: {p.take_profit_pct}% | SL: {p.stop_loss_pct}%
                            </div>
                          </div>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              )}
              <p className="text-xs text-muted-foreground">
                Selecting a profile will auto-fill the strategy parameters below
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="tradeSize">Trade Size (USD)</Label>
                <Input
                  id="tradeSize"
                  type="number"
                  step="0.1"
                  value={tradeSize}
                  onChange={(e) => setTradeSize(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="maxBalance">Max Balance (USD)</Label>
                <Input
                  id="maxBalance"
                  type="number"
                  step="1"
                  value={maxBalance}
                  onChange={(e) => setMaxBalance(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Dry Run Mode</Label>
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
            </div>

            <div className="border-t pt-3 mt-3">

              <p className="text-xs font-medium mb-2">Rebuy Strategy</p>
              <div className="grid grid-cols-2 gap-3 mb-2">
                <div className="space-y-1">
                  <Label className="text-[10px]">Strategy</Label>
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
                  <Label className="text-[10px]">Delay (sec)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={rebuyDelay}
                    onChange={(e) => setRebuyDelay(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
              {rebuyStrategy === "wait_for_drop" && (
                <div className="space-y-1 mb-2">
                  <Label className="text-[10px]">Required Drop %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={rebuyDrop}
                    onChange={(e) => setRebuyDrop(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              )}
            </div>

            <div className="border-t pt-3">
              <p className="text-xs font-medium mb-2">Session Limits</p>
              <div className="grid grid-cols-2 gap-3 mb-2">
                <div className="space-y-1">
                  <Label className="text-[10px]">Max Trades (0=off)</Label>
                  <Input type="number" step="1" value={maxTrades} onChange={(e) => setMaxTrades(e.target.value)} className="h-8 text-xs" />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Session Loss Limit (USD)</Label>
                  <Input type="number" step="0.1" value={sessionLossLimit} onChange={(e) => setSessionLossLimit(e.target.value)} className="h-8 text-xs" />
                </div>
              </div>

              <p className="text-xs font-medium mb-2">Custom Risk Parameters</p>
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
              <div className="mt-2">
                <Label className="text-[10px]">Max Hold Time (seconds)</Label>
                <Input
                  type="number"
                  value={maxHold}
                  onChange={(e) => setMaxHold(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? "Saving..." : bot ? "Update Bot" : "Create Bot"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog >
  )
}

interface BotCardProps {
  bot: BotStatus
  onToggle: (botId: string, isRunning: boolean) => void
  onDelete: (bot: BotStatus) => void
  onEdit: (bot: BotStatus) => void
  onSelect?: (botId: string) => void
  isSelected?: boolean
}

function BotCard({ bot, onToggle, onDelete, onEdit, onSelect, isSelected }: BotCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const statusColors: Record<string, string> = {
    running: "bg-success",
    stopped: "bg-muted",
    paused: "bg-warning",
    error: "bg-destructive",
  }

  const isRunning = bot.status === "running"

  return (
    <div
      className={cn(
        "bg-secondary/30 p-3 rounded-md space-y-2 cursor-pointer transition-all",
        isSelected && "ring-2 ring-primary bg-secondary/50",
        !isSelected && "hover:bg-secondary/40"
      )}
      onClick={() => onSelect?.(bot.bot_id)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className={cn("w-2 h-2 rounded-full flex-shrink-0", statusColors[bot.status] || "bg-muted")} />
          <span className="text-sm font-medium truncate" title={bot.name}>
            {bot.name}
          </span>
          {bot.dry_run && <Badge variant="outline" className="text-[10px] py-0 h-4">DRY RUN</Badge>}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? "Collapse" : "Expand"}
          >
            <Settings className="w-3 h-3" />
          </Button>
          {!isRunning && (
            <Button size="icon-sm" variant="ghost" onClick={() => onEdit(bot)} title="Edit Bot">
              <Edit2 className="w-3 h-3" />
            </Button>
          )}
          {isRunning ? (
            <Button size="icon-sm" variant="ghost" onClick={() => onToggle(bot.bot_id, true)}>
              <Square className="w-3 h-3" />
            </Button>
          ) : (
            <Button size="icon-sm" variant="ghost" onClick={() => onToggle(bot.bot_id, false)}>
              <Play className="w-3 h-3" />
            </Button>
          )}
          <Button size="icon-sm" variant="ghost" onClick={() => onDelete(bot)}>
            <Trash2 className="w-3 h-3 text-destructive" />
          </Button>
        </div>
      </div>

      {/* Expanded Info */}
      {isExpanded && (
        <div className="space-y-2 pt-2 border-t">
          {/* Wallet Info */}
          <div className="flex items-center gap-2 text-xs">
            <Key className="w-3 h-3 text-muted-foreground" />
            <span className="text-muted-foreground">Wallet:</span>
            <span className="font-mono text-[10px] truncate" title={bot.wallet_address}>
              {bot.wallet_address.slice(0, 8)}...{bot.wallet_address.slice(-6)}
            </span>
            <Badge variant="outline" className="text-[10px] py-0 h-4">
              {bot.signature_type}
            </Badge>
          </div>

          {/* Market */}
          {bot.market_slug && (
            <div className="text-xs">
              <span className="text-muted-foreground">Market: </span>
              <span className="font-mono text-[10px]">{bot.market_slug}</span>
            </div>
          )}

          {/* Token ID */}
          {bot.token_id && (
            <div className="text-xs">
              <span className="text-muted-foreground">Token: </span>
              <span className="font-mono text-[10px]" title={bot.token_id}>
                {bot.token_id.slice(0, 12)}...
              </span>
            </div>
          )}

          {/* Balance */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Balance:</span>
            <span className="font-mono">${bot.usdc_balance.toFixed(2)}</span>
          </div>

          {/* Max Balance */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Max Allocation:</span>
            <span className="font-mono">${(bot.max_balance_per_bot ?? 0).toFixed(2)}</span>
          </div>

          {/* P&L */}
          {bot.session_stats && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">P&L:</span>
              <span className={cn(
                "font-mono",
                bot.session_stats.realized_pnl >= 0 ? "text-success" : "text-destructive"
              )}>
                {bot.session_stats.realized_pnl >= 0 ? "+" : ""}${bot.session_stats.realized_pnl.toFixed(2)}
              </span>
            </div>
          )}

          {/* Position */}
          {bot.position?.has_position && (
            <div className="bg-secondary/50 p-2 rounded text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Position:</span>
                <Badge variant={bot.position.side === "BUY" ? "default" : "secondary"}>
                  {bot.position.side}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Size:</span>
                <span className="font-mono">${bot.position.amount_usd?.toFixed(2)}</span>
              </div>
              {bot.position.pnl_usd !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">P&L:</span>
                  <span className={cn(
                    "font-mono",
                    (bot.position.pnl_usd || 0) >= 0 ? "text-success" : "text-destructive"
                  )}>
                    {(bot.position.pnl_usd || 0) >= 0 ? "+" : ""}${(bot.position.pnl_usd || 0).toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Stats */}
          {bot.session_stats && (
            <div className="flex gap-3 text-xs">
              <span>{bot.session_stats.total_trades} trades</span>
              <span>{bot.session_stats.winning_trades} wins</span>
              <span>
                {bot.session_stats.total_trades > 0
                  ? ((bot.session_stats.winning_trades / bot.session_stats.total_trades) * 100).toFixed(0)
                  : 0}% win rate
              </span>
            </div>
          )}

          {/* Error */}
          {bot.error && (
            <div className="text-xs text-destructive bg-destructive/10 p-2 rounded">
              {bot.error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
