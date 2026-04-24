"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { CheckCircle2, Clock, Eye, FileText, Loader2, Plus, Star, Trash2, Upload } from "lucide-react"
import {
  type StoredResume,
  getDefaultResumePath,
  loadStoredResumes,
  saveStoredResumes,
  setDefaultResumePath,
} from "@/lib/resume-store"

function formatFileSize(sizeBytes: number) {
  if (!sizeBytes) {
    return "未知大小"
  }
  if (sizeBytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(sizeBytes / 1024))} KB`
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ResumePage() {
  const [resumes, setResumes] = useState<StoredResume[]>([])
  const [selectedResumeId, setSelectedResumeId] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const stored = loadStoredResumes()
    setResumes(stored)

    const defaultPath = getDefaultResumePath()
    const defaultResume = stored.find((resume) => resume.path === defaultPath) ?? stored[0]
    if (defaultResume) {
      setSelectedResumeId(defaultResume.id)
    }
  }, [])

  const selectedResume = useMemo(
    () => resumes.find((resume) => resume.id === selectedResumeId) ?? resumes[0] ?? null,
    [resumes, selectedResumeId],
  )

  const persistResumes = (nextResumes: StoredResume[]) => {
    setResumes(nextResumes)
    saveStoredResumes(nextResumes)
  }

  const handleSetDefault = (id: string) => {
    const nextResumes = resumes.map((resume) => ({
      ...resume,
      isDefault: resume.id === id,
    }))
    const current = nextResumes.find((resume) => resume.id === id)
    if (current) {
      setDefaultResumePath(current.path)
      setSelectedResumeId(current.id)
    }
    persistResumes(nextResumes)
  }

  const handleDelete = (id: string) => {
    const nextResumes = resumes.filter((resume) => resume.id !== id)
    persistResumes(nextResumes)
    if (selectedResumeId === id) {
      setSelectedResumeId(nextResumes[0]?.id ?? "")
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("请选择一个 PDF 简历文件。")
      return
    }

    setUploading(true)
    setError("")

    try {
      const formData = new FormData()
      formData.append("file", selectedFile)

      const response = await fetch("http://localhost:8000/api/resume/upload", {
        method: "POST",
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || "上传失败")
      }

      const nextResume: StoredResume = {
        id: crypto.randomUUID(),
        filename: data.filename,
        path: data.path,
        uploadedAt: new Date().toISOString(),
        sizeBytes: data.size_bytes ?? selectedFile.size,
        previewText: data.preview_text ?? "",
        isDefault: resumes.length === 0,
      }

      const nextResumes = resumes.map((resume) => ({
        ...resume,
        isDefault: nextResume.isDefault ? false : resume.isDefault,
      }))
      nextResumes.unshift(nextResume)

      persistResumes(nextResumes)
      setSelectedResumeId(nextResume.id)
      setDefaultResumePath(nextResume.path)
      setSelectedFile(null)
      setUploadDialogOpen(false)
      if (inputRef.current) {
        inputRef.current.value = ""
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传失败")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">简历管理</h1>
          <p className="text-muted-foreground">上传真实简历文件，后续定制和自动投递会复用默认简历</p>
        </div>
        <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="size-4 mr-2" />
              上传简历
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>上传新简历</DialogTitle>
              <DialogDescription>当前仅支持 PDF，上传后会保存服务端路径并提取文本预览。</DialogDescription>
            </DialogHeader>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25"
              }`}
              onDragOver={(event) => {
                event.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault()
                setIsDragging(false)
                const file = event.dataTransfer.files?.[0]
                if (file) {
                  setSelectedFile(file)
                  setError("")
                }
              }}
            >
              <Upload className="size-10 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-2">拖拽 PDF 到这里，或点击选择文件</p>
              <Input
                ref={inputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                id="resume-upload"
                onChange={(event) => {
                  setSelectedFile(event.target.files?.[0] ?? null)
                  setError("")
                }}
              />
              <Label htmlFor="resume-upload" asChild>
                <Button variant="secondary" size="sm">
                  选择文件
                </Button>
              </Label>
              <p className="text-xs text-muted-foreground mt-4">
                {selectedFile ? `已选择：${selectedFile.name}` : "支持 PDF 格式，建议 10MB 内"}
              </p>
              {error ? <p className="text-xs text-destructive mt-2">{error}</p> : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setUploadDialogOpen(false)} disabled={uploading}>
                取消
              </Button>
              <Button onClick={handleUpload} disabled={uploading || !selectedFile}>
                {uploading ? <Loader2 className="size-4 mr-2 animate-spin" /> : null}
                上传
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs defaultValue="files">
        <TabsList>
          <TabsTrigger value="files">简历文件</TabsTrigger>
          <TabsTrigger value="parsed">解析预览</TabsTrigger>
        </TabsList>

        <TabsContent value="files" className="mt-6">
          {resumes.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                <FileText className="size-10 mx-auto mb-4 opacity-50" />
                <p>还没有真实简历数据。</p>
                <p className="text-sm mt-1">先上传一份 PDF，后面的定制页和投递页就会直接复用它。</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {resumes.map((resume) => (
                <Card key={resume.id} className={resume.isDefault ? "border-primary/50" : ""}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <div className="size-12 rounded-lg bg-red-100 flex items-center justify-center shrink-0">
                        <FileText className="size-6 text-red-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium truncate">{resume.filename}</p>
                          {resume.isDefault ? (
                            <Badge variant="secondary" className="shrink-0">
                              <Star className="size-3 mr-1 fill-current" />
                              默认
                            </Badge>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground mt-1">
                          <span>{formatFileSize(resume.sizeBytes)}</span>
                          <span className="flex items-center gap-1">
                            <Clock className="size-3" />
                            {new Date(resume.uploadedAt).toLocaleString()}
                          </span>
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle2 className="size-3" />
                            已上传
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2 break-all">{resume.path}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => setSelectedResumeId(resume.id)}>
                          <Eye className="size-4 mr-2" />
                          查看解析
                        </Button>
                        {!resume.isDefault ? (
                          <Button variant="outline" size="sm" onClick={() => handleSetDefault(resume.id)}>
                            <Star className="size-4 mr-2" />
                            设为默认
                          </Button>
                        ) : null}
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(resume.id)}>
                          <Trash2 className="size-4 mr-2" />
                          删除
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="parsed" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>当前解析预览</CardTitle>
              <CardDescription>显示后端从所选 PDF 中实际提取出的文本，不再展示伪造字段。</CardDescription>
            </CardHeader>
            <CardContent>
              {selectedResume ? (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="font-medium">{selectedResume.filename}</p>
                    <p className="text-sm text-muted-foreground break-all">{selectedResume.path}</p>
                  </div>
                  <ScrollArea className="h-[420px] rounded-lg border p-4">
                    <pre className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                      {selectedResume.previewText || "这份 PDF 暂时没有解析出可展示文本。"}
                    </pre>
                  </ScrollArea>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">还没有可解析的简历，请先上传一份 PDF。</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
