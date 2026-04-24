"use client"

export type StoredResume = {
  id: string
  filename: string
  path: string
  uploadedAt: string
  sizeBytes: number
  previewText: string
  isDefault: boolean
}

const RESUME_LIST_KEY = "job-hunt-resumes"
const RESUME_PATH_KEY = "job-hunt-resume-path"

export function loadStoredResumes(): StoredResume[] {
  if (typeof window === "undefined") {
    return []
  }

  try {
    const raw = window.localStorage.getItem(RESUME_LIST_KEY)
    if (!raw) {
      return []
    }

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }

    return parsed.filter(Boolean)
  } catch {
    return []
  }
}

export function saveStoredResumes(resumes: StoredResume[]) {
  window.localStorage.setItem(RESUME_LIST_KEY, JSON.stringify(resumes))
  const defaultResume = resumes.find((resume) => resume.isDefault) ?? resumes[0]
  if (defaultResume) {
    window.localStorage.setItem(RESUME_PATH_KEY, defaultResume.path)
  } else {
    window.localStorage.removeItem(RESUME_PATH_KEY)
  }
}

export function setDefaultResumePath(path: string) {
  window.localStorage.setItem(RESUME_PATH_KEY, path)
}

export function getDefaultResumePath() {
  if (typeof window === "undefined") {
    return ""
  }

  return window.localStorage.getItem(RESUME_PATH_KEY) ?? ""
}
