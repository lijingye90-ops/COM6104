"use client"

import { useState } from "react"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { 
  Upload, 
  FileText, 
  MoreVertical, 
  Download, 
  Trash2, 
  Eye, 
  Star,
  StarOff,
  Clock,
  CheckCircle2,
  File,
  Plus
} from "lucide-react"

// 模拟简历数据
const mockResumes = [
  {
    id: "1",
    name: "张小明_前端工程师简历_v3.pdf",
    type: "pdf",
    size: "256 KB",
    uploadedAt: "2024-01-15",
    isDefault: true,
    status: "已解析",
  },
  {
    id: "2",
    name: "张小明_全栈开发简历.pdf",
    type: "pdf",
    size: "312 KB",
    uploadedAt: "2024-01-10",
    isDefault: false,
    status: "已解析",
  },
  {
    id: "3",
    name: "张小明_英文简历.pdf",
    type: "pdf",
    size: "198 KB",
    uploadedAt: "2024-01-05",
    isDefault: false,
    status: "已解析",
  },
]

// 模拟解析出的简历数据
const parsedResumeData = {
  name: "张小明",
  title: "高级前端工程师",
  email: "xiaoming@example.com",
  phone: "138-xxxx-xxxx",
  location: "北京市",
  summary: "5年前端开发经验，精通 React、Vue、TypeScript，有大型项目架构经验。擅长性能优化和工程化建设。",
  experience: [
    {
      company: "某大厂",
      position: "高级前端工程师",
      duration: "2022.03 - 至今",
      description: "负责核心业务前端架构设计和开发，带领团队完成多个重点项目",
    },
    {
      company: "某互联网公司",
      position: "前端工程师",
      duration: "2020.06 - 2022.02",
      description: "参与电商平台前端开发，负责订单模块的设计和实现",
    },
  ],
  skills: ["React", "Vue", "TypeScript", "Node.js", "Webpack", "性能优化", "微前端"],
  education: [
    {
      school: "某985大学",
      degree: "计算机科学与技术 本科",
      duration: "2016 - 2020",
    },
  ],
}

export default function ResumePage() {
  const [resumes, setResumes] = useState(mockResumes)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)

  const handleSetDefault = (id: string) => {
    setResumes(resumes.map(r => ({
      ...r,
      isDefault: r.id === id
    })))
  }

  const handleDelete = (id: string) => {
    setResumes(resumes.filter(r => r.id !== id))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">简历管理</h1>
          <p className="text-muted-foreground">上传和管理你的简历文件，AI 将自动解析内容</p>
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
              <DialogDescription>
                支持 PDF、Word 格式，AI 将自动解析简历内容
              </DialogDescription>
            </DialogHeader>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25"
              }`}
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setIsDragging(false)
                // 处理文件上传
              }}
            >
              <Upload className="size-10 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-2">
                拖拽文件到这里，或点击选择文件
              </p>
              <Input
                type="file"
                accept=".pdf,.doc,.docx"
                className="hidden"
                id="resume-upload"
              />
              <Label htmlFor="resume-upload" asChild>
                <Button variant="secondary" size="sm">
                  选择文件
                </Button>
              </Label>
              <p className="text-xs text-muted-foreground mt-4">
                支持 PDF、DOC、DOCX 格式，最大 10MB
              </p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setUploadDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={() => setUploadDialogOpen(false)}>
                上传
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs defaultValue="files">
        <TabsList>
          <TabsTrigger value="files">简历文件</TabsTrigger>
          <TabsTrigger value="parsed">解析内容</TabsTrigger>
        </TabsList>

        <TabsContent value="files" className="mt-6">
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
                        <p className="font-medium truncate">{resume.name}</p>
                        {resume.isDefault && (
                          <Badge variant="secondary" className="shrink-0">
                            <Star className="size-3 mr-1 fill-current" />
                            默认
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                        <span>{resume.size}</span>
                        <span>|</span>
                        <span className="flex items-center gap-1">
                          <Clock className="size-3" />
                          {resume.uploadedAt}
                        </span>
                        <span>|</span>
                        <span className="flex items-center gap-1 text-green-600">
                          <CheckCircle2 className="size-3" />
                          {resume.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm">
                        <Eye className="size-4 mr-2" />
                        预览
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Download className="size-4 mr-2" />
                            下载
                          </DropdownMenuItem>
                          {!resume.isDefault && (
                            <DropdownMenuItem onClick={() => handleSetDefault(resume.id)}>
                              <Star className="size-4 mr-2" />
                              设为默认
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            className="text-destructive"
                            onClick={() => handleDelete(resume.id)}
                          >
                            <Trash2 className="size-4 mr-2" />
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="parsed" className="mt-6 space-y-6">
          {/* 基本信息 */}
          <Card>
            <CardHeader>
              <CardTitle>基本信息</CardTitle>
              <CardDescription>从简历中解析出的个人信息</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label className="text-muted-foreground">姓名</Label>
                  <p className="font-medium mt-1">{parsedResumeData.name}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">职位</Label>
                  <p className="font-medium mt-1">{parsedResumeData.title}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">邮箱</Label>
                  <p className="font-medium mt-1">{parsedResumeData.email}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">电话</Label>
                  <p className="font-medium mt-1">{parsedResumeData.phone}</p>
                </div>
                <div className="md:col-span-2">
                  <Label className="text-muted-foreground">个人简介</Label>
                  <p className="mt-1">{parsedResumeData.summary}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 工作经历 */}
          <Card>
            <CardHeader>
              <CardTitle>工作经历</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {parsedResumeData.experience.map((exp, i) => (
                <div key={i} className="relative pl-6 pb-6 last:pb-0 border-l-2 border-muted last:border-transparent">
                  <div className="absolute -left-[9px] top-0 size-4 rounded-full bg-foreground" />
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium">{exp.position}</h4>
                      <p className="text-muted-foreground">{exp.company}</p>
                    </div>
                    <Badge variant="outline">{exp.duration}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">{exp.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* 技能标签 */}
          <Card>
            <CardHeader>
              <CardTitle>技能标签</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {parsedResumeData.skills.map((skill, i) => (
                  <Badge key={i} variant="secondary">
                    {skill}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* 教育背景 */}
          <Card>
            <CardHeader>
              <CardTitle>教育背景</CardTitle>
            </CardHeader>
            <CardContent>
              {parsedResumeData.education.map((edu, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{edu.school}</p>
                    <p className="text-sm text-muted-foreground">{edu.degree}</p>
                  </div>
                  <Badge variant="outline">{edu.duration}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
