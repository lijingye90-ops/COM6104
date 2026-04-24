"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Brain, Building2, Copy, Loader2, Sparkles, Target, Users } from "lucide-react"

type StarAnswer = {
  question: string
  star: {
    S: string
    T: string
    A: string
    R: string
  }
}

type InterviewResult = {
  company: string
  role: string
  questions: string[]
  star_answers: StarAnswer[]
}

export default function InterviewPage() {
  const [company, setCompany] = useState("")
  const [jobTitle, setJobTitle] = useState("")
  const [jobDescription, setJobDescription] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<InterviewResult | null>(null)

  const handleGenerate = async () => {
    if (!company.trim() || !jobTitle.trim() || !jobDescription.trim()) {
      setError("请先填写公司、岗位和职位描述。")
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await fetch("http://localhost:8000/api/interview/prep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: company.trim(),
          job_title: jobTitle.trim(),
          job_description: jobDescription.trim(),
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || "生成失败")
      }

      setResult(data)
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "生成失败")
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">面试准备</h1>
          <p className="text-muted-foreground">根据真实岗位信息生成面试题和 STAR 参考答案</p>
        </div>
        {result ? (
          <Badge variant="outline" className="gap-1.5">
            <Brain className="size-3.5" />
            {result.questions.length} 题
          </Badge>
        ) : null}
      </div>

      <div className="grid lg:grid-cols-[380px_1fr] gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">岗位输入</CardTitle>
            <CardDescription>不再展示默认题库，所有内容都来自你当前填写的岗位信息。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">公司</label>
              <Input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例如：OpenAI" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">岗位</label>
              <Input value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder="例如：Frontend Engineer" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">职位描述</label>
              <Textarea
                className="min-h-[260px] resize-none"
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
                placeholder="粘贴真实 JD..."
              />
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button className="w-full" onClick={handleGenerate} disabled={loading}>
              {loading ? <Loader2 className="size-4 mr-2 animate-spin" /> : <Sparkles className="size-4 mr-2" />}
              生成面试准备
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">生成结果</CardTitle>
            <CardDescription>这里展示的是后端 `interview_prep` 工具的真实输出。</CardDescription>
          </CardHeader>
          <CardContent>
            {!result ? (
              <div className="h-[560px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <div className="text-center text-muted-foreground">
                  <Target className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">还没有面试题结果</p>
                  <p className="text-sm">填写岗位信息后点击生成。</p>
                </div>
              </div>
            ) : (
              <Tabs defaultValue="questions">
                <TabsList>
                  <TabsTrigger value="questions" className="gap-2">
                    <Users className="size-4" />
                    面试题
                  </TabsTrigger>
                  <TabsTrigger value="answers" className="gap-2">
                    <Building2 className="size-4" />
                    STAR 答案
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="questions" className="mt-4">
                  <ScrollArea className="h-[470px] pr-4">
                    <div className="space-y-3">
                      {result.questions.map((question, index) => (
                        <div key={`${question}-${index}`} className="rounded-lg border p-4">
                          <div className="flex items-start justify-between gap-4">
                            <p className="font-medium leading-6">{question}</p>
                            <Badge variant="outline">Q{index + 1}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="answers" className="mt-4">
                  <ScrollArea className="h-[470px] pr-4">
                    <div className="space-y-4">
                      {result.star_answers.map((item, index) => (
                        <Card key={`${item.question}-${index}`} className="shadow-none">
                          <CardHeader className="pb-3">
                            <CardTitle className="text-sm leading-6">{item.question}</CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-3">
                            {(["S", "T", "A", "R"] as const).map((sectionKey) => (
                              <div key={sectionKey} className="rounded-lg bg-muted/40 p-3">
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="text-sm font-medium">{sectionKey}</span>
                                  <Button variant="ghost" size="sm" onClick={() => handleCopy(item.star[sectionKey])}>
                                    <Copy className="size-4 mr-2" />
                                    复制
                                  </Button>
                                </div>
                                <p className="text-sm text-muted-foreground leading-6">{item.star[sectionKey]}</p>
                              </div>
                            ))}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
