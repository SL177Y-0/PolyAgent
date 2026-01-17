"use client"

import type React from "react"
import { useState, useMemo } from "react"
import { ArrowUpRight, ArrowDownRight, Zap, CheckCircle2, XCircle, Clock, Settings, ChevronLeft, ChevronRight } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import type { Activity } from "@/lib/types"

interface ActivityFeedProps {
  activities: Activity[]
  pageSize?: number
}

type FilterType = "all" | "trades" | "signals" | "system"

export function ActivityFeed({ activities, pageSize = 20 }: ActivityFeedProps) {
  const [filter, setFilter] = useState<FilterType>("all")
  const [currentPage, setCurrentPage] = useState(1)

  const filteredActivities = useMemo(() => {
    return activities.filter((activity) => {
      if (filter === "all") return true
      if (filter === "trades") return ["order", "fill", "exit", "pnl"].includes(activity.type)
      if (filter === "signals") return ["signal", "spike"].includes(activity.type)
      if (filter === "system") return ["confirm", "cooldown", "error", "system"].includes(activity.type)
      return true
    })
  }, [activities, filter])

  // Reset to page 1 when filter changes
  const handleFilterChange = (newFilter: FilterType) => {
    setFilter(newFilter)
    setCurrentPage(1)
  }

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(filteredActivities.length / pageSize))
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = startIndex + pageSize
  const paginatedActivities = filteredActivities.slice(startIndex, endIndex)

  // Ensure current page is valid
  if (currentPage > totalPages && totalPages > 0) {
    setCurrentPage(totalPages)
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
        <CardTitle className="text-xs text-muted-foreground font-medium tracking-wide">ACTIVITY LOG</CardTitle>
        <div className="flex gap-1">
          {(["all", "trades", "signals", "system"] as const).map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              className={cn(
                "px-2 py-1 text-[10px] font-medium uppercase transition-colors rounded",
                filter === f ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0">
        {paginatedActivities.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">No activity yet</div>
        ) : (
          <div className="divide-y divide-border">
            {paginatedActivities.map((activity, i) => {
              // Ensure unique, stable keys even if upstream ids repeat
              const uniqueKey = `${activity.id ?? 'noid'}-${activity.timestamp}-${activity.bot_id ?? ''}`
              return <ActivityItem key={uniqueKey} activity={activity} />
            })}
          </div>
        )}
      </CardContent>

      {/* Pagination Controls */}
      {filteredActivities.length > pageSize && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-secondary/30">
          <span className="text-[10px] text-muted-foreground">
            {startIndex + 1}-{Math.min(endIndex, filteredActivities.length)} of {filteredActivities.length}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <span className="text-[10px] text-muted-foreground min-w-[60px] text-center">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function ActivityItem({ activity }: { activity: Activity }) {
  const { type, timestamp, message, details } = activity

  const typeConfig: Record<
    string,
    {
      icon: React.ReactNode
      color: string
      bgColor: string
    }
  > = {
    signal: {
      icon: <Zap className="w-3 h-3" />,
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
    spike: {
      icon: <Zap className="w-3 h-3" />,
      color: "text-warning",
      bgColor: "bg-warning/10",
    },
    order: {
      icon: <ArrowUpRight className="w-3 h-3" />,
      color: "text-info",
      bgColor: "bg-info/10",
    },
    fill: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    confirm: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    exit: {
      icon: <ArrowDownRight className="w-3 h-3" />,
      color: "text-info",
      bgColor: "bg-info/10",
    },
    pnl: {
      icon: details?.profit ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />,
      color: details?.profit ? "text-primary" : "text-destructive",
      bgColor: details?.profit ? "bg-primary/10" : "bg-destructive/10",
    },
    cooldown: {
      icon: <Clock className="w-3 h-3" />,
      color: "text-muted-foreground",
      bgColor: "bg-muted/50",
    },
    error: {
      icon: <XCircle className="w-3 h-3" />,
      color: "text-destructive",
      bgColor: "bg-destructive/10",
    },
    system: {
      icon: <Settings className="w-3 h-3" />,
      color: "text-muted-foreground",
      bgColor: "bg-muted/50",
    },
  }

  const config = typeConfig[type] || typeConfig.system

  return (
    <div className="flex items-start gap-3 px-4 py-2 hover:bg-accent/50 transition-colors">
      {/* Timestamp */}
      <span className="text-[10px] font-mono text-muted-foreground shrink-0 w-16">
        {new Date(timestamp).toLocaleTimeString("en-US", { hour12: false })}
      </span>

      {/* Type Badge */}
      <div className={cn("flex items-center gap-1 px-1.5 py-0.5 shrink-0 rounded", config.bgColor, config.color)}>
        {config.icon}
        <span className="text-[10px] font-medium uppercase">{type}</span>
      </div>

      {/* Message */}
      <p className="text-xs text-foreground flex-1 leading-relaxed">{message}</p>
    </div>
  )
}
