"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Search,
  MapPin,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  Copy,
  Filter,
  Sparkles,
  DollarSign,
  Briefcase,
  GraduationCap,
  Loader2,
} from "lucide-react"

type ApiJob = {
  job_id: string
  title: string
  company: string
  url: string
  description: string
  location: string
  source: string
  posted_at: string
  match_score: number
  match_reason: string
}

type Job = {
  id: string
  title: string
  company: string
  location: string
  salary: string
  experience: string
  education: string
  tags: string[]
  description: string
  postedAt: string
  source: string
  matchScore: number
  matchReason: string
  saved: boolean
  url: string
}

type EmailAssist = {
  apply_email: string
  subject: string
  body: string
  resume_pdf: string
  cover_letter: string
  job_url: string
}

const sourceColors: Record<string, string> = {
  LinkedIn: "bg-blue-100 text-blue-700",
  Indeed: "bg-orange-100 text-orange-700",
  官网: "bg-green-100 text-green-700",
  "BOSS直聘": "bg-cyan-100 text-cyan-700",
  remoteok: "bg-orange-100 text-orange-700",
  hn: "bg-amber-100 text-amber-700",
  cached: "bg-slate-100 text-slate-700",
}

function formatPostedAt(value: string) {
  if (!value) return "未知"

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString("zh-CN")
}

function extractTags(job: ApiJob) {
  const text = `${job.title} ${job.description}`.toLowerCase()
  const candidates = [
    "python",
    "fastapi",
    "react",
    "typescript",
    "docker",
    "postgresql",
    "redis",
    "sql",
    "ai",
    "ml",
  ]

  const matched = candidates
    .filter((tag) => text.includes(tag))
    .slice(0, 3)
    .map((tag) => tag.toUpperCase())

  return matched.length > 0 ? matched : ["通用岗位"]
}

function repairMojibake(value: string) {
  if (!/[ÂÃâ]/.test(value)) {
    return value
  }

  try {
    const bytes = Uint8Array.from(
      Array.from(value).map((char) => char.charCodeAt(0) & 0xff)
    )
    return new TextDecoder("utf-8").decode(bytes)
  } catch {
    return value
  }
}

function decodeHtmlEntities(value: string) {
  let current = value

  for (let i = 0; i < 3; i += 1) {
    const textarea = document.createElement("textarea")
    textarea.innerHTML = current
    const decoded = textarea.value

    if (decoded === current) {
      break
    }

    current = decoded
  }

  return current
}

function normalizeDescription(raw: string) {
  if (!raw) {
    return "暂无职位描述"
  }

  const decoded = decodeHtmlEntities(raw)
  const repaired = repairMojibake(decoded).replaceAll("\u00a0", " ")

  const parser = new DOMParser()
  const doc = parser.parseFromString(repaired, "text/html")

  doc.querySelectorAll("br").forEach((node) => {
    node.replaceWith("\n")
  })

  doc.querySelectorAll("p, li, h1, h2, h3, h4, h5, h6").forEach((node) => {
    node.append("\n")
  })

  const text = doc.body.textContent ?? repaired

  return text
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .trim() || "暂无职位描述"
}

function toUiJob(job: ApiJob): Job {
  return {
    id: job.job_id,
    title: job.title,
    company: job.company,
    location: job.location || "Remote",
    salary: "面议",
    experience: "未注明",
    education: "未注明",
    tags: extractTags(job),
    description: normalizeDescription(job.description),
    postedAt: formatPostedAt(job.posted_at),
    source: job.source || "cached",
    matchScore: job.match_score || 0,
    matchReason: job.match_reason || "",
    saved: false,
    url: job.url || "",
  }
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [searchQuery, setSearchQuery] = useState("python")
  const [isSearching, setIsSearching] = useState(false)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [applyDialogOpen, setApplyDialogOpen] = useState(false)
  const [resumePathInput, setResumePathInput] = useState("")
  const [isApplying, setIsApplying] = useState(false)
  const [applyMessage, setApplyMessage] = useState<string | null>(null)
  const [emailAssist, setEmailAssist] = useState<EmailAssist | null>(null)
  const [isSendingEmail, setIsSendingEmail] = useState(false)
  const [sendEmailMessage, setSendEmailMessage] = useState<string | null>(null)
  const emailAssistRef = useRef<HTMLDivElement | null>(null)

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null

  const handleSearch = async () => {
    setIsSearching(true)
    setError(null)

    try {
      const response = await fetch(
        `http://localhost:8000/api/jobs/search?query=${encodeURIComponent(searchQuery)}`
      )

      if (!response.ok) {
        throw new Error(`搜索失败: ${response.status}`)
      }

      const data = await response.json()
      const nextJobs = (data.jobs ?? []).map(toUiJob)
      setJobs(nextJobs)
      setSelectedJobId(nextJobs[0]?.id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "职位搜索失败")
      setJobs([])
      setSelectedJobId(null)
    } finally {
      setIsSearching(false)
    }
  }

  useEffect(() => {
    void handleSearch()
  }, [])

  useEffect(() => {
    const savedResumePath = window.localStorage.getItem("job-hunt-resume-path")
    if (savedResumePath) {
      setResumePathInput(savedResumePath)
    }
  }, [])

  useEffect(() => {
    if (emailAssist && applyDialogOpen) {
      emailAssistRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }, [emailAssist, applyDialogOpen])

  const toggleSave = (id: string) => {
    setJobs((currentJobs) =>
      currentJobs.map((job) =>
        job.id === id ? { ...job, saved: !job.saved } : job
      )
    )
  }

  const handleApply = async () => {
    if (!selectedJob || !resumePathInput.trim()) {
      setApplyMessage("请先提供 PDF 简历路径。")
      return
    }

    setIsApplying(true)
    setApplyMessage(null)
    setEmailAssist(null)
    setSendEmailMessage(null)

    try {
      const response = await fetch("http://localhost:8000/api/jobs/apply", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          job_id: selectedJob.id,
          title: selectedJob.title,
          company: selectedJob.company,
          url: selectedJob.url,
          description: selectedJob.description,
          resume_path: resumePathInput.trim(),
        }),
      })

      if (!response.ok) {
        throw new Error(`申请失败: ${response.status}`)
      }

      const data = await response.json()
      const result = data.apply_result

      window.localStorage.setItem("job-hunt-resume-path", resumePathInput.trim())

      if (result.status === "applied") {
        setApplyMessage("自动投递已提交，申请追踪里也已经记录。")
      } else if (result.reason === "email_only_application") {
        setApplyMessage("这个职位是邮箱投递，不是网页表单。我已经帮你准备好邮件申请材料。")
        setEmailAssist(result.email_assist ?? null)
      } else if (result.reason === "login_wall") {
        setApplyMessage("这个职位的申请入口需要先注册或登录账号，当前没法直接自动提交。你可以先登录目标站点后再重试。")
      } else {
        setApplyMessage(`已记录为 fallback：${result.reason ?? "请手动继续处理"}`)
      }
    } catch (err) {
      setApplyMessage(err instanceof Error ? err.message : "申请失败")
    } finally {
      setIsApplying(false)
    }
  }

  const handleCopy = async (value: string) => {
    await navigator.clipboard.writeText(value)
  }

  const handleSendEmail = async () => {
    if (!emailAssist?.apply_email) {
      setSendEmailMessage("当前没有可发送的收件邮箱。")
      return
    }

    setIsSendingEmail(true)
    setSendEmailMessage(null)

    try {
      const response = await fetch("http://localhost:8000/api/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to_email: emailAssist.apply_email,
          subject: emailAssist.subject,
          body: emailAssist.body,
          resume_path: emailAssist.resume_pdf,
          cover_letter_path: emailAssist.cover_letter,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || "发送失败")
      }

      setSendEmailMessage(`邮件已通过 Resend 发出${data.message_id ? `（ID: ${data.message_id}）` : ""}。`)
    } catch (error) {
      setSendEmailMessage(error instanceof Error ? error.message : "发送失败")
    } finally {
      setIsSendingEmail(false)
    }
  }

  const mailtoHref = emailAssist
    ? `mailto:${encodeURIComponent(emailAssist.apply_email || "")}?subject=${encodeURIComponent(emailAssist.subject || "")}&body=${encodeURIComponent(emailAssist.body || "")}`
    : ""

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">职位搜索</h1>
        <p className="text-muted-foreground">AI 自动搜索多个平台，为你匹配最合适的职位</p>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                placeholder="搜索职位、公司或技能..."
                className="pl-10"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select defaultValue="all">
              <SelectTrigger className="w-[140px]">
                <MapPin className="size-4 mr-2" />
                <SelectValue placeholder="城市" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部城市</SelectItem>
                <SelectItem value="remote">远程</SelectItem>
                <SelectItem value="beijing">北京</SelectItem>
                <SelectItem value="shanghai">上海</SelectItem>
                <SelectItem value="hangzhou">杭州</SelectItem>
                <SelectItem value="shenzhen">深圳</SelectItem>
              </SelectContent>
            </Select>
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline">
                  <Filter className="size-4 mr-2" />
                  筛选
                </Button>
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>筛选条件</SheetTitle>
                  <SheetDescription>
                    当前版本只接通了基础搜索，筛选项还没有联动到后端。
                  </SheetDescription>
                </SheetHeader>
                <div className="space-y-6 py-6">
                  <div className="space-y-3">
                    <Label>薪资范围</Label>
                    <Select defaultValue="all">
                      <SelectTrigger>
                        <SelectValue placeholder="选择薪资范围" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">不限</SelectItem>
                        <SelectItem value="10-20">10-20K</SelectItem>
                        <SelectItem value="20-30">20-30K</SelectItem>
                        <SelectItem value="30-50">30-50K</SelectItem>
                        <SelectItem value="50+">50K以上</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-3">
                    <Label>工作经验</Label>
                    <Select defaultValue="all">
                      <SelectTrigger>
                        <SelectValue placeholder="选择经验要求" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">不限</SelectItem>
                        <SelectItem value="0-1">1年以下</SelectItem>
                        <SelectItem value="1-3">1-3年</SelectItem>
                        <SelectItem value="3-5">3-5年</SelectItem>
                        <SelectItem value="5+">5年以上</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-3">
                    <Label>职位来源</Label>
                    <div className="space-y-2">
                      {["LinkedIn", "Indeed", "BOSS直聘", "猎聘", "官网"].map((source) => (
                        <div key={source} className="flex items-center space-x-2">
                          <Checkbox id={source} defaultChecked />
                          <label htmlFor={source} className="text-sm">
                            {source}
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" className="flex-1">重置</Button>
                  <Button className="flex-1">应用筛选</Button>
                </div>
              </SheetContent>
            </Sheet>
            <Button onClick={() => void handleSearch()} disabled={isSearching}>
              {isSearching ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  搜索中...
                </>
              ) : (
                <>
                  <Sparkles className="size-4 mr-2" />
                  AI 智能搜索
                </>
              )}
            </Button>
          </div>
          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>

      <div className="grid lg:grid-cols-[400px_1fr] gap-6">
        <Card className="h-[calc(100vh-280px)]">
          <CardHeader className="py-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">找到 {jobs.length} 个职位</CardTitle>
              <Select defaultValue="match">
                <SelectTrigger className="w-[120px] h-8 text-sm">
                  <SelectValue placeholder="排序" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="match">匹配度</SelectItem>
                  <SelectItem value="date">发布时间</SelectItem>
                  <SelectItem value="salary">薪资</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <ScrollArea className="h-[calc(100%-70px)]">
            <div className="px-4 pb-4 space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                    selectedJob?.id === job.id
                      ? "border-foreground bg-muted/50"
                      : "hover:border-foreground/30"
                  }`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-medium">{job.title}</h3>
                      <p className="text-sm text-muted-foreground">{job.company}</p>
                    </div>
                    <div className="flex items-center gap-1 text-sm font-medium text-green-600">
                      <Sparkles className="size-3" />
                      {job.matchScore}%
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground mb-2">
                    <span className="flex items-center gap-1">
                      <MapPin className="size-3" />
                      {job.location}
                    </span>
                    <span className="flex items-center gap-1">
                      <DollarSign className="size-3" />
                      {job.salary}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex gap-1">
                      {job.tags.slice(0, 2).map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-xs text-muted-foreground">{job.postedAt}</span>
                  </div>
                </div>
              ))}
              {!isSearching && jobs.length === 0 ? (
                <p className="px-2 text-sm text-muted-foreground">没有找到匹配的职位。</p>
              ) : null}
            </div>
          </ScrollArea>
        </Card>

        {selectedJob ? (
          <Card className="h-[calc(100vh-280px)]">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h2 className="text-xl font-semibold">{selectedJob.title}</h2>
                      <Badge className={sourceColors[selectedJob.source] ?? "bg-slate-100 text-slate-700"}>
                        {selectedJob.source}
                      </Badge>
                    </div>
                    <p className="text-lg text-muted-foreground">{selectedJob.company}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => toggleSave(selectedJob.id)}
                    >
                      {selectedJob.saved ? (
                        <BookmarkCheck className="size-4 text-primary" />
                      ) : (
                        <Bookmark className="size-4" />
                      )}
                    </Button>
                    <Button
                      disabled={!selectedJob.url}
                      onClick={() => {
                        setApplyMessage(null)
                        setApplyDialogOpen(true)
                      }}
                    >
                      立即申请
                    </Button>
                  </div>
                </div>

                <Card className="bg-muted/30">
                  <CardHeader>
                    <CardTitle className="text-base">AI 匹配分析</CardTitle>
                    <CardDescription>当前岗位来自后端实时搜索结果。</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">匹配度</span>
                        <span className="text-2xl font-semibold text-green-600">
                          {selectedJob.matchScore}%
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {selectedJob.matchReason || "当前结果暂未返回匹配原因。"}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <DollarSign className="size-4" />
                      <span className="text-sm">薪资</span>
                    </div>
                    <p className="font-medium">{selectedJob.salary}</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <MapPin className="size-4" />
                      <span className="text-sm">地点</span>
                    </div>
                    <p className="font-medium">{selectedJob.location}</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <Briefcase className="size-4" />
                      <span className="text-sm">经验</span>
                    </div>
                    <p className="font-medium">{selectedJob.experience}</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2 text-muted-foreground mb-1">
                      <GraduationCap className="size-4" />
                      <span className="text-sm">学历</span>
                    </div>
                    <p className="font-medium">{selectedJob.education}</p>
                  </div>
                </div>

                <Separator />

                <div>
                  <h3 className="font-medium mb-3">技能关键词</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedJob.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium mb-3">职位描述</h3>
                  <div className="prose prose-sm max-w-none text-muted-foreground whitespace-pre-line">
                    {selectedJob.description}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium mb-3">公司信息</h3>
                  <div className="flex items-center gap-4 p-4 rounded-lg border">
                    <div className="size-14 rounded-lg bg-muted flex items-center justify-center text-xl font-bold">
                      {selectedJob.company[0]}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium">{selectedJob.company}</p>
                      <p className="text-sm text-muted-foreground">职位来源：{selectedJob.source}</p>
                    </div>
                    <Button variant="outline" size="sm" asChild disabled={!selectedJob.url}>
                      <a
                        href={selectedJob.url || "#"}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <ExternalLink className="size-4 mr-2" />
                        原始链接
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </Card>
        ) : (
          <Card className="h-[calc(100vh-280px)]">
            <CardContent className="h-full flex items-center justify-center text-sm text-muted-foreground">
              暂无职位数据，请先执行一次搜索。
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={applyDialogOpen} onOpenChange={setApplyDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>发起自动申请</DialogTitle>
            <DialogDescription>
              当前会优先尝试 LinkedIn Easy Apply。邮箱投递会在这个弹窗里直接展开邮件发送辅助区，不会跳到新页面。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>职位</Label>
              <div className="rounded-md border px-3 py-2 text-sm">
                {selectedJob?.title} · {selectedJob?.company}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="resume-path">PDF 简历路径</Label>
              <Input
                id="resume-path"
                placeholder="/tmp/resume.pdf"
                value={resumePathInput}
                onChange={(event) => setResumePathInput(event.target.value)}
              />
            </div>
            {selectedJob?.url ? (
              <p className="text-xs text-muted-foreground break-all">
                职位链接：{selectedJob.url}
              </p>
            ) : null}
            {applyMessage ? (
              <p className="text-sm text-muted-foreground">{applyMessage}</p>
            ) : null}
            {emailAssist ? (
              <div ref={emailAssistRef} className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-3">
                <div>
                  <p className="font-medium">邮件申请辅助</p>
                  <p className="text-sm text-muted-foreground">已识别为邮箱投递，你可以直接复制内容、打开邮件客户端，或通过 Resend 发送。</p>
                </div>
                {emailAssist.apply_email ? (
                  <div className="space-y-1">
                    <Label>收件邮箱</Label>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 rounded-md border px-3 py-2 text-sm break-all">
                        {emailAssist.apply_email}
                      </div>
                      <Button variant="outline" size="sm" onClick={() => void handleCopy(emailAssist.apply_email)}>
                        <Copy className="size-4 mr-2" />
                        复制
                      </Button>
                    </div>
                  </div>
                ) : null}
                <div className="space-y-1">
                  <Label>邮件主题</Label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 rounded-md border px-3 py-2 text-sm break-all">
                      {emailAssist.subject}
                    </div>
                    <Button variant="outline" size="sm" onClick={() => void handleCopy(emailAssist.subject)}>
                      <Copy className="size-4 mr-2" />
                      复制
                    </Button>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>邮件正文</Label>
                  <div className="rounded-md border px-3 py-2 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {emailAssist.body}
                  </div>
                  <Button variant="outline" size="sm" onClick={() => void handleCopy(emailAssist.body)}>
                    <Copy className="size-4 mr-2" />
                    复制正文
                  </Button>
                </div>
                <div className="space-y-1 text-xs text-muted-foreground">
                  <p>简历附件：{emailAssist.resume_pdf || "未生成"}</p>
                  {emailAssist.cover_letter ? <p>求职信附件：{emailAssist.cover_letter}</p> : null}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" asChild disabled={!mailtoHref}>
                    <a href={mailtoHref || "#"}>
                      <ExternalLink className="size-4 mr-2" />
                      打开邮件客户端
                    </a>
                  </Button>
                  <Button size="sm" onClick={() => void handleSendEmail()} disabled={isSendingEmail || !emailAssist.apply_email}>
                    {isSendingEmail ? <Loader2 className="size-4 mr-2 animate-spin" /> : null}
                    通过 Resend 发送
                  </Button>
                </div>
                {sendEmailMessage ? (
                  <p className="text-sm text-muted-foreground">{sendEmailMessage}</p>
                ) : null}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApplyDialogOpen(false)}>
              关闭
            </Button>
            <Button onClick={() => void handleApply()} disabled={isApplying || !selectedJob}>
              {isApplying ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  申请中...
                </>
              ) : (
                "开始自动申请"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
