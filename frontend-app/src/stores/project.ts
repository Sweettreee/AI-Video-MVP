import { create } from 'zustand'
import type { PlotRequest, PlotEvalResponse, SceneState } from '../types/api'

interface ProjectStore {
  // Navigation
  projectId: string | null
  currentStep: number

  // Step 1
  formData: PlotRequest | null

  // Step 2
  plainText: string | null

  // Step 3
  evalResult: PlotEvalResponse | null
  humanEvalPassed: boolean

  // Step 4
  scenes: SceneState[]
  generationPhase: 'idle' | 'images' | 'videos' | 'finalizing' | 'done'

  // Step 5
  clipUrls: string[]

  // Actions
  setProjectId: (id: string) => void
  setStep: (step: number) => void
  setFormData: (data: PlotRequest) => void
  setPlainText: (text: string) => void
  setEvalResult: (result: PlotEvalResponse) => void
  setHumanEvalPassed: (passed: boolean) => void
  setScenes: (scenes: SceneState[]) => void
  updateSceneImage: (sceneId: string, image_url: string, image_status: SceneState['image_status']) => void
  updateSceneVideo: (sceneId: string, video_url: string | undefined, video_status: SceneState['video_status']) => void
  setGenerationPhase: (phase: ProjectStore['generationPhase']) => void
  setClipUrls: (urls: string[]) => void
  reset: () => void
}

const initial = {
  projectId: null,
  currentStep: 1,
  formData: null,
  plainText: null,
  evalResult: null,
  humanEvalPassed: false,
  scenes: [],
  generationPhase: 'idle' as const,
  clipUrls: [],
}

export const useProjectStore = create<ProjectStore>((set) => ({
  ...initial,

  setProjectId: (id) => set({ projectId: id }),
  setStep: (step) => set({ currentStep: step }),
  setFormData: (data) => set({ formData: data }),
  setPlainText: (text) => set({ plainText: text }),
  setEvalResult: (result) => set({ evalResult: result }),
  setHumanEvalPassed: (passed) => set({ humanEvalPassed: passed }),
  setScenes: (scenes) => set({ scenes }),
  updateSceneImage: (sceneId, image_url, image_status) =>
    set((s) => ({
      scenes: s.scenes.map((sc) =>
        sc.scene_id === sceneId ? { ...sc, image_url, image_status } : sc
      ),
    })),
  updateSceneVideo: (sceneId, video_url, video_status) =>
    set((s) => ({
      scenes: s.scenes.map((sc) =>
        sc.scene_id === sceneId ? { ...sc, video_url, video_status } : sc
      ),
    })),
  setGenerationPhase: (phase) => set({ generationPhase: phase }),
  setClipUrls: (urls) => set({ clipUrls: urls }),
  reset: () => set(initial),
}))
