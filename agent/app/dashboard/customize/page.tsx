"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sparkles,
  FileText,
  Copy,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  Wand2,
  FileDown,
  Eye,
} from "lucide-react"

// 模拟简历列表
const resumes = [
  { id: "1", name: "张小明_前端工程师简历_v3.pdf" },
  { id: "2", name: "张小明_全栈开发简历.pdf" },
]

// 模拟生成的内容
const generatedResume = `# 张小明
高级前端工程师 | 北京

## 个人简介
5年前端开发经验，**精通 React 生态系统**，有大型电商平台架构经验。在字节跳动技术团队的职位中，我的经验可以直接应用于：
- 抖音电商前端架构设计（与我在某大厂的架构经验高度匹配）
- 核心功能开发和性能优化（我有丰富的性能调优经验）
- 前端工程化建设（主导过多个工程化项目）

## 相关工作经历

### 某大厂 | 高级前端工程师 | 2022.03 - 至今
**与目标职位相关度：95%**

- **架构设计**：主导设计了基于微前端的电商平台架构，支撑日活用户 500万+
- **性能优化**：优化首屏加载时间从 3.5s 降至 1.2s，提升 65%
- **团队协作**：带领 5 人前端团队，建立代码规范和 Review 机制
- **技术创新**：引入 TypeScript 重构核心模块，减少线上 Bug 40%

### 某互联网公司 | 前端工程师 | 2020.06 - 2022.02
**与目标职位相关度：80%**

- 负责订单系统前端开发，处理复杂业务逻辑
- 参与移动端 H5 性能优化项目

## 技能匹配分析

| 职位要求 | 我的技能 | 匹配度 |
|---------|---------|-------|
| React 精通 | 4年 React 开发经验 | ✅ 完全匹配 |
| TypeScript | 2年 TS 项目经验 | ✅ 完全匹配 |
| Node.js | 有服务端开发经验 | ✅ 完全匹配 |
| 架构能力 | 主导过多个大型项目架构 | ✅ 完全匹配 |

## 教育背景
某985大学 | 计算机科学与技术 本科 | 2016 - 2020`

const generatedCoverLetter = `尊敬的招聘团队：

您好！我是张小明，一名拥有 5 年前端开发经验的工程师。在浏览贵司招聘信息后，我对**高级前端工程师**这一职位非常感兴趣，现诚挚地向您推荐自己。

**为什么我适合这个职位？**

在过去的工作中，我积累了丰富的大型项目开发经验：

1. **架构设计能力**：在某大厂期间，我主导设计了基于微前端的电商平台架构，该平台日活用户超过 500 万。这与贵司抖音电商的业务场景高度契合。

2. **技术深度**：我精通 React 技术栈，有 4 年以上的 React 开发经验，熟练使用 TypeScript、Webpack 等现代前端工具链。

3. **性能优化经验**：我曾将项目首屏加载时间从 3.5s 优化至 1.2s，提升了 65% 的性能指标，这对于用户体验至关重要。

4. **团队协作**：我有带领 5 人前端团队的经验，建立了完善的代码规范和 Review 机制，能够很好地融入贵司的技术团队。

我相信，凭借我的技术能力和项目经验，能够为贵司的前端团队带来价值。期待有机会与您进一步沟通。

此致
敬礼！

张小明
138-xxxx-xxxx
xiaoming@example.com`

export default function CustomizePage() {
  const [selectedResume, setSelectedResume] = useState(resumes[0].id)
  const [jobDescription, setJobDescription] = useState(`职位：高级前端工程师
公司：字节跳动
地点：北京

职责：
- 负责抖音电商前端架构设计和核心功能开发
- 参与前端工程化建设，提升研发效率
- 优化前端性能，提升用户体验

要求：
- 本科及以上学历，3年以上前端开发经验
- 精通 React/Vue 等主流框架
- 熟悉 TypeScript、Node.js
- 有大型项目架构经验优先`)
  const [isGenerating, setIsGenerating] = useState(false)
  const [hasGenerated, setHasGenerated] = useState(false)
  const [generationProgress, setGenerationProgress] = useState(0)

  const handleGenerate = () => {
    setIsGenerating(true)
    setGenerationProgress(0)
    
    // 模拟生成进度
    const interval = setInterval(() => {
      setGenerationProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsGenerating(false)
          setHasGenerated(true)
          return 100
        }
        return prev + 10
      })
    }, 200)
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">简历定制</h1>
        <p className="text-muted-foreground">根据职位 JD 自动优化简历和生成 Cover Letter</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* 左侧输入区 */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">选择基础简历</CardTitle>
              <CardDescription>选择用于定制的原始简历</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedResume} onValueChange={setSelectedResume}>
                <SelectTrigger>
                  <SelectValue placeholder="选择简历" />
                </SelectTrigger>
                <SelectContent>
                  {resumes.map(resume => (
                    <SelectItem key={resume.id} value={resume.id}>
                      <div className="flex items-center gap-2">
                        <FileText className="size-4" />
                        {resume.name}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">职位描述 (JD)</CardTitle>
              <CardDescription>粘贴目标职位的完整描述，AI 将据此优化简历</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="粘贴职位描述..."
                className="min-h-[300px] resize-none"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  已输入 {jobDescription.length} 字符
                </div>
                <Button 
                  onClick={handleGenerate} 
                  disabled={isGenerating || !jobDescription.trim()}
                  size="lg"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="size-4 mr-2 animate-spin" />
                      生成中...
                    </>
                  ) : (
                    <>
                      <Wand2 className="size-4 mr-2" />
                      AI 智能生成
                    </>
                  )}
                </Button>
              </div>
              
              {isGenerating && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">正在分析职位需求...</span>
                    <span>{generationProgress}%</span>
                  </div>
                  <Progress value={generationProgress} />
                </div>
              )}
            </CardContent>
          </Card>

          {/* 匹配分析 */}
          {hasGenerated && (
            <Card className="border-green-200 bg-green-50/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2 text-green-700">
                  <CheckCircle2 className="size-5" />
                  匹配度分析
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm">整体匹配度</span>
                  <div className="flex items-center gap-2">
                    <Progress value={92} className="w-24 h-2" />
                    <span className="font-medium text-green-700">92%</span>
                  </div>
                </div>
                <Separator />
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-green-600" />
                    <span>React 技术栈 - 完全匹配</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-green-600" />
                    <span>架构经验 - 完全匹配</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-green-600" />
                    <span>工作年限 - 完全匹配</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="size-4 text-amber-500" />
                    <span>电商经验 - 部分匹配</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* 右侧输出区 */}
        <Card className="h-fit">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">生成结果</CardTitle>
                <CardDescription>AI 根据 JD 定制的内容</CardDescription>
              </div>
              {hasGenerated && (
                <Button variant="outline" size="sm" onClick={handleGenerate}>
                  <RefreshCw className="size-4 mr-2" />
                  重新生成
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!hasGenerated ? (
              <div className="h-[500px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <div className="text-center text-muted-foreground">
                  <Sparkles className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">输入 JD 后点击生成</p>
                  <p className="text-sm">AI 将自动优化你的简历</p>
                </div>
              </div>
            ) : (
              <Tabs defaultValue="resume">
                <TabsList className="w-full grid grid-cols-2">
                  <TabsTrigger value="resume">定制简历</TabsTrigger>
                  <TabsTrigger value="cover">Cover Letter</TabsTrigger>
                </TabsList>
                
                <TabsContent value="resume" className="mt-4">
                  <div className="flex items-center gap-2 mb-4">
                    <Badge variant="secondary" className="bg-green-100 text-green-700">
                      <CheckCircle2 className="size-3 mr-1" />
                      针对性优化
                    </Badge>
                    <Badge variant="secondary">
                      匹配度 92%
                    </Badge>
                  </div>
                  <ScrollArea className="h-[400px] border rounded-lg p-4">
                    <div className="prose prose-sm max-w-none">
                      <pre className="whitespace-pre-wrap font-sans text-sm text-foreground bg-transparent p-0">
                        {generatedResume}
                      </pre>
                    </div>
                  </ScrollArea>
                  <div className="flex items-center gap-2 mt-4">
                    <Button variant="outline" onClick={() => handleCopy(generatedResume)}>
                      <Copy className="size-4 mr-2" />
                      复制
                    </Button>
                    <Button variant="outline">
                      <Eye className="size-4 mr-2" />
                      预览 PDF
                    </Button>
                    <Button>
                      <FileDown className="size-4 mr-2" />
                      导出 PDF
                    </Button>
                  </div>
                </TabsContent>
                
                <TabsContent value="cover" className="mt-4">
                  <div className="flex items-center gap-2 mb-4">
                    <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                      <FileText className="size-3 mr-1" />
                      专属定制
                    </Badge>
                  </div>
                  <ScrollArea className="h-[400px] border rounded-lg p-4">
                    <div className="prose prose-sm max-w-none">
                      <pre className="whitespace-pre-wrap font-sans text-sm text-foreground bg-transparent p-0">
                        {generatedCoverLetter}
                      </pre>
                    </div>
                  </ScrollArea>
                  <div className="flex items-center gap-2 mt-4">
                    <Button variant="outline" onClick={() => handleCopy(generatedCoverLetter)}>
                      <Copy className="size-4 mr-2" />
                      复制
                    </Button>
                    <Button variant="outline">
                      <Eye className="size-4 mr-2" />
                      预览
                    </Button>
                    <Button>
                      <FileDown className="size-4 mr-2" />
                      导出 Word
                    </Button>
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
