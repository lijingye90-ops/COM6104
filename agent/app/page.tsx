"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Briefcase, FileText, MessageSquare, Sparkles, Target } from "lucide-react"

export default function HomePage() {
  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-foreground text-background p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="size-10 rounded-xl bg-background flex items-center justify-center">
              <Briefcase className="size-5 text-foreground" />
            </div>
            <span className="text-xl font-semibold">Job Hunt Agent</span>
          </div>
          <p className="text-background/60 text-sm">AI 驱动的求职全流程自动化平台</p>
        </div>

        <div className="space-y-8">
          <h1 className="text-4xl font-bold leading-tight text-balance">
            让 AI 帮你搞定
            <br />
            求职的每一步
          </h1>

          <div className="space-y-6">
            <FeatureItem
              icon={<Target className="size-5" />}
              title="智能职位匹配"
              description="搜索真实职位并做相关度筛选。"
            />
            <FeatureItem
              icon={<FileText className="size-5" />}
              title="简历与求职信定制"
              description="根据真实 JD 生成定制版内容和 diff。"
            />
            <FeatureItem
              icon={<Sparkles className="size-5" />}
              title="申请状态追踪"
              description="用同一个看板查看保存、投递和后续进展。"
            />
            <FeatureItem
              icon={<MessageSquare className="size-5" />}
              title="面试准备"
              description="基于岗位信息生成面试题和 STAR 参考答案。"
            />
          </div>
        </div>

        <p className="text-background/40 text-sm">本地运行版，适合演示和课堂答辩。</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-muted/30">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="size-10 rounded-xl bg-foreground flex items-center justify-center">
              <Briefcase className="size-5 text-background" />
            </div>
            <span className="text-xl font-semibold">Job Hunt Agent</span>
          </div>

          <Card className="border-0 shadow-lg">
            <CardHeader className="text-center pb-4">
              <CardTitle className="text-2xl">欢迎使用</CardTitle>
              <CardDescription>当前版本不提供账号系统，直接进入工作台即可开始真实流程。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border bg-muted/40 p-4 text-sm text-muted-foreground">
                <p>建议先完成这三步：</p>
                <p className="mt-2">1. 上传 PDF 简历</p>
                <p>2. 搜索真实职位</p>
                <p>3. 定制简历并继续投递</p>
              </div>
              <Button className="w-full" asChild>
                <Link href="/dashboard">进入工作台</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function FeatureItem({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex gap-4">
      <div className="size-10 rounded-lg bg-background/10 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div>
        <h3 className="font-medium mb-1">{title}</h3>
        <p className="text-sm text-background/70 leading-6">{description}</p>
      </div>
    </div>
  )
}
