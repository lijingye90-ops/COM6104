"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
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
  Building2,
  Clock,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  Filter,
  Sparkles,
  ChevronRight,
  DollarSign,
  Briefcase,
  GraduationCap,
  Loader2,
} from "lucide-react"

// 模拟职位数据
const mockJobs = [
  {
    id: "1",
    title: "高级前端工程师",
    company: "字节跳动",
    location: "北京",
    salary: "40-70K",
    experience: "3-5年",
    education: "本科",
    tags: ["React", "TypeScript", "Node.js"],
    description: "负责抖音电商前端架构设计和核心功能开发，参与前端工程化建设...",
    postedAt: "2天前",
    source: "LinkedIn",
    matchScore: 95,
    saved: true,
  },
  {
    id: "2",
    title: "全栈工程师",
    company: "阿里巴巴",
    location: "杭州",
    salary: "35-55K",
    experience: "3-5年",
    education: "本科",
    tags: ["Vue", "Java", "MySQL"],
    description: "参与淘宝核心业务开发，负责前后端联调和性能优化...",
    postedAt: "3天前",
    source: "Indeed",
    matchScore: 88,
    saved: false,
  },
  {
    id: "3",
    title: "前端技术专家",
    company: "腾讯",
    location: "深圳",
    salary: "50-80K",
    experience: "5年以上",
    education: "本科",
    tags: ["React", "微前端", "性能优化"],
    description: "负责微信生态前端技术规划和团队建设，推动前端技术创新...",
    postedAt: "1周前",
    source: "官网",
    matchScore: 82,
    saved: false,
  },
  {
    id: "4",
    title: "Web开发工程师",
    company: "美团",
    location: "北京",
    salary: "30-50K",
    experience: "2-4年",
    education: "本科",
    tags: ["React", "Redux", "Webpack"],
    description: "参与美团外卖商家端产品开发，负责商家营销工具的前端实现...",
    postedAt: "5天前",
    source: "LinkedIn",
    matchScore: 78,
    saved: true,
  },
  {
    id: "5",
    title: "前端开发工程师",
    company: "快手",
    location: "北京",
    salary: "35-60K",
    experience: "2-4年",
    education: "本科",
    tags: ["Vue", "TypeScript", "直播技术"],
    description: "负责快手直播间前端开发，优化直播互动体验...",
    postedAt: "1天前",
    source: "BOSS直聘",
    matchScore: 85,
    saved: false,
  },
]

const sourceColors: Record<string, string> = {
  "LinkedIn": "bg-blue-100 text-blue-700",
  "Indeed": "bg-orange-100 text-orange-700",
  "官网": "bg-green-100 text-green-700",
  "BOSS直聘": "bg-cyan-100 text-cyan-700",
}

export default function JobsPage() {
  const [jobs, setJobs] = useState(mockJobs)
  const [searchQuery, setSearchQuery] = useState("前端工程师")
  const [isSearching, setIsSearching] = useState(false)
  const [selectedJob, setSelectedJob] = useState(mockJobs[0])

  const handleSearch = () => {
    setIsSearching(true)
    setTimeout(() => {
      setIsSearching(false)
    }, 1500)
  }

  const toggleSave = (id: string) => {
    setJobs(jobs.map(job => 
      job.id === id ? { ...job, saved: !job.saved } : job
    ))
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">职位搜索</h1>
        <p className="text-muted-foreground">AI 自动搜索多个平台，为你匹配最合适的职位</p>
      </div>

      {/* 搜索栏 */}
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
                <SelectItem value="beijing">北京</SelectItem>
                <SelectItem value="shanghai">上海</SelectItem>
                <SelectItem value="hangzhou">杭州</SelectItem>
                <SelectItem value="shenzhen">深圳</SelectItem>
                <SelectItem value="guangzhou">广州</SelectItem>
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
                    设置更多筛选条件来精准匹配职位
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
            <Button onClick={handleSearch} disabled={isSearching}>
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
        </CardContent>
      </Card>

      {/* 职位列表和详情 */}
      <div className="grid lg:grid-cols-[400px_1fr] gap-6">
        {/* 职位列表 */}
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
                  onClick={() => setSelectedJob(job)}
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
                      {job.tags.slice(0, 2).map((tag, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-xs text-muted-foreground">{job.postedAt}</span>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </Card>

        {/* 职位详情 */}
        {selectedJob && (
          <Card className="h-[calc(100vh-280px)]">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-6">
                {/* 头部信息 */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h2 className="text-xl font-semibold">{selectedJob.title}</h2>
                      <Badge className={sourceColors[selectedJob.source]}>{selectedJob.source}</Badge>
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
                    <Button>
                      立即申请
                      <ChevronRight className="size-4 ml-1" />
                    </Button>
                  </div>
                </div>

                {/* 匹配度 */}
                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <div className="size-14 rounded-full bg-green-100 flex items-center justify-center">
                        <span className="text-xl font-bold text-green-700">{selectedJob.matchScore}%</span>
                      </div>
                      <div>
                        <p className="font-medium text-green-700">高度匹配</p>
                        <p className="text-sm text-green-600">你的简历与该职位高度匹配，建议尽快申请</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* 职位信息 */}
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

                {/* 技能要求 */}
                <div>
                  <h3 className="font-medium mb-3">技能要求</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedJob.tags.map((tag, i) => (
                      <Badge key={i} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* 职位描述 */}
                <div>
                  <h3 className="font-medium mb-3">职位描述</h3>
                  <div className="prose prose-sm max-w-none text-muted-foreground">
                    <p>{selectedJob.description}</p>
                    <h4 className="text-foreground mt-4">职责：</h4>
                    <ul>
                      <li>负责核心业务模块的前端开发和维护</li>
                      <li>参与前端架构设计和技术选型</li>
                      <li>优化前端性能，提升用户体验</li>
                      <li>参与代码评审，保证代码质量</li>
                    </ul>
                    <h4 className="text-foreground mt-4">要求：</h4>
                    <ul>
                      <li>计算机相关专业本科及以上学历</li>
                      <li>3年以上前端开发经验</li>
                      <li>熟练掌握 React/Vue 等主流框架</li>
                      <li>良好的沟通能力和团队协作精神</li>
                    </ul>
                  </div>
                </div>

                {/* 公司信息 */}
                <div>
                  <h3 className="font-medium mb-3">公司信息</h3>
                  <div className="flex items-center gap-4 p-4 rounded-lg border">
                    <div className="size-14 rounded-lg bg-muted flex items-center justify-center text-xl font-bold">
                      {selectedJob.company[0]}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium">{selectedJob.company}</p>
                      <p className="text-sm text-muted-foreground">互联网/移动互联网 | 10000人以上</p>
                    </div>
                    <Button variant="outline" size="sm">
                      <ExternalLink className="size-4 mr-2" />
                      官网
                    </Button>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </Card>
        )}
      </div>
    </div>
  )
}
