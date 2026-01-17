
"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { useBotState } from "@/hooks/use-bot-state"
import { getApiClient, BotStatus } from "@/lib/api-client"
import { HeaderBar } from "@/components/header-bar"
import { TradingDashboard } from "@/components/trading-dashboard"
import { ArrowLeft, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function BotTradingPage() {
  const { botId } = useParams()
  const router = useRouter()
  const { bots, selectBot, selectedBotId, refresh } = useBotState()
  const [directBot, setDirectBot] = useState<BotStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const api = getApiClient()
  
  // Fetch bot directly on page load/refresh
  const fetchBot = useCallback(async () => {
    if (!botId || typeof botId !== "string") return
    
    setLoading(true)
    try {
      // Try to get from API directly
      const bot = await api.getBot(botId)
      setDirectBot(bot)
      setError(null)
      
      // Also refresh context and select this bot
      await refresh()
      selectBot(botId)
    } catch (err) {
      console.error("Failed to fetch bot:", err)
      setError("Bot not found or failed to load")
    } finally {
      setLoading(false)
    }
  }, [botId, api, refresh, selectBot])
  
  // Fetch on mount and when botId changes
  useEffect(() => {
    fetchBot()
  }, [fetchBot])
  
  // Update directBot when context bots update (for real-time updates)
  useEffect(() => {
    if (bots.length > 0 && botId) {
      const contextBot = bots.find(b => b.bot_id === botId)
      if (contextBot) {
        setDirectBot(contextBot)
      }
    }
  }, [bots, botId])

  // Get current bot - prefer context (has real-time updates), fallback to direct fetch
  const currentBot = bots.find(b => b.bot_id === botId) || directBot

  // Back handler
  const handleBack = () => {
    router.push("/")
  }

  // Error state
  if (error && !currentBot) {
    return (
      <div className="flex flex-col items-center justify-center h-screen space-y-4">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
        </Button>
      </div>
    )
  }

  // Loading state
  if (loading && !currentBot) {
    return (
      <div className="flex flex-col items-center justify-center h-screen space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading bot...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground">
      {currentBot ? (
        <>
         <HeaderBar
           currentBot={currentBot}
           onBack={handleBack}
           onKill={async () => {
             try {
               await api.stopBot(currentBot.bot_id)
             } catch (e) {
               console.error(e)
             }
           }}
         />
          <TradingDashboard />
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-screen space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Loading bot...</p>
          <Button variant="outline" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Button>
        </div>
      )}
    </div>
  )
}
