import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { generateAllImages, getImageScenes, modifyImageByText } from '../api/image'
import { useProjectStore } from '../stores/project'
import { usePolling } from '../hooks/usePolling'
import { IMAGE_POLL_INTERVAL } from '../lib/constants'
import type { ImageScenesResponse, SceneState } from '../types/api'

type PagePhase = 'generating' | 'review' | 'modifying'

export function ImagesPage() {
  const navigate = useNavigate()
  const { projectId, scenes, setScenes } = useProjectStore()

  const [phase, setPhase] = useState<PagePhase>('generating')
  const [localScenes, setLocalScenes] = useState<SceneState[]>(scenes)
  const [pollEnabled, setPollEnabled] = useState(false)
  const [modifyText, setModifyText] = useState('')
  const [modifying, setModifying] = useState(false)
  const [modifyError, setModifyError] = useState<string | null>(null)
  const [modifyResult, setModifyResult] = useState<{ changed_cuts: number[]; passed: boolean } | null>(null)
  const [genError, setGenError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    // Fire image generation
    generateAllImages(projectId).catch((err: unknown) => {
      const e = err as Error & { detail?: string }
      setGenError(e.detail ?? 'Image generation failed')
      setPollEnabled(false)
    })
    setPollEnabled(true)
  }, [projectId])

  // Poll image scenes until all done
  usePolling<ImageScenesResponse>({
    fetcher: () => getImageScenes(projectId!),
    interval: IMAGE_POLL_INTERVAL,
    enabled: pollEnabled && phase === 'generating',
    onData: (data) => {
      const updated: SceneState[] = data.scenes.map(s => ({
        scene_id: s.scene_id,
        cut_number: s.cut_number,
        image_url: s.image_url,
        image_status: s.image_status,
        video_status: 'pending',
        prompt: s.prompt,
      }))
      setLocalScenes(updated)
      setScenes(updated)
    },
    shouldStop: (data) => {
      const allSettled = data.scenes.every(
        s => s.image_status !== 'pending' && s.image_status !== 'generating'
      )
      if (allSettled) {
        setPollEnabled(false)
        setPhase('review')
      }
      return allSettled
    },
    onError: (err) => {
      console.error('image poll error:', err)
    },
  })

  async function handleModify() {
    if (!projectId || !modifyText.trim()) return
    setModifying(true)
    setModifyError(null)
    setModifyResult(null)
    setPhase('modifying')
    try {
      const res = await modifyImageByText(projectId, modifyText)
      setModifyResult({ changed_cuts: res.changed_cuts, passed: res.eval_passed })
      if (res.eval_passed && res.images) {
        // C3: compute updated scenes first, then pass same ref to both state and store
        const updatedMap = new Map(res.images.map(img => [img.cut_number, img]))
        const updatedScenes = localScenes.map(sc => {
          const update = updatedMap.get(sc.cut_number)
          if (!update) return sc
          return {
            ...sc,
            image_url: update.image_url ?? sc.image_url,
            image_status: (update.image_status as SceneState['image_status']) ?? sc.image_status,
          }
        })
        setLocalScenes(updatedScenes)
        setScenes(updatedScenes)
        setModifyText('')
      } else if (!res.eval_passed) {
        setModifyError(`수정된 스토리보드가 평가를 통과하지 못했습니다. (점수: ${res.eval_result.total_average?.toFixed(1) ?? '?'})`)
      }
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setModifyError(e.detail ?? '수정 실패')
    } finally {
      setModifying(false)
      setPhase('review')
    }
  }

  function handleConfirm() {
    navigate('/generating')
  }

  const total = localScenes.length
  const doneCount = localScenes.filter(
    s => s.image_status === 'done' || s.image_status === 'modified'
  ).length
  const failedCount = localScenes.filter(s => s.image_status === 'failed').length
  const progress = total === 0 ? 0 : Math.round((doneCount / total) * 100)
  const allSettled = total > 0 && localScenes.every(
    s => s.image_status !== 'pending' && s.image_status !== 'generating'
  )

  if (!projectId) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: '#50508A' }}>
        No project found.{' '}
        <button onClick={() => navigate('/')} style={{ color: '#6C63FF', background: 'none', border: 'none', cursor: 'pointer' }}>
          처음부터
        </button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px 80px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 24, fontWeight: 700, margin: 0, color: '#F0F0FF' }}>
            {phase === 'generating' ? '이미지 생성 중...' : '이미지 컷씬 확인'}
          </h2>
          <p style={{ color: '#50508A', margin: '4px 0 0', fontSize: 14 }}>
            {phase === 'generating'
              ? `${doneCount} / ${total} 컷 완료`
              : `${doneCount}개 성공${failedCount > 0 ? `, ${failedCount}개 실패` : ''} · 수정 후 확인하세요`}
          </p>
        </div>
        {allSettled && (
          <button
            onClick={handleConfirm}
            style={{
              padding: '10px 24px', borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg,#22D4A0,#00E5FF)',
              color: '#080810', fontSize: 14, fontWeight: 700, cursor: 'pointer',
              fontFamily: 'Syne, sans-serif', boxShadow: '0 4px 20px rgba(34,212,160,0.3)',
            }}
          >
            영상 제작 시작 →
          </button>
        )}
      </div>

      {/* Progress bar */}
      {phase === 'generating' && (
        <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 14, padding: 18, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: '#A8A4FF' }}>이미지 생성 진행률</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#6C63FF' }}>{progress}%</span>
          </div>
          <div style={{ height: 5, background: 'rgba(108,99,255,0.15)', borderRadius: 3 }}>
            <div style={{ height: '100%', width: `${progress}%`, background: 'linear-gradient(90deg,#6C63FF,#00E5FF)', borderRadius: 3, transition: 'width 0.5s ease' }} />
          </div>
        </div>
      )}

      {genError && (
        <div style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.3)', borderRadius: 12, padding: 14, marginBottom: 16, color: '#FF4D6D', fontSize: 13 }}>
          {genError}
        </div>
      )}

      {/* Image cut cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16, marginBottom: 28 }}>
        {(localScenes.length > 0 ? localScenes : Array.from({ length: 6 }).map((_, i): SceneState => ({
          scene_id: '', cut_number: i + 1, image_status: 'pending', video_status: 'pending',
        }))).map((sc) => {
          const isDone = sc.image_status === 'done' || sc.image_status === 'modified'
          const isFailed = sc.image_status === 'failed'
          const isPending = sc.image_status === 'pending' || sc.image_status === 'generating'
          const isChanged = modifyResult?.changed_cuts.includes(sc.cut_number)

          return (
            <div key={sc.cut_number} style={{
              background: 'rgba(12,12,22,0.95)',
              border: `1px solid ${isChanged ? 'rgba(0,229,255,0.5)' : isDone ? 'rgba(108,99,255,0.25)' : isFailed ? 'rgba(255,77,109,0.3)' : 'rgba(108,99,255,0.12)'}`,
              borderRadius: 16, overflow: 'hidden',
              boxShadow: isChanged ? '0 0 16px rgba(0,229,255,0.15)' : undefined,
            }}>
              {/* Image area */}
              <div style={{ height: 160, position: 'relative', background: 'linear-gradient(135deg,rgba(108,99,255,0.15),rgba(0,229,255,0.08))' }}>
                {sc.image_url ? (
                  <img
                    src={sc.image_url}
                    alt={`Cut ${sc.cut_number}`}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <div className="shimmer" style={{ position: 'absolute', inset: 0 }} />
                )}

                {/* Status overlay when pending/generating */}
                {isPending && (
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(8,8,16,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: 28, height: 28, borderRadius: '50%', border: '3px solid #6C63FF', borderTopColor: 'transparent', animation: 'spin 0.9s linear infinite' }} />
                  </div>
                )}

                {isFailed && (
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(255,77,109,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ color: '#FF4D6D', fontSize: 13, fontWeight: 600 }}>생성 실패</span>
                  </div>
                )}

                {isChanged && (
                  <div style={{ position: 'absolute', top: 8, right: 8, padding: '3px 8px', borderRadius: 100, background: 'rgba(0,229,255,0.9)', color: '#080810', fontSize: 10, fontWeight: 700 }}>
                    수정됨
                  </div>
                )}
              </div>

              {/* Card body */}
              <div style={{ padding: '12px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: '#6C63FF', fontWeight: 600 }}>
                    Cut {sc.cut_number}
                  </span>
                  <span style={{ fontSize: 11, color: isDone ? '#22D4A0' : isFailed ? '#FF4D6D' : '#50508A', fontWeight: 600 }}>
                    {isDone ? '✓ 완료' : isFailed ? '✗ 실패' : '생성 중...'}
                  </span>
                </div>
                {sc.prompt && (
                  <p style={{ margin: '6px 0 0', fontSize: 11, color: '#50508A', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                    {sc.prompt}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Modify panel — only shown when images are ready */}
      {allSettled && (
        <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 18, padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#F0F0FF', fontFamily: 'Syne, sans-serif', marginBottom: 4 }}>
            이미지 수정
          </div>
          <p style={{ color: '#50508A', fontSize: 13, margin: '0 0 16px' }}>
            마음에 들지 않는 부분을 텍스트로 설명하면 변경된 컷만 재생성합니다
          </p>

          {modifyResult && (
            <div style={{
              padding: '10px 14px', borderRadius: 10, marginBottom: 14,
              background: modifyResult.passed ? 'rgba(34,212,160,0.1)' : 'rgba(255,77,109,0.1)',
              border: `1px solid ${modifyResult.passed ? 'rgba(34,212,160,0.3)' : 'rgba(255,77,109,0.3)'}`,
              color: modifyResult.passed ? '#22D4A0' : '#FF4D6D', fontSize: 13,
            }}>
              {modifyResult.passed
                ? `✓ Cut ${modifyResult.changed_cuts.join(', ')} 재생성 완료`
                : modifyError}
            </div>
          )}

          {!modifyResult && modifyError && (
            <div style={{ padding: '10px 14px', borderRadius: 10, marginBottom: 14, background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.3)', color: '#FF4D6D', fontSize: 13 }}>
              {modifyError}
            </div>
          )}

          <textarea
            value={modifyText}
            onChange={e => setModifyText(e.target.value)}
            rows={3}
            placeholder="예: 1번 컷의 배경을 밤하늘로 바꿔줘, 3번 컷 캐릭터 표정을 더 강렬하게..."
            style={{
              width: '100%', background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(108,99,255,0.2)', borderRadius: 10,
              padding: '10px 12px', color: '#F0F0FF', fontSize: 14,
              fontFamily: 'DM Sans, sans-serif', outline: 'none', resize: 'none', boxSizing: 'border-box',
            }}
          />

          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <button
              onClick={handleModify}
              disabled={!modifyText.trim() || modifying}
              style={{
                padding: '9px 22px', borderRadius: 10, border: 'none',
                background: modifyText.trim() && !modifying ? 'linear-gradient(135deg,#6C63FF,#5A54E8)' : 'rgba(108,99,255,0.2)',
                color: modifyText.trim() && !modifying ? '#fff' : '#50508A',
                fontSize: 13, fontWeight: 600,
                cursor: modifyText.trim() && !modifying ? 'pointer' : 'not-allowed',
              }}
            >
              {modifying ? '⟳ 수정 중...' : '✎ 수정 적용'}
            </button>
            <button
              onClick={handleConfirm}
              style={{
                flex: 1, padding: '9px', borderRadius: 10, border: 'none',
                background: 'linear-gradient(135deg,#22D4A0,#00E5FF)',
                color: '#080810', fontSize: 13, fontWeight: 700, cursor: 'pointer',
              }}
            >
              이미지 확정 — 영상 제작 시작 →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
