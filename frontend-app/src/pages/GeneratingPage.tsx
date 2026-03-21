import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { generateAllVideos, getVideoScenes, finalizeVideo } from '../api/video'
import { useProjectStore } from '../stores/project'
import { usePolling } from '../hooks/usePolling'
import { VIDEO_POLL_INTERVAL } from '../lib/constants'
import type { VideoScenesResponse, SceneState } from '../types/api'

export function GeneratingPage() {
  const navigate = useNavigate()
  const { projectId, scenes, setGenerationPhase, setClipUrls } = useProjectStore()

  const [localScenes, setLocalScenes] = useState<SceneState[]>(scenes)
  const [pollEnabled, setPollEnabled] = useState(false)
  const [finalizing, setFinalizing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    // Fire video generation (fire-and-forget)
    generateAllVideos(projectId).catch((err: unknown) => {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? '영상 생성 실패')
      setPollEnabled(false)
    })
    setPollEnabled(true)
  }, [projectId])

  usePolling<VideoScenesResponse>({
    fetcher: () => getVideoScenes(projectId!),
    interval: VIDEO_POLL_INTERVAL,
    enabled: pollEnabled,
    onData: (data) => {
      setLocalScenes(prev =>
        prev.map(sc => {
          const v = data.scenes.find(s => s.scene_id === sc.scene_id || s.cut_number === sc.cut_number)
          if (!v) return sc
          return { ...sc, video_url: v.video_url, video_status: v.video_status }
        })
      )
    },
    shouldStop: (data) => {
      const allSettled = data.scenes.every(
        s => s.video_status !== 'pending' && s.video_status !== 'generating'
      )
      if (allSettled) {
        setPollEnabled(false)
        doFinalize()
      }
      return allSettled
    },
    onError: (err) => console.error('video poll error:', err),
  })

  async function doFinalize() {
    if (!projectId) return
    setFinalizing(true)
    try {
      const res = await finalizeVideo(projectId)
      setClipUrls(res.clip_urls)
      setGenerationPhase('done')
      navigate('/result')
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? '영상 취합 실패')
    } finally {
      setFinalizing(false)
    }
  }

  const total = localScenes.length
  const doneCount = localScenes.filter(s => s.video_status === 'done').length
  const failedCount = localScenes.filter(s => s.video_status === 'failed' || s.video_status === 'skipped').length
  const progress = total === 0 ? 0 : finalizing ? 98 : Math.round((doneCount / total) * 100)

  const displayScenes: SceneState[] = localScenes.length > 0
    ? localScenes
    : Array.from({ length: 6 }).map((_, i): SceneState => ({
        scene_id: '', cut_number: i + 1, image_status: 'done', video_status: 'pending',
      }))

  if (!projectId) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: '#50508A' }}>
        No project.{' '}
        <button onClick={() => navigate('/')} style={{ color: '#6C63FF', background: 'none', border: 'none', cursor: 'pointer' }}>
          처음부터
        </button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 16px 80px' }}>
      <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 24, fontWeight: 700, margin: '0 0 8px', color: '#F0F0FF' }}>
        {finalizing ? '영상 취합 중...' : '영상 생성 중'}
      </h2>
      <p style={{ color: '#50508A', fontSize: 14, margin: '0 0 24px' }}>
        확정된 이미지로 영상 클립을 생성합니다 — 컷당 최대 5분 소요
      </p>

      {/* Progress bar */}
      <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#F0F0FF' }}>
            {finalizing ? '최종 취합 중...' : `${doneCount} / ${total} 클립 완료`}
          </span>
          <span style={{ fontSize: 14, fontWeight: 700, color: progress === 100 ? '#22D4A0' : '#6C63FF' }}>
            {progress}%
          </span>
        </div>
        <div style={{ height: 6, background: 'rgba(108,99,255,0.15)', borderRadius: 3 }}>
          <div style={{
            height: '100%', width: `${progress}%`,
            background: progress >= 98 ? '#22D4A0' : 'linear-gradient(90deg,#6C63FF,#00E5FF)',
            borderRadius: 3, transition: 'width 0.6s ease',
          }} />
        </div>
        {failedCount > 0 && (
          <p style={{ margin: '10px 0 0', fontSize: 12, color: '#FFC107' }}>
            ⚠ {failedCount}개 클립 실패 — 나머지 클립으로 계속 진행됩니다
          </p>
        )}
      </div>

      {error && (
        <div style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.3)', borderRadius: 12, padding: 14, marginBottom: 16, color: '#FF4D6D', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Scene clip cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 14 }}>
        {displayScenes.map((sc) => {
          const isDone = sc.video_status === 'done'
          const isFailed = sc.video_status === 'failed' || sc.video_status === 'skipped'
          const isPending = sc.video_status === 'pending' || sc.video_status === 'generating'

          return (
            <div key={sc.cut_number} style={{
              background: 'rgba(12,12,22,0.95)',
              border: `1px solid ${isDone ? 'rgba(34,212,160,0.35)' : isFailed ? 'rgba(255,77,109,0.3)' : 'rgba(108,99,255,0.12)'}`,
              borderRadius: 14, overflow: 'hidden',
            }}>
              {/* Thumbnail with video status overlay */}
              <div style={{ height: 120, position: 'relative', background: 'linear-gradient(135deg,rgba(108,99,255,0.15),rgba(0,229,255,0.08))' }}>
                {sc.image_url && (
                  <img src={sc.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                )}
                {!sc.image_url && <div className="shimmer" style={{ position: 'absolute', inset: 0 }} />}

                {/* Overlay: video progress */}
                {!isDone && sc.image_url && (
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(8,8,16,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {isPending && (
                      <div style={{ width: 28, height: 28, borderRadius: '50%', border: '3px solid #00E5FF', borderTopColor: 'transparent', animation: 'spin 1s linear infinite' }} />
                    )}
                    {isFailed && <span style={{ color: '#FF4D6D', fontSize: 22 }}>✗</span>}
                  </div>
                )}

                {isDone && (
                  <div style={{ position: 'absolute', top: 8, right: 8, padding: '3px 8px', borderRadius: 100, background: 'rgba(34,212,160,0.9)', color: '#080810', fontSize: 10, fontWeight: 700 }}>
                    ✓ 완료
                  </div>
                )}
              </div>

              <div style={{ padding: '10px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#6C63FF' }}>Cut {sc.cut_number}</span>
                  <span style={{ fontSize: 11, color: isDone ? '#22D4A0' : isFailed ? '#FF4D6D' : '#50508A', fontWeight: 600 }}>
                    {isDone ? '영상 완료' : isFailed ? '실패' : '생성 중...'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
