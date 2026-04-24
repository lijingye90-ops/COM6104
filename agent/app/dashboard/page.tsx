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
  Clock3,
  Activity,
  CheckCheck,
  RotateCcw,
} from "lucide-react"
import { getDefaultResumePath } from "@/lib/resume-store"

// --- Types ---

type SSEEventType = "plan" | "tool_start" | "tool_progress" | "tool_result" | "reasoning" | "decision" | "done" | "error" | "memory" | "workflow"

type Message = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  eventType?: SSEEventType
  data?: any
}

type Application = {
  status: string
}

type PersistedChatMessage = {
  id: number
  role: "user" | "assistant" | "system"
  event_type: string
  content: string
  data?: any
}

type WorkflowAgentCard = {
  label: string
  title: string
  status: "pending" | "running" | "done" | "error"
  detail: string
}

type WorkflowState = {
  conversation_id: string
  goal: string
  status: string
  current_stage: string
  recommended_job?: {
    company?: string
    title?: string
    url?: string
  }
  artifact_paths?: {
    resume_file_path?: string
    cover_letter_path?: string
  }
  apply_result?: {
    status?: string
    detail?: string
    reason?: string
  }
  last_error?: string
  agents?: Record<string, WorkflowAgentCard>
}

type AgentStatus = "idle" | "running" | "done" | "error"

type AgentActivityItem = {
  id: string
  type: Exclude<SSEEventType, "plan">
  title: string
  detail: string
}

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

function ToolProgressMessage({ data }: { data: any }) {
  const tool = data?.tool || "工具"
  const message = data?.message || data?.detail || "工具正在处理中"
  const stage = data?.stage ? `阶段: ${data.stage}` : ""
  return (
    <div className="flex items-start gap-2 py-2 px-3 rounded-lg bg-amber-50/70 border border-amber-200 text-sm text-amber-900">
      <Activity className="size-4 shrink-0 mt-0.5 text-amber-600" />
      <div className="min-w-0 space-y-1">
        <div>
          <strong>{tool}</strong> {message}
        </div>
        {stage && <div className="text-xs text-amber-700">{stage}</div>}
      </div>
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
  const lastToolResult = data?.last_tool_result
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
        {lastToolResult && (
          <div className="rounded-lg border border-emerald-200 bg-white/80 p-3 space-y-1.5">
            <div className="text-xs font-medium text-emerald-700">最后一个可用结果</div>
            <div className="text-sm text-emerald-900">
              <strong>{lastToolResult.tool}</strong>
            </div>
            <pre className="text-xs bg-background rounded-md p-2 overflow-x-auto whitespace-pre-wrap border">
              {typeof lastToolResult.result === "string"
                ? lastToolResult.result
                : JSON.stringify(lastToolResult.result, null, 2)}
            </pre>
          </div>
        )}
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

function WorkflowAgentCards({ workflowState }: { workflowState: WorkflowState | null }) {
  const cards = Object.values(workflowState?.agents || {})
  if (cards.length === 0) {
    return (
      <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
        这里会展示 Agent A/B/C 的分工、当前阶段和交接状态。
      </div>
    )
  }

  const statusStyles: Record<string, string> = {
    pending: "border-muted bg-muted/20 text-muted-foreground",
    running: "border-amber-200 bg-amber-50 text-amber-900",
    done: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-red-200 bg-red-50 text-red-900",
  }

  const statusLabels: Record<string, string> = {
    pending: "待命",
    running: "执行中",
    done: "已完成",
    error: "异常",
  }

  return (
    <div className="grid gap-2">
      {cards.map((card) => (
        <div key={`${card.label}-${card.title}`} className={`rounded-lg border px-3 py-3 ${statusStyles[card.status] || statusStyles.pending}`}>
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-xs font-medium opacity-80">{card.label}</div>
              <div className="text-sm font-semibold">{card.title}</div>
            </div>
            <Badge variant="outline" className="bg-white/80">
              {statusLabels[card.status] || card.status}
            </Badge>
          </div>
          <div className="mt-2 text-xs whitespace-pre-wrap break-words opacity-90">
            {card.detail}
          </div>
        </div>
      ))}
    </div>
  )
}

function WorkflowSnapshot({ workflowState }: { workflowState: WorkflowState | null }) {
  if (!workflowState) {
    return (
      <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
        刷新恢复后，这里会显示当前 workflow 阶段、推荐岗位、材料路径和投递状态。
      </div>
    )
  }

  return (
    <div className="space-y-2 rounded-lg border bg-muted/20 px-3 py-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">当前阶段</span>
        <span className="font-medium">{workflowState.current_stage || "started"}</span>
      </div>
      {workflowState.recommended_job?.title && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">推荐岗位</span>
          <span className="font-medium text-right">
            {workflowState.recommended_job.company} / {workflowState.recommended_job.title}
          </span>
        </div>
      )}
      {workflowState.artifact_paths?.resume_file_path && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">定制简历</span>
          <span className="font-medium text-right break-all">
            {workflowState.artifact_paths.resume_file_path}
          </span>
        </div>
      )}
      {workflowState.apply_result?.status && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">投递状态</span>
          <span className="font-medium">{workflowState.apply_result.status}</span>
        </div>
      )}
      {workflowState.last_error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-2 py-2 text-xs text-red-700">
          {workflowState.last_error}
        </div>
      )}
    </div>
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
      case "tool_progress":
        return <ToolProgressMessage data={message.data} />
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

function buildActivityItem(eventType: string, data: any, content: string): AgentActivityItem | null {
  switch (eventType) {
    case "plan":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "reasoning",
        title: "执行计划已生成",
        detail: Array.isArray(data?.steps) ? data.steps.map((step: string, index: number) => `${index + 1}. ${step}`).join("\n") : "Agent 已输出执行计划",
      }
    case "tool_start":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "tool_start",
        title: `开始执行 ${data?.tool || "工具"}`,
        detail: data?.args ? JSON.stringify(data.args, null, 2) : "等待工具返回结果",
      }
    case "tool_progress":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "tool_progress",
        title: `${data?.tool || "工具"} 进行中`,
        detail: [
          data?.message || "工具执行中",
          data?.stage ? `stage: ${data.stage}` : "",
          data?.url ? `url: ${data.url}` : "",
        ].filter(Boolean).join("\n"),
      }
    case "tool_result":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "tool_result",
        title: `${data?.tool || "工具"} 已返回`,
        detail:
          typeof data?.result === "string"
            ? data.result
            : JSON.stringify(data?.result ?? {}, null, 2),
      }
    case "reasoning":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "reasoning",
        title: "Agent 分析",
        detail: content || data?.text || data?.content || "",
      }
    case "workflow":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "workflow",
        title: "Workflow 状态更新",
        detail: JSON.stringify(
          {
            stage: data?.current_stage,
            status: data?.status,
            recommended_job: data?.recommended_job?.title,
            apply_status: data?.apply_result?.status,
          },
          null,
          2
        ),
      }
    case "decision":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "decision",
        title: `${data?.label || data?.stage || "模型决策"}`,
        detail: [
          data?.reason ? `原因: ${data.reason}` : "",
          data?.mode ? `模式: ${data.mode}` : "",
          typeof data?.headless === "boolean" ? `后台运行: ${data.headless ? "是" : "否"}` : "",
          data?.model ? `模型: ${data.model}` : "",
          data?.reasoning_effort ? `推理强度: ${data.reasoning_effort}` : "",
          typeof data?.thinking_enabled === "boolean" ? `Thinking: ${data.thinking_enabled ? "开启" : "关闭"}` : "",
          data?.base_url ? `节点: ${data.base_url}` : "",
          data?.error ? `异常: ${data.error}` : "",
        ].filter(Boolean).join("\n"),
      }
    case "done":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "done",
        title: "任务完成",
        detail: data?.message || "本轮任务已结束",
      }
    case "error":
      return {
        id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "error",
        title: "任务异常",
        detail: data?.message || content || "发生错误",
      }
    default:
      return null
  }
}

function MonitorStatusBadge({ status }: { status: AgentStatus }) {
  if (status === "running") {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <Spinner className="size-3" />
        执行中
      </Badge>
    )
  }
  if (status === "done") {
    return (
      <Badge variant="secondary" className="gap-1.5 bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
        <CheckCheck className="size-3" />
        已完成
      </Badge>
    )
  }
  if (status === "error") {
    return (
      <Badge variant="secondary" className="gap-1.5 bg-red-100 text-red-700 hover:bg-red-100">
        <AlertCircle className="size-3" />
        异常
      </Badge>
    )
  }
  return <Badge variant="outline">待命</Badge>
}

// --- Main page ---

export default function DashboardPage() {
  const [messages, setMessages] = useState<Message[]>(welcomeMessages)
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [resumePath, setResumePath] = useState("")
  const [agentStatus, setAgentStatus] = useState<AgentStatus>("idle")
  const [currentTool, setCurrentTool] = useState("")
  const [planSteps, setPlanSteps] = useState<string[]>([])
  const [agentActivities, setAgentActivities] = useState<AgentActivityItem[]>([])
  const [modelDecisions, setModelDecisions] = useState<AgentActivityItem[]>([])
  const [reasoningTrace, setReasoningTrace] = useState<AgentActivityItem[]>([])
  const [lastToolResult, setLastToolResult] = useState<any>(null)
  const [finalMessage, setFinalMessage] = useState("")
  const [lastSubmittedMessage, setLastSubmittedMessage] = useState("")
  const [conversationId, setConversationId] = useState("")
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null)
  const [stats, setStats] = useState([
    { label: "已投递", value: 0, icon: Send, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "面试中", value: 0, icon: Calendar, color: "text-green-600", bg: "bg-green-50" },
    { label: "已录用", value: 0, icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
  ])
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const activeRequestRef = useRef<AbortController | null>(null)
  const requestSeqRef = useRef(0)

  useEffect(() => {
    setResumePath(getDefaultResumePath())
  }, [])

  useEffect(() => {
    const storedConversationId = window.localStorage.getItem("job-hunt-conversation-id") || ""
    if (!storedConversationId) {
      return
    }

    const loadHistory = async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/chat/history?conversation_id=${encodeURIComponent(storedConversationId)}`
        )
        if (!response.ok) {
          return
        }
        const payload = await response.json()
        const persisted: PersistedChatMessage[] = Array.isArray(payload?.messages) ? payload.messages : []
        setConversationId(storedConversationId)
        if (payload?.workflow) {
          setWorkflowState(payload.workflow)
        }
        const mem = payload?.memory || {}
        if (Object.keys(mem).length > 0) {
          // store memory items for monitoring and UI
          setMessages((prev) => [
            ...prev,
            {
              id: `memory-${Date.now()}`,
              role: "system",
              content: `持久记忆同步:\n${Object.entries(mem).map(([k, v]) => `${k}: ${v}`).join('\n')}`,
              eventType: "memory",
              data: mem,
            },
          ])
          if (mem.last_resume_path) {
            setResumePath(mem.last_resume_path)
          }
        }
        if (persisted.length === 0) {
          return
        }
        setMessages(
          persisted.map((item) => ({
            id: `persisted-${item.id}`,
            role: item.role,
            content: item.content || "",
            eventType: (item.event_type as SSEEventType) || undefined,
            data: item.data,
          }))
        )
        const lastAssistant = [...persisted].reverse().find((item) => item.role === "assistant")
        if (lastAssistant?.content) {
          setFinalMessage(lastAssistant.content)
        }
      } catch {
        // Ignore history restore failures.
      }
    }

    void loadHistory()
  }, [])

  useEffect(() => {
    const loadApplications = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/applications")
        const applications: Application[] = await response.json()
        if (!response.ok || !Array.isArray(applications)) {
          return
        }

        const applied = applications.filter((item) => item.status === "applied").length
        const interviewing = applications.filter((item) => item.status === "interview").length
        const hired = applications.filter((item) => item.status === "offer").length

        setStats([
          { label: "已投递", value: applied, icon: Send, color: "text-blue-600", bg: "bg-blue-50" },
          { label: "面试中", value: interviewing, icon: Calendar, color: "text-green-600", bg: "bg-green-50" },
          { label: "已录用", value: hired, icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
        ])
      } catch {
        // Keep zero-state stats when backend is unavailable.
      }
    }

    void loadApplications()
  }, [])

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
    const content = data?.text || data?.content || data?.message || ""
    const activity = buildActivityItem(eventType, data, content)

    if (activity) {
      setAgentActivities((prev) => [activity, ...prev].slice(0, 12))
      if (eventType === "decision") {
        setModelDecisions((prev) => [activity, ...prev].slice(0, 12))
      }
      if (eventType === "reasoning" || eventType === "plan") {
        setReasoningTrace((prev) => [activity, ...prev].slice(0, 8))
      }
    }

    switch (eventType) {
      case "plan":
        setPlanSteps(Array.isArray(data?.steps) ? data.steps : [])
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "plan",
          data,
        }])
        break
      case "tool_start":
        setAgentStatus("running")
        setCurrentTool(data?.tool || "")
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "tool_start",
          data,
        }])
        break
      case "tool_progress":
        setAgentStatus("running")
        setCurrentTool(data?.tool || "")
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: data?.message || "",
          eventType: "tool_progress",
          data,
        }])
        break
      case "tool_result":
        setLastToolResult(data?.result ?? null)
        setCurrentTool("")
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
        setAgentStatus("running")
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: data?.text || data?.content || "",
          eventType: "reasoning",
          data,
        }])
        break
      case "workflow":
        setWorkflowState(data ?? null)
        break
      case "decision":
        break
      case "done":
        setAgentStatus("done")
        setCurrentTool("")
        setFinalMessage(data?.summary || data?.message || "任务完成")
        if (data?.workflow_state) {
          setWorkflowState(data.workflow_state)
        }
        if (data?.last_tool_result) {
          setLastToolResult(data.last_tool_result)
        }
        setMessages(prev => [...prev, {
          id,
          role: "assistant",
          content: "",
          eventType: "done",
          data,
        }])
        break
      case "error":
        setAgentStatus("error")
        setCurrentTool("")
        setFinalMessage(data?.message || "发生错误")
        if (data?.workflow_state) {
          setWorkflowState(data.workflow_state)
        }
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
    const trimmedMessage = message.trim()
    if (!trimmedMessage) return

    activeRequestRef.current?.abort()
    const controller = new AbortController()
    activeRequestRef.current = controller
    requestSeqRef.current += 1
    const requestSeq = requestSeqRef.current
    setLastSubmittedMessage(trimmedMessage)

    setIsLoading(true)
    setAgentStatus("running")
    setCurrentTool("")
    setPlanSteps([])
    setAgentActivities([])
    setModelDecisions([])
    setReasoningTrace([])
    setLastToolResult(null)
    setFinalMessage("")
    const userMsgId = `user-${Date.now()}`
    setMessages(prev => [...prev, { id: userMsgId, role: "user", content: trimmedMessage }])

    // ✅ 添加重试逻辑
    let retryCount = 0
    const MAX_RETRIES = 3
    const INITIAL_DELAY = 1000 // 1 秒

    const attemptConnect = async (): Promise<void> => {
      try {
        const response = await fetch("http://localhost:8000/api/workflow/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            goal: trimmedMessage,
            resume_path: resumePath,
            conversation_id: conversationId || undefined,
          }),
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        const returnedConversationId = response.headers.get("X-Conversation-Id") || ""
        if (returnedConversationId) {
          setConversationId(returnedConversationId)
          window.localStorage.setItem("job-hunt-conversation-id", returnedConversationId)
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
                if (requestSeq === requestSeqRef.current) {
                  handleSSEEvent(eventType, data)
                }
              } catch {
                // Ignore malformed JSON lines
              }
              eventType = ""
            }
          }
        }
        // 成功完成，重置重试计数
        retryCount = 0
      } catch (error) {
        if (controller.signal.aborted) {
          if (requestSeq === requestSeqRef.current) {
            setAgentStatus("idle")
            setCurrentTool("")
            setFinalMessage("本轮任务已停止，可直接重试")
          }
          return
        }

        const errMsg = error instanceof Error ? error.message : "网络错误"
        
        // ✅ 自动重连逻辑：网络错误时自动重试（最多3次）
        if (retryCount < MAX_RETRIES && errMsg.includes("network")) {
          retryCount++
          const delay = INITIAL_DELAY * Math.pow(2, retryCount - 1) // 指数退避：1s, 2s, 4s
          
          if (requestSeq === requestSeqRef.current) {
            setFinalMessage(`连接中断，${delay / 1000}秒后自动重连... (第 ${retryCount}/${MAX_RETRIES} 次)`)
            setMessages(prev => [...prev, {
              id: `retry-${Date.now()}`,
              role: "system",
              content: `连接中断，${delay / 1000}秒后自动重连... (第 ${retryCount}/${MAX_RETRIES} 次)`,
              eventType: "reasoning",
            }])
          }

          // 等待后重试
          await new Promise(resolve => setTimeout(resolve, delay))
          
          // 检查是否已被中止
          if (!controller.signal.aborted && requestSeq === requestSeqRef.current) {
            return attemptConnect() // 递归重试
          }
          return
        }

        // 重试次数用尽，返回错误
        if (requestSeq === requestSeqRef.current) {
          setAgentStatus("error")
          setFinalMessage(`连接失败: ${errMsg}${retryCount > 0 ? ` (重试 ${retryCount} 次仍失败)` : ""}`)
          setMessages(prev => [...prev, {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `连接失败: ${errMsg}${retryCount > 0 ? ` (重试 ${retryCount} 次仍失败)` : ""}`,
            eventType: "error",
          }])
        }
      }
    }

    try {
      await attemptConnect()
    } finally {
      if (requestSeq === requestSeqRef.current) {
        activeRequestRef.current = null
        setIsLoading(false)
      }
    }
  }, [resumePath, conversationId, handleSSEEvent])

  const retryLastMessage = useCallback(() => {
    if (!lastSubmittedMessage) return
    void sendMessage(lastSubmittedMessage)
  }, [lastSubmittedMessage, sendMessage])

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

      <div className="grid flex-1 min-h-0 gap-4 xl:grid-cols-[minmax(0,1.5fr)_380px]">
        <Card className="flex flex-col overflow-hidden min-h-0">
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

          <ScrollArea className="flex-1 min-h-0" ref={scrollRef}>
            <div className="p-4 space-y-4">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

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

        <Card className="flex flex-col min-h-0 overflow-hidden">
          <CardHeader className="py-3 px-4 border-b shrink-0 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Activity className="size-5" />
                Agent 执行预览
              </CardTitle>
              <div className="flex items-center gap-2">
                {lastSubmittedMessage && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5"
                    onClick={retryLastMessage}
                  >
                    <RotateCcw className="size-3.5" />
                    重试本轮
                  </Button>
                )}
                <MonitorStatusBadge status={agentStatus} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-muted-foreground mb-1">当前工具</div>
                <div className="font-medium text-foreground break-all">
                  {currentTool || "等待中"}
                </div>
              </div>
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-muted-foreground mb-1">最终状态</div>
                <div className="font-medium text-foreground line-clamp-2">
                  {finalMessage || "本轮还没有结束"}
                </div>
              </div>
            </div>
          </CardHeader>

          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Bot className="size-4 text-indigo-600" />
                  Agent 分工
                </div>
                <WorkflowAgentCards workflowState={workflowState} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Briefcase className="size-4 text-emerald-600" />
                  Workflow 快照
                </div>
                <WorkflowSnapshot workflowState={workflowState} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <ListChecks className="size-4 text-blue-600" />
                  执行计划
                </div>
                {planSteps.length > 0 ? (
                  <div className="space-y-2">
                    {planSteps.map((step, index) => (
                      <div key={`${step}-${index}`} className="flex items-start gap-2 rounded-lg border bg-blue-50/50 px-3 py-2 text-sm">
                        <Badge variant="secondary" className="size-5 rounded-full p-0 flex items-center justify-center bg-blue-100 text-blue-700">
                          {index + 1}
                        </Badge>
                        <span className="text-blue-950">{step}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
                    Agent 还没产出结构化计划，收到执行计划后会显示在这里。
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Bot className="size-4 text-sky-600" />
                  思考摘要
                </div>
                {reasoningTrace.length > 0 ? (
                  <div className="space-y-2">
                    {reasoningTrace.map((item) => (
                      <div key={item.id} className="rounded-lg border bg-sky-50/40 px-3 py-2.5">
                        <div className="text-sm font-medium text-sky-950">{item.title}</div>
                        <pre className="mt-1 text-xs whitespace-pre-wrap break-words text-sky-900/80">
                          {item.detail}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
                    这里显示的是可展示的思考摘要，不是模型原始私有推理链。你会看到计划、判断、下一步和降级原因。
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="size-4 text-fuchsia-600" />
                  模型决策
                </div>
                {modelDecisions.length > 0 ? (
                  <div className="space-y-2">
                    {modelDecisions.map((item) => (
                      <div key={item.id} className="rounded-lg border bg-fuchsia-50/40 px-3 py-2.5">
                        <div className="text-sm font-medium text-fuchsia-950">{item.title}</div>
                        <pre className="mt-1 text-xs whitespace-pre-wrap break-words text-fuchsia-900/80">
                          {item.detail}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
                    这里会显示每一步为什么选这个模型，是否开启 thinking，以及是否发生了重试或切池。
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Clock3 className="size-4 text-amber-600" />
                  最近动作
                </div>
                {agentActivities.length > 0 ? (
                  <div className="space-y-2">
                    {agentActivities.map((item) => (
                      <div key={item.id} className="rounded-lg border bg-background px-3 py-2.5">
                        <div className="text-sm font-medium">{item.title}</div>
                        <pre className="mt-1 text-xs whitespace-pre-wrap break-words text-muted-foreground">
                          {item.detail}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
                    这里会实时显示搜索、定制简历、面试准备、自动申请等动作。
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Wrench className="size-4 text-green-600" />
                  最新可用结果
                </div>
                {lastToolResult ? (
                  <pre className="rounded-lg border bg-muted/20 p-3 text-xs whitespace-pre-wrap break-words overflow-x-auto">
                    {typeof lastToolResult === "string"
                      ? lastToolResult
                      : JSON.stringify(lastToolResult, null, 2)}
                  </pre>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
                    如果模型中途断开，这里也会保留最后一个成功工具结果，避免整轮任务白做。
                  </div>
                )}
              </div>
            </div>
          </ScrollArea>
        </Card>
      </div>
    </div>
  )
}
