"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import {
  MoreVertical,
  Calendar,
  Trash2,
  Edit2,
  ArrowRight,
  MessageSquare,
  Search,
  ExternalLink,
  FileText,
  FileDiff,
} from "lucide-react"

// --- Types matching API response ---

type ApplicationStatus = "saved" | "applied" | "fallback"

interface Application {
  job_id: string
  title: string
  company: string
  url: string
  status: ApplicationStatus
  applied_at: string | null
  resume_file_path: string | null
  cover_letter_path: string | null
  notes: string | null
  created_at: string
}

const statusConfig: Record<ApplicationStatus, { label: string; color: string; bgColor: string }> = {
  saved: { label: "已保存", color: "text-slate-600", bgColor: "bg-slate-100" },
  applied: { label: "已投递", color: "text-blue-600", bgColor: "bg-blue-100" },
  fallback: { label: "备选", color: "text-amber-600", bgColor: "bg-amber-100" },
}

const columns: ApplicationStatus[] = ["saved", "applied", "fallback"]

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedApp, setSelectedApp] = useState<Application | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)

  useEffect(() => {
    fetch("http://localhost:8000/api/applications")
      .then(res => res.json())
      .then(data => {
        setApplications(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const filteredApplications = applications.filter(app =>
    app.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
    app.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const getColumnApplications = (status: ApplicationStatus) =>
    filteredApplications.filter(app => app.status === status)

  const deleteApplication = (jobId: string) => {
    setApplications(apps => apps.filter(app => app.job_id !== jobId))
  }

  const moveApplication = (jobId: string, newStatus: ApplicationStatus) => {
    setApplications(apps =>
      apps.map(app => (app.job_id === jobId ? { ...app, status: newStatus } : app))
    )
  }

  const openDetail = (app: Application) => {
    setSelectedApp(app)
    setDetailDialogOpen(true)
  }

  const openDiff = (jobId: string) => {
    window.open(`http://localhost:8000/api/diff/${jobId}`, '_blank')
  }

  // Generate a logo character from company name
  const getLogo = (company: string) => company.charAt(0)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-140px)]">
        <div className="flex flex-col items-center gap-3">
          <Spinner className="size-8" />
          <p className="text-sm text-muted-foreground">加载申请数据...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 h-[calc(100vh-140px)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">申请追踪</h1>
          <p className="text-muted-foreground">看板式管理你的所有职位申请</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="搜索公司或职位..."
              className="pl-10 w-[240px]"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {applications.length === 0 && !loading ? (
        <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
          <FileText className="size-16 mb-4 opacity-40" />
          <p className="text-lg font-medium">暂无申请记录</p>
          <p className="text-sm mt-1">使用 AI 助手开始搜索和投递职位</p>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4 h-[calc(100%-80px)]">
          {columns.map(status => (
            <div key={status} className="flex-shrink-0 w-[340px]">
              <Card className="h-full flex flex-col">
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={`size-3 rounded-full ${statusConfig[status].bgColor}`} />
                      <CardTitle className="text-sm font-medium">
                        {statusConfig[status].label}
                      </CardTitle>
                    </div>
                    <Badge variant="secondary" className="text-xs">
                      {getColumnApplications(status).length}
                    </Badge>
                  </div>
                </CardHeader>
                <ScrollArea className="flex-1">
                  <div className="p-2 space-y-2">
                    {getColumnApplications(status).map(app => (
                      <Card
                        key={app.job_id}
                        className="cursor-pointer hover:border-foreground/30 transition-colors"
                        onClick={() => openDetail(app)}
                      >
                        <CardContent className="p-3">
                          <div className="flex items-start gap-3">
                            <div className="size-10 rounded-lg bg-muted flex items-center justify-center text-sm font-medium shrink-0">
                              {getLogo(app.company)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm truncate">{app.title}</p>
                              <p className="text-xs text-muted-foreground">{app.company}</p>
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                <Button variant="ghost" size="icon" className="size-7 shrink-0">
                                  <MoreVertical className="size-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); openDetail(app) }}>
                                  <Edit2 className="size-4 mr-2" />
                                  查看详情
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); openDiff(app.job_id) }}>
                                  <FileDiff className="size-4 mr-2" />
                                  查看 Diff
                                </DropdownMenuItem>
                                {app.url && (
                                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); window.open(app.url, '_blank') }}>
                                    <ExternalLink className="size-4 mr-2" />
                                    查看原始职位
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuSeparator />
                                {columns.filter(s => s !== status).map(targetStatus => (
                                  <DropdownMenuItem
                                    key={targetStatus}
                                    onClick={(e) => { e.stopPropagation(); moveApplication(app.job_id, targetStatus) }}
                                  >
                                    <ArrowRight className="size-4 mr-2" />
                                    移至{statusConfig[targetStatus].label}
                                  </DropdownMenuItem>
                                ))}
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-destructive"
                                  onClick={(e) => { e.stopPropagation(); deleteApplication(app.job_id) }}
                                >
                                  <Trash2 className="size-4 mr-2" />
                                  删除
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>

                          {/* Meta info */}
                          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                            {app.applied_at && (
                              <span className="flex items-center gap-1">
                                <Calendar className="size-3" />
                                {new Date(app.applied_at).toLocaleDateString("zh-CN")}
                              </span>
                            )}
                          </div>

                          {/* Diff button */}
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full mt-2 h-7 text-xs gap-1.5"
                            onClick={(e) => { e.stopPropagation(); openDiff(app.job_id) }}
                          >
                            <FileDiff className="size-3" />
                            查看 Diff
                          </Button>

                          {app.notes && (
                            <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
                              {app.notes}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                    {getColumnApplications(status).length === 0 && (
                      <div className="py-8 text-center text-muted-foreground text-sm">
                        暂无申请
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </Card>
            </div>
          ))}
        </div>
      )}

      {/* Detail dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-lg">
          {selectedApp && (
            <>
              <DialogHeader>
                <div className="flex items-start gap-4">
                  <div className="size-14 rounded-xl bg-muted flex items-center justify-center text-xl font-medium">
                    {getLogo(selectedApp.company)}
                  </div>
                  <div>
                    <DialogTitle className="text-xl">{selectedApp.title}</DialogTitle>
                    <DialogDescription className="text-base mt-1">
                      {selectedApp.company}
                    </DialogDescription>
                  </div>
                </div>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">状态</span>
                  <Badge className={`${statusConfig[selectedApp.status].bgColor} ${statusConfig[selectedApp.status].color}`}>
                    {statusConfig[selectedApp.status].label}
                  </Badge>
                </div>
                {selectedApp.applied_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">投递时间</span>
                    <span className="flex items-center gap-1">
                      <Calendar className="size-4" />
                      {new Date(selectedApp.applied_at).toLocaleDateString("zh-CN")}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">创建时间</span>
                  <span className="flex items-center gap-1">
                    <Calendar className="size-4" />
                    {new Date(selectedApp.created_at).toLocaleDateString("zh-CN")}
                  </span>
                </div>
                {selectedApp.url && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">职位链接</span>
                    <a
                      href={selectedApp.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary underline underline-offset-4 flex items-center gap-1"
                    >
                      查看原始职位
                      <ExternalLink className="size-3" />
                    </a>
                  </div>
                )}
                {selectedApp.resume_file_path && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">定制简历</span>
                    <span className="text-sm font-mono truncate max-w-[200px]">{selectedApp.resume_file_path.split('/').pop()}</span>
                  </div>
                )}
                {selectedApp.cover_letter_path && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">求职信</span>
                    <span className="text-sm font-mono truncate max-w-[200px]">{selectedApp.cover_letter_path.split('/').pop()}</span>
                  </div>
                )}
                <div>
                  <Label className="text-muted-foreground">备注</Label>
                  <p className="mt-1">{selectedApp.notes || "暂无备注"}</p>
                </div>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  variant="outline"
                  onClick={() => openDiff(selectedApp.job_id)}
                >
                  <FileDiff className="size-4 mr-2" />
                  查看 Diff
                </Button>
                <Button variant="outline" asChild>
                  <a href="/dashboard/interview">
                    <MessageSquare className="size-4 mr-2" />
                    准备面试
                  </a>
                </Button>
                <Button asChild>
                  <a href="/dashboard/customize">
                    定制简历
                    <ArrowRight className="size-4 ml-2" />
                  </a>
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
