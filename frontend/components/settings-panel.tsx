"use client"

import type React from "react"
import { useState, useEffect, useRef, useCallback } from "react"
import { X, Zap, SettingsIcon, Info, Loader2, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { getApiClient, GlobalSettings } from "@/lib/api-client"
import type { BotConfig } from "@/lib/types"

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
  config: BotConfig
}

type TabType = "execution" | "system"
type SaveStatus = "idle" | "saving" | "saved" | "error"

export function SettingsPanel({ open, onClose, config }: SettingsPanelProps) {
  // Inject daily_loss_limit_usd into local state via API fetch
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const api = getApiClient()

  useEffect(() => {
    const load = async () => {
      try {
        const s = await api.getSettings()
        setGlobalSettings(s as GlobalSettings)
      } catch (e) {
        console.error("Failed to load settings", e)
      }
    }
    if (open) load()
  }, [open])
  const [activeTab, setActiveTab] = useState<TabType>("execution")
  const [localConfig, setLocalConfig] = useState<BotConfig>(config)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle")
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const apiClient = useRef(getApiClient())

  // Derive execution config from global settings when available
  const execConfig: BotConfig = globalSettings ? {
    // coerce to proper types to avoid undefined resets
    slippageTolerance: Number(globalSettings.slippage_tolerance ?? 0.06),
    minBidLiquidity: Number(globalSettings.min_bid_liquidity ?? 5),
    minAskLiquidity: Number(globalSettings.min_ask_liquidity ?? 5),
    maxSpreadPct: Number(globalSettings.max_spread_pct ?? 1),
    wssEnabled: Boolean(globalSettings.wss_enabled ?? true),
    wssReconnectDelay: Number(globalSettings.wss_reconnect_delay ?? 1),
    killswitchOnShutdown: Boolean(globalSettings.killswitch_on_shutdown ?? true),
    logLevel: (globalSettings.log_level as any) ?? "INFO",
  } as BotConfig : localConfig

  const handleExecChange = useCallback((next: BotConfig) => {
    setLocalConfig(next)
    if (globalSettings) {
      const updatedSettings: GlobalSettings = {
        ...globalSettings,
        slippage_tolerance: next.slippageTolerance,
        min_bid_liquidity: next.minBidLiquidity,
        min_ask_liquidity: next.minAskLiquidity,
        max_spread_pct: next.maxSpreadPct,
        wss_enabled: next.wssEnabled,
        wss_reconnect_delay: next.wssReconnectDelay,
        killswitch_on_shutdown: next.killswitchOnShutdown,
        log_level: next.logLevel as any,
      }
      setGlobalSettings(updatedSettings)

      // Trigger debounced auto-save
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
      setSaveStatus("saving")
      saveTimeoutRef.current = setTimeout(async () => {
        try {
          await api.updateSettings(updatedSettings)
          setSaveStatus("saved")
          setTimeout(() => setSaveStatus("idle"), 2000)
        } catch (error) {
          console.error("Failed to save settings:", error)
          setSaveStatus("error")
          toast.error("Failed to save settings")
          setTimeout(() => setSaveStatus("idle"), 3000)
        }
      }, 500)
    }
  }, [globalSettings, api])

  const initialLoadRef = useRef(true)

  // Sync local config when prop changes (initial load)
  useEffect(() => {
    setLocalConfig(config)
  }, [config])

  // Load settings from backend on panel open
  useEffect(() => {
    if (open && initialLoadRef.current) {
      initialLoadRef.current = false
      apiClient.current.getSettings().then(settings => {
        setLocalConfig(prev => ({
          ...prev,
          slippageTolerance: settings.slippage_tolerance,
          minBidLiquidity: settings.min_bid_liquidity,
          minAskLiquidity: settings.min_ask_liquidity,
          maxSpreadPct: settings.max_spread_pct,
          killswitchOnShutdown: settings.killswitch_on_shutdown,
          wssEnabled: settings.wss_enabled,
          logLevel: settings.log_level as "DEBUG" | "INFO" | "WARNING" | "ERROR",
        }))
      }).catch(err => {
        console.error("Failed to load settings:", err)
      })
    }
  }, [open])

  // Debounced save function
  const saveSettings = useCallback(async (configToSave: BotConfig) => {
    setSaveStatus("saving")

    const settings: GlobalSettings = {
      slippage_tolerance: configToSave.slippageTolerance ?? 0.02,
      min_bid_liquidity: configToSave.minBidLiquidity ?? 100,
      min_ask_liquidity: configToSave.minAskLiquidity ?? 100,
      max_spread_pct: configToSave.maxSpreadPct ?? 2,
      wss_enabled: configToSave.wssEnabled ?? true,
      wss_reconnect_delay: 5,
      killswitch_on_shutdown: configToSave.killswitchOnShutdown ?? false,
      log_level: (configToSave.logLevel === "DEBUG" || configToSave.logLevel === "INFO" || configToSave.logLevel === "WARNING" || configToSave.logLevel === "ERROR")
        ? configToSave.logLevel
        : "INFO",
      daily_loss_limit_usd: globalSettings?.daily_loss_limit_usd ?? 0,
    }

    try {
      await apiClient.current.updateSettings(settings)
      setSaveStatus("saved")
      // Reset to idle after 2 seconds
      setTimeout(() => setSaveStatus("idle"), 2000)
    } catch (error) {
      console.error("Failed to save settings:", error)
      setSaveStatus("error")
      toast.error("Failed to save settings")
      setTimeout(() => setSaveStatus("idle"), 3000)
    }
  }, [])

  // Handle config changes with debounced auto-save
  const handleConfigChange = useCallback((newConfig: BotConfig) => {
    setLocalConfig(newConfig)

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }

    // Set new timeout for debounced save (500ms)
    saveTimeoutRef.current = setTimeout(() => {
      saveSettings(newConfig)
    }, 500)
  }, [saveSettings])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [])

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: "execution", label: "EXECUTION", icon: <Zap className="w-3.5 h-3.5" /> },
    { id: "system", label: "SYSTEM", icon: <SettingsIcon className="w-3.5 h-3.5" /> },
  ]

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-[480px] bg-card border-l border-border z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium tracking-wide">GLOBAL SETTINGS</h2>
            {/* Save Status Indicator */}
            {saveStatus === "saving" && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Saving...</span>
              </div>
            )}
            {saveStatus === "saved" && (
              <div className="flex items-center gap-1 text-xs text-primary">
                <Check className="w-3 h-3" />
                <span>Saved</span>
              </div>
            )}
            {saveStatus === "error" && (
              <div className="flex items-center gap-1 text-xs text-destructive">
                <span>Save failed</span>
              </div>
            )}
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Info Banner */}
        <div className="mx-4 mt-4 p-3 bg-secondary/50 rounded-md flex gap-2">
          <Info className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
          <p className="text-xs text-muted-foreground">
            These are global execution and system settings. Changes are saved automatically. Bot-specific settings like wallet, market, strategy, and risk parameters are configured per-bot in the Bot Manager.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border mt-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 text-xs font-medium whitespace-nowrap transition-colors",
                activeTab === tab.id
                  ? "text-foreground border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === "execution" && <ExecutionSettings config={execConfig} onChange={handleExecChange} />}
          {activeTab === "system" && (
            <SystemSettings
              config={execConfig}
              onChange={handleExecChange}
              globalSettings={globalSettings}
              setGlobalSettings={setGlobalSettings}
              saving={saving}
              setSaving={setSaving}
              api={api}
            />
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            Settings are auto-saved when changed. Bot-specific settings are saved when creating/editing bots.
          </p>
        </div>
      </div>
    </>
  )
}

function ExecutionSettings({ config, onChange }: { config: BotConfig; onChange: (c: BotConfig) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Slippage Tolerance</Label>
          <span className="text-xs font-mono text-foreground">{((config.slippageTolerance ?? 0.02) * 100).toFixed(1)}%</span>
        </div>
        <Slider
          value={[(config.slippageTolerance ?? 0.02) * 100]}
          onValueChange={([value]) => onChange({ ...config, slippageTolerance: value / 100 })}
          min={1}
          max={10}
          step={0.5}
          className="py-2"
        />
        <p className="text-[10px] text-muted-foreground">Maximum acceptable price slippage for order execution</p>
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Min Bid Liquidity ($)</Label>
        <Input
          type="number"
          value={config.minBidLiquidity ?? 100}
          onChange={(e) => onChange({ ...config, minBidLiquidity: Number.parseFloat(e.target.value) })}
          className="font-mono h-9"
        />
        <p className="text-[10px] text-muted-foreground">Minimum liquidity required on bid side to place sell orders</p>
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Min Ask Liquidity ($)</Label>
        <Input
          type="number"
          value={config.minAskLiquidity ?? 100}
          onChange={(e) => onChange({ ...config, minAskLiquidity: Number.parseFloat(e.target.value) })}
          className="font-mono h-9"
        />
        <p className="text-[10px] text-muted-foreground">Minimum liquidity required on ask side to place buy orders</p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Max Spread (%)</Label>
          <span className="text-xs font-mono text-foreground">{config.maxSpreadPct ?? 2}%</span>
        </div>
        <Slider
          value={[config.maxSpreadPct ?? 2]}
          onValueChange={([value]) => onChange({ ...config, maxSpreadPct: value })}
          min={0.1}
          max={5}
          step={0.1}
          className="py-2"
        />
        <p className="text-[10px] text-muted-foreground">Maximum bid-ask spread percentage for trade execution</p>
      </div>
    </div>
  )
}

interface SystemSettingsProps {
  config: BotConfig;
  onChange: (c: BotConfig) => void;
  globalSettings: GlobalSettings | null;
  setGlobalSettings: React.Dispatch<React.SetStateAction<GlobalSettings | null>>;
  saving: boolean;
  setSaving: React.Dispatch<React.SetStateAction<boolean>>;
  api: ReturnType<typeof getApiClient>;
}

function SystemSettings({ config, onChange, globalSettings, setGlobalSettings, saving, setSaving, api }: SystemSettingsProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-md">
        <div>
          <Label className="text-xs">Killswitch on Shutdown</Label>
          <p className="text-[10px] text-muted-foreground">Auto-close all positions on Ctrl+C</p>
        </div>
        <Switch
          checked={config.killswitchOnShutdown ?? false}
          onCheckedChange={(checked) => onChange({ ...config, killswitchOnShutdown: checked })}
        />
      </div>

      <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-md">
        <div>
          <Label className="text-xs">WebSocket Enabled</Label>
          <p className="text-[10px] text-muted-foreground">Real-time price updates (~1s latency)</p>
        </div>
        <Switch
          checked={config.wssEnabled ?? true}
          onCheckedChange={(checked) => onChange({ ...config, wssEnabled: checked })}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Daily Loss Limit (USD)</Label>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            step="0.1"
            value={globalSettings?.daily_loss_limit_usd ?? 0}
            onChange={(e) => setGlobalSettings(prev => prev ? { ...prev, daily_loss_limit_usd: parseFloat(e.target.value || "0") } : null)}
          />
          <Button
            size="sm"
            onClick={async () => {
              if (!globalSettings) return
              try {
                setSaving(true)
                const s: GlobalSettings = {
                  ...globalSettings,
                  slippage_tolerance: globalSettings.slippage_tolerance ?? 0.06,
                  min_bid_liquidity: globalSettings.min_bid_liquidity ?? 5,
                  min_ask_liquidity: globalSettings.min_ask_liquidity ?? 5,
                  max_spread_pct: globalSettings.max_spread_pct ?? 1,
                  wss_enabled: globalSettings.wss_enabled ?? true,
                  wss_reconnect_delay: globalSettings.wss_reconnect_delay ?? 1,
                  killswitch_on_shutdown: globalSettings.killswitch_on_shutdown ?? true,
                  log_level: (globalSettings.log_level as any) ?? "INFO",
                }
                await api.updateSettings(s)
                toast.success("Global settings updated")
              } catch (err) {
                console.error(err)
                toast.error("Failed to update settings")
              } finally {
                setSaving(false)
              }
            }}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Log Level</Label>
        <div className="flex gap-2">
          {(["DEBUG", "INFO", "WARNING", "ERROR"] as const).map((level) => (
            <Button
              key={level}
              variant={config.logLevel === level ? "default" : "secondary"}
              size="sm"
              className="flex-1 h-8 text-[10px]"
              onClick={() => onChange({ ...config, logLevel: level })}
            >
              {level}
            </Button>
          ))}
        </div>
        <p className="text-[10px] text-muted-foreground">Logging verbosity level for the bot session</p>
      </div>

      <div className="p-3 bg-muted/50 rounded-md space-y-2 mt-6">
        <Label className="text-xs text-muted-foreground">Note</Label>
        <p className="text-[10px] text-muted-foreground">
          Bot-specific settings (wallet, market, strategy, risk) are configured when creating or editing bots in the Bot Manager tab.
        </p>
      </div>
    </div>
  )
}
