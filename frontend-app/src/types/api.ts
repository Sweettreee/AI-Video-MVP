// ── Plot ──────────────────────────────────────────────────────────────────────

export interface PlotRequest {
  genre: string
  character: string
  mood: string
  story: string
  must_have?: string
  extra?: string
}

export interface PlotGenerateResponse {
  project_id: string
  plain_text: string
}

export interface PlotEvalResponse {
  code_scores: Record<string, number>
  code_average: number
  model_scores: Record<string, number>
  model_average: number
  total_average: number
  passed: boolean
  failed_items: string[]
  previous_total?: number
  model_reasoning?: string
  failure_count?: number
  loop_warning?: string
  template_suggestions?: Array<{ genre: string; character: string; mood: string; story: string }>
}

export interface Feedback {
  feedback_type: string
  detail: string
  target_cuts?: number[]
  free_text?: string
}

export interface PlotAdviceRequest {
  project_id: string
  failed_items?: string[]
  feedback?: Feedback[]
}

export interface PlotModifyRequest {
  project_id: string
  modification_request: string
}

export interface HumanEvalRequest {
  project_id: string
  H1: boolean
  H2: boolean
  H3: boolean
  feedback?: string
}

export interface HumanEvalResponse {
  project_id: string
  passed: boolean
  failed_items: string[]
  message: string
}

export interface SceneData {
  scene_id?: string
  cut_number: number
  main_character: string
  sub_character?: string
  action: string
  pose: string
  background: string
  era: string
  composition: string
  lighting: string
  mood: string
  story_beat: string
  duration_seconds: number
}

export interface PlotConfirmResponse {
  project_id: string
  scene_count: number
  scenes: SceneData[]
}

export interface ProjectStatus {
  project_id: string
  status: string
  current_stage: string
  genre: string
  plain_text: string
  has_global_context: boolean
  created_at?: string
}

// ── Image ─────────────────────────────────────────────────────────────────────

export interface ImageSceneStatus {
  scene_id: string
  cut_number: number
  image_url?: string
  image_status: 'pending' | 'generating' | 'done' | 'failed' | 'modified'
  prompt?: string
  error?: string
}

export interface ImageGenerateAllResponse {
  project_id: string
  images: ImageSceneStatus[]
}

export interface ImageScenesResponse {
  project_id: string
  scenes: ImageSceneStatus[]
}

export interface ImageModifyByTextResponse {
  project_id: string
  changed_cuts: number[]
  eval_passed: boolean
  eval_result: {
    total_average?: number
    failed_items?: string[]
    code_scores?: Record<string, number>
    model_scores?: Record<string, number>
  }
  images?: Array<{
    cut_number: number
    image_url?: string
    image_status: string
  }>
  message?: string
}

// ── Video ─────────────────────────────────────────────────────────────────────

export interface VideoSceneStatus {
  scene_id: string
  cut_number: number
  image_url?: string
  video_url?: string
  video_status: 'pending' | 'generating' | 'done' | 'failed' | 'skipped'
  error?: string
  reason?: string
}

export interface VideoGenerateAllResponse {
  project_id: string
  videos: VideoSceneStatus[]
}

export interface VideoScenesResponse {
  project_id: string
  scenes: VideoSceneStatus[]
}

export interface FinalizeResponse {
  project_id: string
  total_clips: number
  ready_clips: number
  clips: Array<{
    cut_number: number
    video_url?: string
    image_url?: string
    video_status: string
  }>
  clip_urls: string[]
}

// ── Combined scene state (used in store) ─────────────────────────────────────

export interface SceneState {
  scene_id: string
  cut_number: number
  image_url?: string
  image_status: ImageSceneStatus['image_status']
  video_url?: string
  video_status: VideoSceneStatus['video_status']
  prompt?: string
}
