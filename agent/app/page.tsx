"use client"

import { useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Briefcase, FileText, Target, MessageSquare, Sparkles } from "lucide-react"

export default function AuthPage() {
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    // 模拟登录
    setTimeout(() => {
      window.location.href = "/dashboard"
    }, 1000)
  }

  return (
    <div className="min-h-screen flex">
      {/* 左侧品牌区域 */}
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
            让 AI 帮你搞定<br />
            求职的每一步
          </h1>
          
          <div className="space-y-6">
            <FeatureItem 
              icon={<Target className="size-5" />}
              title="智能职位匹配"
              description="自动搜索 LinkedIn、Indeed 等平台，精准匹配合适职位"
            />
            <FeatureItem 
              icon={<FileText className="size-5" />}
              title="简历/Cover Letter 定制"
              description="根据 JD 自动优化简历，每份都独一无二"
            />
            <FeatureItem 
              icon={<Sparkles className="size-5" />}
              title="申请状态追踪"
              description="看板式管理所有申请，不错过任何跟进机会"
            />
            <FeatureItem 
              icon={<MessageSquare className="size-5" />}
              title="面试智能准备"
              description="爬取面试真题，生成 STAR 答案框架"
            />
          </div>
        </div>

        <p className="text-background/40 text-sm">
          已帮助 10,000+ 求职者获得心仪 Offer
        </p>
      </div>

      {/* 右侧登录区域 */}
      <div className="flex-1 flex items-center justify-center p-8 bg-muted/30">
        <div className="w-full max-w-md">
          {/* 移动端 Logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="size-10 rounded-xl bg-foreground flex items-center justify-center">
              <Briefcase className="size-5 text-background" />
            </div>
            <span className="text-xl font-semibold">Job Hunt Agent</span>
          </div>

          <Card className="border-0 shadow-lg">
            <CardHeader className="text-center pb-4">
              <CardTitle className="text-2xl">欢迎使用</CardTitle>
              <CardDescription>登录或创建账号开始你的求职之旅</CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="login" className="w-full">
                <TabsList className="grid w-full grid-cols-2 mb-6">
                  <TabsTrigger value="login">登录</TabsTrigger>
                  <TabsTrigger value="register">注册</TabsTrigger>
                </TabsList>
                
                <TabsContent value="login">
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="email">邮箱</Label>
                      <Input 
                        id="email" 
                        type="email" 
                        placeholder="your@email.com"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="password">密码</Label>
                        <Link href="#" className="text-xs text-muted-foreground hover:text-foreground">
                          忘记密码？
                        </Link>
                      </div>
                      <Input 
                        id="password" 
                        type="password" 
                        placeholder="••••••••"
                        required
                      />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                      {isLoading ? "登录中..." : "登录"}
                    </Button>
                  </form>
                </TabsContent>
                
                <TabsContent value="register">
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">姓名</Label>
                      <Input 
                        id="name" 
                        type="text" 
                        placeholder="张三"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reg-email">邮箱</Label>
                      <Input 
                        id="reg-email" 
                        type="email" 
                        placeholder="your@email.com"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reg-password">密码</Label>
                      <Input 
                        id="reg-password" 
                        type="password" 
                        placeholder="••••••••"
                        required
                      />
                    </div>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                      {isLoading ? "创建中..." : "创建账号"}
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">或使用</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button variant="outline" type="button">
                  <svg className="size-4 mr-2" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  Google
                </Button>
                <Button variant="outline" type="button">
                  <svg className="size-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"/>
                  </svg>
                  LinkedIn
                </Button>
              </div>
            </CardContent>
            <CardFooter className="text-center text-xs text-muted-foreground flex-col gap-2">
              <p>
                继续即表示你同意我们的{" "}
                <Link href="#" className="underline hover:text-foreground">服务条款</Link>
                {" "}和{" "}
                <Link href="#" className="underline hover:text-foreground">隐私政策</Link>
              </p>
            </CardFooter>
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
        <p className="text-sm text-background/60">{description}</p>
      </div>
    </div>
  )
}
