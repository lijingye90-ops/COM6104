"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Spinner } from "@/components/ui/spinner"
import {
  Send,
  Calendar,
  CheckCircle2,
  Briefcase,
  Bot,
  User,
  ChevronDown,
  AlertCircle,
  Wrench,
  Lightbulb,
  ListChecks,
  Sparkles,
} from "lucide-react"

// --- Types ---

type SSEEventType = "plan" | "tool_start" | "tool_result" | "reasoning" | "done" | "error"

type Message = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  eventType?: SSEEventType
  data?: any
}

// --- Stats (hardcoded for now) ---

const stats = [
  { label: "已投递", value: 24, icon: Send, color: "text-blue-600", bg: "bg-blue-50" },
  { label: "面试中", value: 4, icon: Calendar, color: "text-green-600", bg: "bg-green-50" },
  { label: "已录用", value: 1, icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
]

// --- Message renderers ---

function PlanMessage({ data }: { data: any }) {
  const steps: string[] = data?.steps || []
  return (
    <Card className="border-blue-200 bg-blue-50/60">
      <CardHeader className="pb-2 pt-3 px-4">
        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-blue-700">
          <ListChecks className="size-4" />
          执行计划
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <ol className="space-y-1.5">
          {steps.map((step, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-blue-900">
              <Badge variant="secondary" className="size-5 shrink-0 flex items-center justify-center rounded-full text-xs bg-blue-200 text-blue-800 p-0">
                {i + 1}
              </Badge>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

function ToolStartMessage({ data }: { data: any }) {
  const tool = data?.tool || "未知工具"
  return (
    <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-muted/60 text-sm text-muted-foreground">
      <Wrench className="size-4 shrink-0 text-amber-600" />
      <span>正在调用 <strong className="text-foreground">{tool}</strong>...</span>
      <Spinner className="size-3.5 ml-1" />
    </div>
  )
}

function ToolResultMessage({ data }: { data: any }) {
  const tool = data?.tool || "工具"
  const result = data?.result || data?.output || JSON.stringify(data, null, 2)
  return (
    <Collapsible>
      <Card className="border-muted bg-muted/30">
        <CollapsibleTrigger asChild>
          <button className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium hover:bg-muted/50 transition-colors rounded-t-lg">
            <span className="flex items-center gap-2 text-muted-foreground">
              <Wrench className="size-4 text-green-600" />
              {tool} 执行结果
            </span>
            <ChevronDown className="size-4 text-muted-foreground transition-transform [[data-state=open]_&]:rotate-180" />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="px-4 pb-3 pt-0">
            <pre className="text-xs bg-background rounded-md p-3 overflow-x-auto whitespace-pre-wrap border">
              {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
            </pre>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

function ReasoningMessage({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed whitespace-pre-wrap">
      {content}
    </div>
  )
}

function DoneMessage({ data }: { data: any }) {
  const summary = data?.summary || data?.message || "任务完成"
  const details = data?.details || {}
  return (
    <Card className="border-emerald-200 bg-emerald-50/60">
      <CardHeader className="pb-2 pt-3 px-4">
        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-emerald-700">
          <Sparkles className="size-4" />
          任务完成
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3 space-y-2">
        <p className="text-sm text-emerald-900">{summary}</p>
        {Object.keys(details).length > 0 && (
          <div className="space-y-1">
            {Object.entries(details).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-xs">
                <span className="text-emerald-700">{key}</span>
                <span className="font-medium text-emerald-900">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ErrorMessage({ content, data }: { content: string; data?: any }) {
  return (
    <div className="flex items-start gap-2 py-2.5 px-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
      <AlertCircle className="size-4 shrink-0 mt-0.5" />
      <span>{data?.message || content || "发生错误"}</span>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="flex items-end gap-2 max-w-[75%]">
          <div className="bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-2.5 text-sm">
            {message.content}
          </div>
          <div className="size-7 shrink-0 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="size-3.5 text-primary" />
          </div>
        </div>
      </div>
    )
  }

  // Assistant message - render based on eventType
  const renderContent = () => {
    switch (message.eventType) {
      case "plan":
        return <PlanMessage data={message.data} />
      case "tool_start":
        return <ToolStartMessage data={message.data} />
      case "tool_result":
        return <ToolResultMessage data={message.data} />
      case "reasoning":
        return <ReasoningMessage content={message.content} />
      case "done":
        return <DoneMessage data={message.data} />
      case "error":
        return <ErrorMessage content={message.content} data={message.data} />
      default:
        return <ReasoningMessage content={message.content} />
    }
  }

  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-2 max-w-[85%]">
        <div className="size-7 shrink-0 rounded-full bg-muted flex items-center justify-center mt-0.5">
          <Bot className="size-3.5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          {renderContent()}
        </div>
      </div>
    </div>
  )
}

// --- Welcome message ---

const welcomeMessages: Message[] = [
  {
    id: "welcome-1",
    role: "assistant",
    content: "你好! 我是你的求职助手。我可以帮你搜索职位、定制简历、投递申请。试试告诉我你想找什么工作吧!",
  },
]

// --- Main page ---

export default function DashboardPage() {
  const [messages, setMessages] = useState<Message[]>(welcomeMessages)
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [resumePath, setResumePath] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      const viewport = scrollRef.current.querySelector("[data-slot='scroll-area-viewport']")
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight
      }
    }
  }, [messages])

  const handleSSEEvent = useCallback((eventType: string, data: any) => {
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

    switch (eventType) {
      case "plan":
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "plan",
          data,
        }])
        break
      case "tool_start":
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "tool_start",
          data,
        }])
        break
      case "tool_result":
        // Replace the last tool_start with tool_result if possible
        setMessages(prev => {
          const lastToolStartIndex = prev.findLastIndex(m => m.eventType === "tool_start")
          if (lastToolStartIndex !== -1) {
            const updated = [...prev]
            updated[lastToolStartIndex] = {
              ...updated[lastToolStartIndex],
              eventType: "tool_result",
              data,
            }
            return updated
          }
          return [...prev, {
            id,
            role: "assistant",
            content: "",
            eventType: "tool_result",
            data,
          }]
        })
        break
      case "reasoning":
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: data?.text || data?.content || "",
          eventType: "reasoning",
          data,
        }])
        break
      case "done":
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "done",
          data,
        }])
        break
      case "error":
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: data?.message || "发生错误",
          eventType: "error",
          data,
        }])
        break
      default:
        // Unknown event type, show as reasoning
        if (data?.text || data?.content || data?.message) {
          setMessages(prev => [...prev, {
            id,
            role: "assistant",
            content: data?.text || data?.content || data?.message || "",
            eventType: "reasoning",
            data,
          }])
        }
        break
    }
  }, [])

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim() || isLoading) return

    setIsLoading(true)
    const userMsgId = `user-${Date.now()}`
    setMessages(prev => [...prev, { id: userMsgId, role: "user", content: message }])

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, resume_path: resumePath }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        let eventType = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7)
          } else if (line.startsWith("data: ") && eventType) {
            try {
              const data = JSON.parse(line.slice(6))
              handleSSEEvent(eventType, data)
            } catch {
              // Ignore malformed JSON lines
            }
            eventType = ""
          }
        }
      }
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : "网络错误"
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `连接失败: ${errMsg}`,
        eventType: "error",
      }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, resumePath, handleSSEEvent])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim()) {
      sendMessage(inputValue)
      setInputValue("")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // Quick actions for empty state
  const quickActions = [
    "帮我搜索 北京 的前端工程师职位",
    "用我的简历投递这个职位",
    "帮我写一封求职信",
  ]

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] gap-4">
      {/* Top section: compact stats */}
      <div className="flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          {stats.map((stat) => (
            <Card key={stat.label} className="py-2 px-4 shadow-none">
              <div className="flex items-center gap-3">
                <div className={`size-8 rounded-lg ${stat.bg} flex items-center justify-center ${stat.color}`}>
                  <stat.icon className="size-4" />
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-xl font-bold">{stat.value}</span>
                  <span className="text-xs text-muted-foreground">{stat.label}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
        <Badge variant="outline" className="text-xs gap-1.5 py-1 shrink-0">
          <Briefcase className="size-3" />
          求职助手
        </Badge>
      </div>

      {/* Main section: Chat interface */}
      <Card className="flex-1 flex flex-col overflow-hidden min-h-0">
        <CardHeader className="py-3 px-4 border-b shrink-0">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Bot className="size-5" />
            AI 求职助手
            {isLoading && (
              <Badge variant="secondary" className="text-xs gap-1 font-normal">
                <Spinner className="size-3" />
                思考中...
              </Badge>
            )}
          </CardTitle>
        </CardHeader>

        {/* Messages area */}
        <ScrollArea className="flex-1 min-h-0" ref={scrollRef}>
          <div className="p-4 space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Quick action hints when only welcome messages */}
            {messages.length <= 1 && !isLoading && (
              <div className="pt-4 space-y-3">
                <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Lightbulb className="size-3.5" />
                  试试这些:
                </p>
                <div className="flex flex-wrap gap-2">
                  {quickActions.map((action, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      className="text-xs h-8 rounded-full"
                      onClick={() => {
                        setInputValue(action)
                        inputRef.current?.focus()
                      }}
                    >
                      {action}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input area */}
        <div className="border-t p-3 shrink-0">
          <form onSubmit={handleSubmit} className="flex items-center gap-2">
            <Input
              ref={inputRef}
              placeholder="告诉我你想找什么工作，或者需要什么帮助..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              className="flex-1 rounded-full px-4"
              autoFocus
            />
            <Button
              type="submit"
              size="icon"
              disabled={isLoading || !inputValue.trim()}
              className="rounded-full shrink-0 size-9"
            >
              {isLoading ? <Spinner className="size-4" /> : <Send className="size-4" />}
            </Button>
          </form>
        </div>
      </Card>
    </div>
  )
}
