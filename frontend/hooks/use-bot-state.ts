"use client"

// Re-export everything from the context for backwards compatibility
export { useBotState, BotStateProvider } from "@/contexts/bot-state-context"
export type { BotStatus, Activity, Position, SpikeDetection, SessionStats, TradeTarget, PricePoint } from "@/contexts/bot-state-context"
