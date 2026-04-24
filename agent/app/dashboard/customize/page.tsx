"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { CheckCircle2, Copy, ExternalLink, FileText, Loader2, Sparkles, Wand2 } from "lucide-react"
import { type StoredResume, loadStoredResumes } from "@/lib/resume-store"

type CustomizeResult = {
  job_id: string
  customized_text: string
  cover_letter: string
  diff_html_path: string
  resume_file_path: string
  cover_letter_file_path: string
}

export default function CustomizePage() {
  const [resumes, setResumes] = useState<StoredResume[]>([])
  const [selectedResume, setSelectedResume] = useState("")
  const [jobDescription, setJobDescription] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [result, setResult] = useState<CustomizeResult | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    const stored = loadStoredResumes()
    setResumes(stored)
    setSelectedResume(stored.find((resume) => resume.isDefault)?.id ?? stored[0]?.id ?? "")
  }, [])

  const currentResume = useMemo(
    () => resumes.find((resume) => resume.id === selectedResume) ?? null,
    [resumes, selectedResume],
  )

  const handleGenerate = async () => {
    if (!currentResume) {
      setError("请先上传一份真实简历。")
      return
    }

    if (!jobDescription.trim()) {
      setError("请先粘贴职位描述。")
      return
    }

    setIsGenerating(true)
    setError("")

    try {
      const response = await fetch("http://localhost:8000/api/resume/customize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_path: currentResume.path,
          job_description: jobDescription.trim(),
          generate_cover_letter: true,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || "定制失败")
      }

      setResult(data)
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "定制失败")
      setResult(null)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">简历定制</h1>
        <p className="text-muted-foreground">根据真实 JD 调用后端生成定制简历、Cover Letter 和 diff 预览</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">选择基础简历</CardTitle>
              <CardDescription>这里显示的是你已上传的真实简历。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select value={selectedResume} onValueChange={setSelectedResume}>
                <SelectTrigger>
                  <SelectValue placeholder="选择简历" />
                </SelectTrigger>
                <SelectContent>
                  {resumes.map((resume) => (
                    <SelectItem key={resume.id} value={resume.id}>
                      {resume.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {currentResume ? (
                <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                  <p className="font-medium">{currentResume.filename}</p>
                  <p className="text-muted-foreground break-all mt-1">{currentResume.path}</p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">还没有可用简历，请先去“简历管理”上传 PDF。</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">职位描述 (JD)</CardTitle>
              <CardDescription>粘贴真实职位描述，系统会把它传给后端 LLM。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="粘贴职位描述..."
                className="min-h-[320px] resize-none"
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
              />
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">已输入 {jobDescription.length} 字符</div>
                <Button onClick={handleGenerate} disabled={isGenerating || !currentResume || !jobDescription.trim()}>
                  {isGenerating ? <Loader2 className="size-4 mr-2 animate-spin" /> : <Wand2 className="size-4 mr-2" />}
                  AI 智能生成
                </Button>
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">生成结果</CardTitle>
            <CardDescription>这一栏只展示后端真实返回的内容。</CardDescription>
          </CardHeader>
          <CardContent>
            {!result ? (
              <div className="h-[520px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <div className="text-center text-muted-foreground">
                  <Sparkles className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">还没有生成结果</p>
                  <p className="text-sm">选择真实简历并输入 JD 后再开始。</p>
                </div>
              </div>
            ) : (
              <Tabs defaultValue="resume">
                <TabsList className="w-full grid grid-cols-2">
                  <TabsTrigger value="resume">定制简历</TabsTrigger>
                  <TabsTrigger value="cover">Cover Letter</TabsTrigger>
                </TabsList>

                <TabsContent value="resume" className="mt-4 space-y-4">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="bg-green-100 text-green-700">
                      <CheckCircle2 className="size-3 mr-1" />
                      后端已生成
                    </Badge>
                    <Badge variant="outline" className="gap-1">
                      <FileText className="size-3" />
                      Markdown
                    </Badge>
                  </div>
                  <ScrollArea className="h-[400px] border rounded-lg p-4">
                    <pre className="whitespace-pre-wrap font-sans text-sm text-foreground">
                      {result.customized_text}
                    </pre>
                  </ScrollArea>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={() => handleCopy(result.customized_text)}>
                      <Copy className="size-4 mr-2" />
                      复制
                    </Button>
                    <Button variant="outline" asChild>
                      <a href={`http://localhost:8000/api/diff/${result.job_id}`} target="_blank" rel="noreferrer">
                        <ExternalLink className="size-4 mr-2" />
                        查看 diff
                      </a>
                    </Button>
                    <Badge variant="outline" className="max-w-full truncate">
                      {result.resume_file_path}
                    </Badge>
                  </div>
                </TabsContent>

                <TabsContent value="cover" className="mt-4 space-y-4">
                  <ScrollArea className="h-[400px] border rounded-lg p-4">
                    <pre className="whitespace-pre-wrap font-sans text-sm text-foreground">
                      {result.cover_letter || "这次没有生成 Cover Letter。"}
                    </pre>
                  </ScrollArea>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={() => handleCopy(result.cover_letter || "")}>
                      <Copy className="size-4 mr-2" />
                      复制
                    </Button>
                    <Badge variant="outline" className="max-w-full truncate">
                      {result.cover_letter_file_path || "未生成文件路径"}
                    </Badge>
                  </div>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
