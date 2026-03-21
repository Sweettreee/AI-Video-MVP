import { apiPost, apiGet } from './client'
import type {
  ImageGenerateAllResponse, ImageScenesResponse,
  ImageModifyByTextResponse,
} from '../types/api'

export const generateAllImages = (project_id: string) =>
  apiPost<ImageGenerateAllResponse>('api/image/generate-all', { project_id })

export const getImageScenes = (project_id: string) =>
  apiGet<ImageScenesResponse>(`api/image/${project_id}/scenes`)

export const modifyImageByText = (project_id: string, modification_request: string) =>
  apiPost<ImageModifyByTextResponse>('api/image/modify-by-text', { project_id, modification_request })

export const modifyImage = (scene_id: string, modified_prompt: string) =>
  apiPost<{ scene_id: string; updated_prompt: string; new_image_url: string; image_status: string }>(
    'api/image/modify',
    { scene_id, modified_prompt }
  )
