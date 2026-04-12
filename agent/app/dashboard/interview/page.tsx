"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Progress } from "@/components/ui/progress"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Sparkles,
  Target,
  Lightbulb,
  CheckCircle2,
  Play,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Building2,
  Code,
  Users,
  Brain,
  ChevronRight,
  Loader2,
} from "lucide-react"

const technicalQuestions = [
  {
    id: "1",
    question: "请解释 React 的 Virtual DOM 工作原理，以及它如何提升性能？",
    category: "React",
    difficulty: "中等",
    status: "practiced",
    answer: `Virtual DOM 是 React 的核心概念之一，它是真实 DOM 的一个轻量级 JavaScript 对象表示。

**工作原理：**
1. **创建虚拟节点**：React 将 JSX 转换为虚拟 DOM 树
2. **Diff 算法**：当状态变化时，React 创建新的虚拟 DOM 树，并与旧树进行对比
3. **最小化更新**：React 只更新真正变化的部分到真实 DOM

**性能优势：**
- 减少直接 DOM 操作次数
- 批量更新，避免重复渲染
- 跨平台渲染能力（React Native）

**面试加分点：**
- 提到 Fiber 架构和时间切片
- 说明 key 在 Diff 算法中的作用`,
  },
  {
    id: "2",
    question: "什么是闭包？请举例说明闭包的实际应用场景",
    category: "JavaScript",
    difficulty: "基础",
    status: "not-started",
    answer: "",
  },
  {
    id: "3",
    question: "请描述 HTTP 缓存机制，强缓存和协商缓存的区别",
    category: "网络",
    difficulty: "中等",
    status: "practiced",
    answer: "",
  },
  {
    id: "4",
    question: "React Hooks 的工作原理是什么？为什么不能在条件语句中使用？",
    category: "React",
    difficulty: "进阶",
    status: "not-started",
    answer: "",
  },
  {
    id: "5",
    question: "请解释 webpack 的构建流程和核心概念",
    category: "工程化",
    difficulty: "中等",
    status: "practiced",
    answer: "",
  },
]

const behaviorQuestions = [
  {
    id: "b1",
    question: "请描述一次你解决复杂技术问题的经历",
    type: "STAR",
  },
  {
    id: "b2",
    question: "描述一次你与团队成员产生分歧并最终达成共识的经历",
    type: "STAR",
  },
  {
    id: "b3",
    question: "你如何处理紧急的项目截止日期？",
    type: "STAR",
  },
]

const companyQuestions = [
  {
    company: "字节跳动",
    questions: [
      "抖音的推荐算法是如何工作的？",
      "你如何看待短视频对社会的影响？",
      "为什么想加入字节？",
    ],
    source: "Glassdoor",
    updatedAt: "2024-01",
  },
  {
    company: "阿里巴巴",
    questions: [
      "双十一期间如何保证系统稳定性？",
      "谈谈你对中台战略的理解",
      "你最喜欢的阿里产品是什么？",
    ],
    source: "牛客网",
    updatedAt: "2024-01",
  },
]

const difficultyColors: Record<string, string> = {
  "基础": "bg-green-100 text-green-700",
  "中等": "bg-amber-100 text-amber-700",
  "进阶": "bg-red-100 text-red-700",
}

export default function InterviewPage() {
  const [practiceDialogOpen, setPracticeDialogOpen] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState(technicalQuestions[0])
  const [userAnswer, setUserAnswer] = useState("")
  const [showAnswer, setShowAnswer] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)

  const handleStartPractice = (question: typeof technicalQuestions[0]) => {
    setCurrentQuestion(question)
    setUserAnswer("")
    setShowAnswer(false)
    setPracticeDialogOpen(true)
  }

  const handleGenerateAnswer = () => {
    setIsGenerating(true)
    setTimeout(() => {
      setIsGenerating(false)
      setShowAnswer(true)
    }, 1500)
  }

  const practicedCount = technicalQuestions.filter(q => q.status === "practiced").length
  const totalCount = technicalQuestions.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">面试准备</h1>
          <p className="text-muted-foreground">AI 驱动的面试题库和 STAR 答案生成</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right mr-2">
            <p className="text-sm text-muted-foreground">练习进度</p>
            <p className="font-medium">{practicedCount}/{totalCount} 题</p>
          </div>
          <Progress value={(practicedCount / totalCount) * 100} className="w-32" />
        </div>
      </div>

      <Tabs defaultValue="technical">
        <TabsList>
          <TabsTrigger value="technical" className="gap-2">
            <Code className="size-4" />
            技术题
          </TabsTrigger>
          <TabsTrigger value="behavior" className="gap-2">
            <Users className="size-4" />
            行为题
          </TabsTrigger>
          <TabsTrigger value="company" className="gap-2">
            <Building2 className="size-4" />
            公司题库
          </TabsTrigger>
        </TabsList>

        <TabsContent value="technical" className="mt-6">
          <div className="grid lg:grid-cols-[1fr_350px] gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">技术面试题库</CardTitle>
                    <CardDescription>常见前端技术面试题，点击开始练习</CardDescription>
                  </div>
                  <Select defaultValue="all">
                    <SelectTrigger className="w-[140px]">
                      <SelectValue placeholder="筛选类别" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部类别</SelectItem>
                      <SelectItem value="react">React</SelectItem>
                      <SelectItem value="javascript">JavaScript</SelectItem>
                      <SelectItem value="network">网络</SelectItem>
                      <SelectItem value="engineering">工程化</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {technicalQuestions.map((q) => (
                    <div
                      key={q.id}
                      className="p-4 rounded-lg border hover:border-foreground/30 transition-colors cursor-pointer"
                      onClick={() => handleStartPractice(q)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <p className="font-medium mb-2">{q.question}</p>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{q.category}</Badge>
                            <Badge className={difficultyColors[q.difficulty]}>{q.difficulty}</Badge>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {q.status === "practiced" ? (
                            <Badge variant="secondary" className="bg-green-100 text-green-700">
                              <CheckCircle2 className="size-3 mr-1" />
                              已练习
                            </Badge>
                          ) : (
                            <Badge variant="secondary">未练习</Badge>
                          )}
                          <Button size="sm">
                            <Play className="size-4 mr-1" />
                            练习
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Lightbulb className="size-5" />
                  知识点速查
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="react">
                    <AccordionTrigger>React 核心概念</AccordionTrigger>
                    <AccordionContent>
                      <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>Virtual DOM 与 Diff 算法</li>
                        <li>Hooks 原理与使用规则</li>
                        <li>生命周期与渲染机制</li>
                        <li>状态管理方案对比</li>
                        <li>性能优化技巧</li>
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="js">
                    <AccordionTrigger>JavaScript 基础</AccordionTrigger>
                    <AccordionContent>
                      <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>闭包与作用域</li>
                        <li>原型链与继承</li>
                        <li>事件循环机制</li>
                        <li>Promise 与异步</li>
                        <li>ES6+ 新特性</li>
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="network">
                    <AccordionTrigger>网络与浏览器</AccordionTrigger>
                    <AccordionContent>
                      <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>HTTP/HTTPS 协议</li>
                        <li>缓存策略</li>
                        <li>跨域解决方案</li>
                        <li>浏览器渲染原理</li>
                        <li>安全相关 (XSS/CSRF)</li>
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="behavior" className="mt-6">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">行为面试题</CardTitle>
                <CardDescription>使用 STAR 法则准备你的回答</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {behaviorQuestions.map((q) => (
                  <div
                    key={q.id}
                    className="p-4 rounded-lg border hover:border-foreground/30 transition-colors"
                  >
                    <p className="font-medium mb-3">{q.question}</p>
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="gap-1">
                        <Target className="size-3" />
                        {q.type} 法则
                      </Badge>
                      <Button size="sm" variant="outline">
                        <Sparkles className="size-4 mr-1" />
                        生成答案
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="size-5" />
                  STAR 答案框架
                </CardTitle>
                <CardDescription>
                  结构化地组织你的行为面试回答
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <h4 className="font-medium text-blue-700 mb-2">S - Situation（��景）</h4>
                  <p className="text-sm text-blue-600">描述当时的背景、环境和挑战</p>
                </div>
                <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                  <h4 className="font-medium text-green-700 mb-2">T - Task（任务）</h4>
                  <p className="text-sm text-green-600">说明你的职责和需要达成的目标</p>
                </div>
                <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
                  <h4 className="font-medium text-amber-700 mb-2">A - Action（行动）</h4>
                  <p className="text-sm text-amber-600">详细描述你采取的具体行动和方法</p>
                </div>
                <div className="p-4 rounded-lg bg-purple-50 border border-purple-200">
                  <h4 className="font-medium text-purple-700 mb-2">R - Result（结果）</h4>
                  <p className="text-sm text-purple-600">量化你的成果和影响</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="company" className="mt-6">
          <div className="grid lg:grid-cols-2 gap-6">
            {companyQuestions.map((company, i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-12 rounded-xl bg-muted flex items-center justify-center font-bold">
                        {company.company[0]}
                      </div>
                      <div>
                        <CardTitle className="text-base">{company.company}</CardTitle>
                        <CardDescription>
                          来源：{company.source} | 更新：{company.updatedAt}
                        </CardDescription>
                      </div>
                    </div>
                    <Badge variant="outline">{company.questions.length} 题</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {company.questions.map((q, j) => (
                      <div
                        key={j}
                        className="p-3 rounded-lg bg-muted/50 flex items-center justify-between group hover:bg-muted transition-colors"
                      >
                        <p className="text-sm flex-1">{q}</p>
                        <Button 
                          size="sm" 
                          variant="ghost" 
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Sparkles className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  <Button variant="outline" className="w-full mt-4">
                    查看更多
                    <ChevronRight className="size-4 ml-1" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={practiceDialogOpen} onOpenChange={setPracticeDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline">{currentQuestion.category}</Badge>
              <Badge className={difficultyColors[currentQuestion.difficulty]}>
                {currentQuestion.difficulty}
              </Badge>
            </div>
            <DialogTitle className="text-lg leading-relaxed">
              {currentQuestion.question}
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium mb-2 block">你的回答：</label>
              <Textarea
                placeholder="在这里写下你的答案..."
                className="min-h-[150px]"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
              />
            </div>

            {!showAnswer ? (
              <Button 
                className="w-full" 
                onClick={handleGenerateAnswer}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    生成参考答案...
                  </>
                ) : (
                  <>
                    <Sparkles className="size-4 mr-2" />
                    查看参考答案
                  </>
                )}
              </Button>
            ) : (
              <div className="space-y-4">
                <div className="p-4 rounded-lg border bg-muted/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Brain className="size-5 text-primary" />
                    <span className="font-medium">AI 参考答案</span>
                  </div>
                  <ScrollArea className="h-[200px]">
                    <pre className="whitespace-pre-wrap font-sans text-sm">
                      {currentQuestion.answer || "暂无参考答案"}
                    </pre>
                  </ScrollArea>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">这个答案对你有帮助吗？</span>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <ThumbsUp className="size-4 mr-1" />
                      有帮助
                    </Button>
                    <Button variant="outline" size="sm">
                      <ThumbsDown className="size-4 mr-1" />
                      需改进
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPracticeDialogOpen(false)}>
              关闭
            </Button>
            <Button onClick={() => {
              setUserAnswer("")
              setShowAnswer(false)
            }}>
              <RefreshCw className="size-4 mr-2" />
              重新练习
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
