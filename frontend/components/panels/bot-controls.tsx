
"use client"

import { Button } from "@/components/ui/button"
import { Play, Pause, Square, Settings } from "lucide-react"
import { getApiClient } from "@/lib/api-client"

interface BotControlsProps {
  botId: string
  status: "running" | "stopped" | "paused" | "error"
  onUpdate: () => void
  onSettingsClick: () => void
}

export function BotControls({ botId, status, onUpdate, onSettingsClick }: BotControlsProps) {
  const api = getApiClient()

  const handleAction = async (action: "start" | "stop" | "pause" | "resume") => {
    try {
      if (action === "start") await api.startBot(botId)
      if (action === "stop") await api.stopBot(botId)
      if (action === "pause") await api.pauseBot(botId)
      if (action === "resume") await api.resumeBot(botId)
      onUpdate()
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="flex items-center gap-2 bg-card border rounded-lg p-2 shadow-sm">
      {status === "running" ? (
        <>
          <Button size="sm" variant="outline" onClick={() => handleAction("pause")}>
            <Pause className="h-4 w-4 mr-2" /> Pause
          </Button>
          <Button size="sm" variant="destructive" onClick={() => handleAction("stop")}>
            <Square className="h-4 w-4 mr-2" /> Stop
          </Button>
        </>
      ) : status === "paused" ? (
        <>
          <Button size="sm" variant="outline" onClick={() => handleAction("resume")}>
            <Play className="h-4 w-4 mr-2" /> Resume
          </Button>
          <Button size="sm" variant="destructive" onClick={() => handleAction("stop")}>
            <Square className="h-4 w-4 mr-2" /> Stop
          </Button>
        </>
      ) : (
        <Button size="sm" variant="default" onClick={() => handleAction("start")}>
          <Play className="h-4 w-4 mr-2" /> Start Bot
        </Button>
      )}
      
      <div className="w-px h-6 bg-border mx-2" />
      
      <Button size="sm" variant="ghost" onClick={onSettingsClick}>
        <Settings className="h-4 w-4 mr-2" /> Settings
      </Button>
    </div>
  )
}
