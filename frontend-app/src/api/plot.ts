import { apiPost, apiGet } from './client'
import type {
  PlotRequest, PlotGenerateResponse, PlotEvalResponse,
  PlotAdviceRequest, PlotModifyRequest, HumanEvalRequest,
  HumanEvalResponse, PlotConfirmResponse, ProjectStatus,
} from '../types/api'

export const generatePlot = (req: PlotRequest) =>
  apiPost<PlotGenerateResponse>('api/plot/generate', req)

export const evaluatePlot = (project_id: string) =>
  apiPost<PlotEvalResponse>('api/plot/evaluate', { project_id })

export const getAdvice = (req: PlotAdviceRequest) =>
  apiPost<{ project_id: string; advice: string }>('api/plot/advice', req)

export const modifyPlot = (req: PlotModifyRequest) =>
  apiPost<PlotGenerateResponse>('api/plot/modify', req)

export const humanEval = (req: HumanEvalRequest) =>
  apiPost<HumanEvalResponse>('api/plot/human-eval', req)

export const confirmPlot = (project_id: string) =>
  apiPost<PlotConfirmResponse>('api/plot/confirm', { project_id })

export const getProject = (project_id: string) =>
  apiGet<ProjectStatus>(`api/plot/${project_id}`)
