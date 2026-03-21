import ky from 'ky'
import { API_BASE } from '../lib/constants'

export const api = ky.create({
  prefixUrl: API_BASE,
  timeout: 360_000,
  hooks: {
    beforeError: [
      async (error) => {
        const { response } = error
        if (response) {
          try {
            const body = await response.clone().json() as { detail?: string }
            if (body.detail) {
              (error as unknown as { detail: string }).detail = body.detail
            }
          } catch {}
        }
        return error
      },
    ],
  },
})

export async function apiPost<T>(path: string, json?: unknown): Promise<T> {
  return api.post(path, json ? { json } : undefined).json<T>()
}

export async function apiGet<T>(path: string): Promise<T> {
  return api.get(path).json<T>()
}
