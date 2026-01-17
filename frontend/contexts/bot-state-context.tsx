"use client"

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from "react"
import { getApiClient } from "@/lib/api-client"
import type { BotStatus, Activity, Position, SpikeDetection, SessionStats, TradeTarget, PricePoint } from "@/lib/types"

// Default empty states
const DEFAULT_POSITION: Position = {
  has_position: false,
  side: "BUY",
  entry_price: 0,
  current_price: 0,
  amount_usd: 0,
  shares: 0,
  pnl_pct: 0,
  pnl_usd: 0,
  age_seconds: 0,
  pending_settlement: false
}

const DEFAULT_SESSION_STATS: SessionStats = {
  realized_pnl: 0,
  total_trades: 0,
  winning_trades: 0
}

const DEFAULT_SPIKE_DETECTION: SpikeDetection = {
  is_active: false,
  threshold: 8.0,
  max_change_pct: 0,
  max_change_window_sec: 0,
  volatility_cv: 0,
  max_volatility_cv: 10.0,
  is_volatility_filtered: false,
  history_size: 0,
  max_history_size: 3600,
  windows: []
}

interface BotStateContextType {
  bots: BotStatus[]
  selectedBotId: string | null
  selectBot: (botId: string) => void
  position: Position
  sessionStats: SessionStats
  spikeDetection: SpikeDetection
  priceHistory: PricePoint[]
  target: TradeTarget | null
  activities: Activity[]
  isConnected: boolean
  error: string | null
  refresh: () => Promise<BotStatus[]>
}

const BotStateContext = createContext<BotStateContextType | null>(null)

export function BotStateProvider({ children }: { children: ReactNode }) {
  const [bots, setBots] = useState<BotStatus[]>([])
  const [selectedBotId, setSelectedBotId] = useState<string | null>(null)

  // Per-bot caches for real-time retention
  const positionsRef = useRef<Record<string, Position>>({})
  const statsRef = useRef<Record<string, SessionStats>>({})
  const spikeRef = useRef<Record<string, SpikeDetection>>({})
  const historyRef = useRef<Record<string, PricePoint[]>>({})
  const targetRef = useRef<Record<string, TradeTarget | null>>({})
  const activitiesRef = useRef<Record<string, Activity[]>>({})

  // Derived selected state (exposed to consumers)
  const [position, setPosition] = useState<Position>(DEFAULT_POSITION)
  const [sessionStats, setSessionStats] = useState<SessionStats>(DEFAULT_SESSION_STATS)
  const [spikeDetection, setSpikeDetection] = useState<SpikeDetection>(DEFAULT_SPIKE_DETECTION)
  const [priceHistory, setPriceHistory] = useState<PricePoint[]>([])
  const [target, setTarget] = useState<TradeTarget | null>(null)
  const [activities, setActivities] = useState<Activity[]>([])

  // Connection state
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const api = getApiClient()
  const wsConnectedRef = useRef(false)
  const initialSelectDoneRef = useRef(false)

  // Helper: update caches from a BotStatus payload
  const cacheFromBotStatus = useCallback((bot: BotStatus) => {
    const id = bot.bot_id
    // Position with current price enrichment
    const pos = bot.position || DEFAULT_POSITION
    const enrichedPos = bot.current_price && bot.current_price > 0 ? { ...pos, current_price: bot.current_price } : pos
    positionsRef.current[id] = enrichedPos

    statsRef.current[id] = bot.session_stats || DEFAULT_SESSION_STATS
    // Normalize spike detection to SpikeDetection shape when present
    if (bot.spike_detection) {
      spikeRef.current[id] = bot.spike_detection
    }

    // Only seed history if empty, and convert time to milliseconds
    const existing = historyRef.current[id] || []
    if ((bot.price_history_sample?.length || 0) > existing.length) {
      // Convert backend time (seconds) to milliseconds for chart
      historyRef.current[id] = (bot.price_history_sample || []).map((p: any) => ({
        time: p.time * 1000,
        price: p.price
      }))
    }
  }, [])

  // When selectedBotId changes, project cached state to derived values
  useEffect(() => {
    if (!selectedBotId) return
    setPosition(positionsRef.current[selectedBotId] || DEFAULT_POSITION)
    setSessionStats(statsRef.current[selectedBotId] || DEFAULT_SESSION_STATS)
    setSpikeDetection(spikeRef.current[selectedBotId] || DEFAULT_SPIKE_DETECTION)
    setPriceHistory(historyRef.current[selectedBotId] || [])
    setTarget(targetRef.current[selectedBotId] || null)
    setActivities(activitiesRef.current[selectedBotId] || [])
  }, [selectedBotId])

  // Update caches and derived state from a bot object
  const updateBotState = useCallback((bot: BotStatus) => {
    cacheFromBotStatus(bot)
    if (selectedBotId && bot.bot_id === selectedBotId) {
      setPosition(positionsRef.current[selectedBotId])
      setSessionStats(statsRef.current[selectedBotId])
      setSpikeDetection(spikeRef.current[selectedBotId] || DEFAULT_SPIKE_DETECTION)
      setPriceHistory(historyRef.current[selectedBotId] || [])
      setTarget(targetRef.current[selectedBotId] || null)
      setActivities(activitiesRef.current[selectedBotId] || [])
    }
  }, [cacheFromBotStatus, selectedBotId])

  // Fetch initial state
  const fetchState = useCallback(async () => {
    try {
      const { bots: botsList } = await api.getBots()
      setBots(botsList)

      // Auto-select first bot if none selected (only once)
      if (!initialSelectDoneRef.current && botsList.length > 0) {
        initialSelectDoneRef.current = true
        const firstBotId = botsList[0].bot_id
        setSelectedBotId(firstBotId)
        // Update state immediately for the first bot
        updateBotState(botsList[0])
      }

      setError(null)

      // Return bots list for callers that need it
      return botsList
    } catch (err) {
      console.error("Failed to fetch bot state:", err)
      setError("Failed to connect to backend")
      return []
    }
  }, [api, updateBotState])

  // Fetch detailed data for selected bot
  const fetchBotDetails = useCallback(async (botId: string) => {
    try {
      const [targetRes, activitiesRes, priceHistoryRes] = await Promise.all([
        api.getTarget(botId),
        api.getActivities(botId),
        api.getPriceHistory(botId)
      ])

      setTarget(targetRes.target)
      setActivities(activitiesRes.activities)

      // Update price history from dedicated endpoint if available
      if (priceHistoryRes.data && priceHistoryRes.data.length > 0) {
        setPriceHistory(priceHistoryRes.data)
      }
    } catch (err) {
      console.error("Failed to fetch bot details:", err)
    }
  }, [api])

  // WebSocket event handlers - global events
  useEffect(() => {
    api.connectWebSocket()

    const handleInit = () => {
      wsConnectedRef.current = true
      setIsConnected(true)
      fetchState()
    }

    const handleBotChange = () => fetchState()

    const handleError = (data: { bot_id?: string; data?: { message?: string } }) => {
      if (data.bot_id === selectedBotId || !data.bot_id) {
        const newActivity: Activity = {
          id: `err_${Date.now()}`,
          timestamp: Math.floor(Date.now() / 1000),
          type: "error",
          message: data.data?.message || "Unknown error",
          bot_id: data.bot_id
        }
        setActivities(prev => [newActivity, ...prev].slice(0, 100))
      }
    }

    api.on("init", handleInit)
    api.on("bot_created", handleBotChange)
    api.on("bot_deleted", handleBotChange)
    api.on("bot_started", handleBotChange)
    api.on("bot_stopped", handleBotChange)
    api.on("bot_paused", handleBotChange)
    api.on("bot_resumed", handleBotChange)
    api.on("bot_updated", handleBotChange)
    api.on("error", handleError)
    api.on("settings_updated", () => fetchState())

    return () => {
      api.off("init")
      api.off("bot_created")
      api.off("bot_deleted")
      api.off("bot_started")
      api.off("bot_stopped")
      api.off("bot_paused")
      api.off("bot_resumed")
      api.off("bot_updated")
      api.off("error")
      api.off("settings_updated")
      // Clean up WebSocket connection
      api.disconnectWebSocket()
    }
  }, [api, fetchState, selectedBotId])

  // Bot-specific WebSocket handlers
  useEffect(() => {
    if (!selectedBotId) return

    // Fetch fresh data for this bot
    const loadBotData = async () => {
      // Fetch details (target, activities)
      fetchBotDetails(selectedBotId)

      // Fetch fresh bot list and update state
      const freshBots = await fetchState()
      const currentBot = freshBots.find((b: BotStatus) => b.bot_id === selectedBotId)
      if (currentBot) {
        updateBotState(currentBot)
      }
    }

    loadBotData()

    // Subscribe to bot-specific events
    const eventTypes = {
      price_update: `price_update:${selectedBotId}`,
      position_update: `position_update:${selectedBotId}`,
      spike_detected: `spike_detected:${selectedBotId}`,
      target_update: `target_update:${selectedBotId}`,
      activity: `activity:${selectedBotId}`,
      trade_executed: `trade_executed:${selectedBotId}`,
      position_closed: `position_closed:${selectedBotId}`
    }

    const handlePriceUpdate = (data: any) => {
      // Handle both formats: { bot_id, timestamp, data: { price } } and { bot_id, data: { price } }
      const price = data?.data?.price || data?.price
      const botId = data?.bot_id || data?.data?.bot_id

      if (price && botId) {
        const newItem: PricePoint = {
          time: data?.timestamp || data?.data?.timestamp || Math.floor(Date.now() / 1000),
          price: price
        }
        const existing = historyRef.current[botId] || []
        historyRef.current[botId] = [...existing.slice(-299), newItem]
        if (botId === selectedBotId) {
          setPriceHistory(historyRef.current[botId])
        }
      }
    }

    const handlePositionUpdate = (data: any) => {
      // Handle both formats: direct position data or nested in data property
      const pos = data?.data || data
      const botId = data?.bot_id || pos?.bot_id

      if (pos && botId) {
        positionsRef.current[botId] = pos
        if (botId === selectedBotId) setPosition(pos)
      }
    }

    const handleSpikeDetected = () => {
      fetchState()
    }

    const handleTargetUpdate = (data: any) => {
      // Handle both formats: { data: { target } } or { target }
      const target = data?.data?.target || data?.target || data?.data
      const botId = data?.bot_id || data?.data?.bot_id

      if (target && botId) {
        targetRef.current[botId] = target
        if (botId === selectedBotId) setTarget(target)
      }
    }

    const handleActivity = (data: any) => {
      // Handle both formats: { data: Activity } or { bot_id, data: { activity } }
      const activityPayload = data?.data?.activity || data?.activity || data?.data
      const botId = data?.bot_id || data?.data?.bot_id || activityPayload?.bot_id

      if (activityPayload && botId) {
        const activity: Activity = {
          id: activityPayload.id || `act_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: activityPayload.timestamp || data?.timestamp || Math.floor(Date.now() / 1000),
          type: activityPayload.type || "system",
          message: activityPayload.message || "Activity",
          details: activityPayload.details,
          bot_id: botId
        }
        const list = activitiesRef.current[botId] || []
        activitiesRef.current[botId] = [activity, ...list].slice(0, 100)
        if (botId === selectedBotId) {
          setActivities(activitiesRef.current[botId])
        }
      }
    }

    // Handle trade executed - refresh state and add activity
    const handleTradeExecuted = (data: { bot_id?: string; data?: { side?: string; amount_usd?: number; order_id?: string } }) => {
      if (!data.bot_id) return
      const id = data.bot_id
      // Refresh to get updated position and stats
      fetchState()
      fetchBotDetails(id)

      // Add trade activity immediately for responsiveness
      if (data.data) {
        const tradeActivity: Activity = {
          id: `trade_${Date.now()}`,
          timestamp: Math.floor(Date.now() / 1000),
          type: "fill",
          message: `${data.data.side} $${data.data.amount_usd?.toFixed(2)} executed`,
          bot_id: id
        }
        const list = activitiesRef.current[id] || []
        activitiesRef.current[id] = [tradeActivity, ...list].slice(0, 100)
        if (id === selectedBotId) setActivities(activitiesRef.current[id])
      }
    }

    // Handle position closed - reset position and refresh
    const handlePositionClosed = (data?: { bot_id?: string }) => {
      const id = data?.bot_id || selectedBotId
      if (!id) return
      if (id === selectedBotId) setPosition(DEFAULT_POSITION)
      fetchState()
      fetchBotDetails(id)
    }

    api.on(eventTypes.price_update, handlePriceUpdate)
    api.on(eventTypes.position_update, handlePositionUpdate)
    api.on(eventTypes.spike_detected, handleSpikeDetected)
    api.on(eventTypes.target_update, handleTargetUpdate)
    api.on(eventTypes.activity, handleActivity)
    api.on(eventTypes.trade_executed, handleTradeExecuted)
    api.on(eventTypes.position_closed, handlePositionClosed)

    // Request initial subscription
    api.send({ type: "subscribe_bot", bot_id: selectedBotId })

    return () => {
      Object.values(eventTypes).forEach(type => api.off(type))
    }
  }, [api, selectedBotId, fetchBotDetails, fetchState, updateBotState])

  // Polling fallback for bots list, and enrich spike detection for selected bot
  useEffect(() => {
    const botsInterval = setInterval(fetchState, 5000)
    let spikeInterval: NodeJS.Timeout | null = null
    let detailsInterval: NodeJS.Timeout | null = null

    const startSpikePolling = async () => {
      if (!selectedBotId) return
      // Light-weight polling to enrich SpikeDetection with latest server computation
      spikeInterval = setInterval(async () => {
        try {
          const status = await api.getSpikeStatus(selectedBotId)
          // Map directly since backend now aligns to SpikeDetection
          spikeRef.current[selectedBotId] = status as SpikeDetection
          setSpikeDetection(spikeRef.current[selectedBotId])
        } catch (e) {
          // ignore network errors
        }
      }, 3000)
    }

    // Poll price history and activities more frequently when bot is running
    const startDetailsPolling = async () => {
      if (!selectedBotId) return

      detailsInterval = setInterval(async () => {
        try {
          // Fetch price history
          const priceRes = await api.getPriceHistory(selectedBotId)
          if (priceRes.data && priceRes.data.length > 0) {
            // Convert API response to PricePoint format (convert seconds to ms)
            const newHistory: PricePoint[] = priceRes.data.map((p: any) => ({
              time: p.time * 1000,
              price: p.price
            }))
            historyRef.current[selectedBotId] = newHistory
            setPriceHistory(newHistory)
          }

          // Fetch activities
          const activitiesRes = await api.getActivities(selectedBotId, 50)
          if (activitiesRes.activities && activitiesRes.activities.length > 0) {
            activitiesRef.current[selectedBotId] = activitiesRes.activities
            setActivities(activitiesRes.activities)
          }

          // Fetch target
          const targetRes = await api.getTarget(selectedBotId)
          if (targetRes.target) {
            targetRef.current[selectedBotId] = targetRes.target
            setTarget(targetRes.target)
          }
        } catch (e) {
          // ignore network errors during polling
        }
      }, 1000) // Poll every 2 seconds
    }

    startSpikePolling()
    startDetailsPolling()

    return () => {
      clearInterval(botsInterval)
      if (spikeInterval) clearInterval(spikeInterval)
      if (detailsInterval) clearInterval(detailsInterval)
    }
  }, [fetchState, api, selectedBotId])

  // Stable selectBot function - CLEAR state immediately to prevent stale data
  const selectBot = useCallback((botId: string) => {
    // Clear all bot-specific state immediately when switching bots
    setPosition(DEFAULT_POSITION)
    setSessionStats(DEFAULT_SESSION_STATS)
    setSpikeDetection(DEFAULT_SPIKE_DETECTION)
    setPriceHistory([])
    setTarget(null)
    setActivities([])

    // Then set the new bot ID (triggers loadBotData via useEffect)
    setSelectedBotId(botId)
  }, [])

  return (
    <BotStateContext.Provider value={{
      bots,
      selectedBotId,
      selectBot,
      position,
      sessionStats,
      spikeDetection,
      priceHistory,
      target,
      activities,
      isConnected,
      error,
      refresh: fetchState
    }}>
      {children}
    </BotStateContext.Provider>
  )
}

export function useBotState() {
  const context = useContext(BotStateContext)
  if (!context) {
    throw new Error("useBotState must be used within a BotStateProvider")
  }
  return context
}

// Re-export types
export type { BotStatus, Activity, Position, SpikeDetection, SessionStats, TradeTarget, PricePoint }
