import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { evaluatePlot, getAdvice, modifyPlot, humanEval, confirmPlot } from '../api/plot'
import { useProjectStore } from '../stores/project'
import { scoreToColor } from '../lib/utils'

type EvalPhase = 'running' | 'failed' | 'awaiting_human' | 'human_failed'

export function EvaluatePage() {
  const navigate = useNavigate()
  const { projectId, evalResult, setEvalResult, setPlainText, setScenes } = useProjectStore()

  const [phase, setPhase] = useState<EvalPhase>('running')
  const [confirming, setConfirming] = useState(false)
  const [advice, setAdvice] = useState<string | null>(null)
  const [modifyText, setModifyText] = useState('')
  const [modifying, setModifying] = useState(false)
  const [H1, setH1] = useState(false)
  const [H2, setH2] = useState(false)
  const [H3, setH3] = useState(false)
  const [humanFeedback, setHumanFeedback] = useState('')
  const [humanFailed, setHumanFailed] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    runEval()
  }, [])

  async function runEval() {
    if (!projectId) return
    setPhase('running')
    setError(null)
    try {
      const res = await evaluatePlot(projectId)
      setEvalResult(res)
      if (res.passed) {
        setPhase('awaiting_human')
      } else {
        setPhase('failed')
        try {
          const adv = await getAdvice({ project_id: projectId, failed_items: res.failed_items })
          setAdvice(adv.advice)
        } catch {}
      }
    } catch (err: unknown) {
      const e = err as Error & { detail?: string; status?: number }
      if (e.status === 422) {
        setError('Maximum retries reached. Please try a different story concept or use one of the example prompts.')
      } else {
        setError(e.detail ?? 'Evaluation failed')
      }
      setPhase('failed')
    }
  }

  async function handleRetry() {
    if (!projectId || !modifyText.trim()) return
    setModifying(true)
    setError(null)
    try {
      const res = await modifyPlot({ project_id: projectId, modification_request: modifyText })
      setPlainText(res.plain_text)
      setModifyText('')
      setAdvice(null)
      await runEval()
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? 'Modification failed')
      setPhase('failed')
    } finally {
      setModifying(false)
    }
  }

  async function handleHumanEval() {
    if (!projectId || confirming) return
    setError(null)
    setConfirming(true)
    try {
      const res = await humanEval({ project_id: projectId, H1, H2, H3, feedback: humanFeedback || undefined })
      if (res.passed) {
        const confirmed = await confirmPlot(projectId)
        setScenes(confirmed.scenes.map(sc => ({
          scene_id: sc.scene_id ?? '',
          cut_number: sc.cut_number,
          image_status: 'pending' as const,
          video_status: 'pending' as const,
        })))
        navigate('/images')
      } else {
        setHumanFailed(res.failed_items)
        setPhase('human_failed')
      }
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? 'Human evaluation failed')
    } finally {
      setConfirming(false)
    }
  }

  const r = evalResult

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 16px 80px' }}>
      <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 24, fontWeight: 700, margin: '0 0 8px', color: '#F0F0FF' }}>
        AI Evaluation
      </h2>
      <p style={{ color: '#50508A', margin: '0 0 24px', fontSize: 14 }}>
        Your storyboard is evaluated on structure, quality, and safety
      </p>

      {/* Eval status bar */}
      <div style={{ background: 'rgba(12,12,22,0.95)', border: `1px solid ${phase === 'running' ? 'rgba(108,99,255,0.3)' : r?.passed ? 'rgba(34,212,160,0.3)' : 'rgba(255,77,109,0.3)'}`, borderRadius: 16, padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {phase === 'running' && (
            <div style={{ width: 20, height: 20, borderRadius: '50%', border: '3px solid #6C63FF', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }} />
          )}
          {phase !== 'running' && (
            <div style={{ width: 24, height: 24, borderRadius: '50%', background: r?.passed ? '#22D4A0' : '#FF4D6D', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#fff' }}>
              {r?.passed ? '✓' : '✗'}
            </div>
          )}
          <div>
            <div style={{ fontWeight: 700, color: '#F0F0FF', fontSize: 16, fontFamily: 'Syne, sans-serif' }}>
              {phase === 'running' ? 'Evaluating storyboard...' : r?.passed ? 'Storyboard Passed!' : 'Needs Improvement'}
            </div>
            {r && (
              <div style={{ fontSize: 13, color: '#50508A', marginTop: 2 }}>
                Total score: <span style={{ color: scoreToColor(r.total_average), fontWeight: 600 }}>{r.total_average.toFixed(1)}</span> / 10
                {r.failure_count ? ` · Attempt ${r.failure_count}` : ''}
              </div>
            )}
          </div>
          {r && (
            <div style={{ marginLeft: 'auto', fontSize: 32, fontFamily: 'Syne, sans-serif', fontWeight: 800, color: scoreToColor(r.total_average) }}>
              {r.total_average.toFixed(1)}
            </div>
          )}
        </div>

        {r && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
            {Object.entries({ ...r.code_scores, ...r.model_scores }).map(([key, val]) => (
              <div key={key} style={{ padding: '4px 12px', borderRadius: 100, background: `${scoreToColor(val)}22`, border: `1px solid ${scoreToColor(val)}66`, color: scoreToColor(val), fontSize: 12, fontWeight: 600 }}>
                {key}: {val.toFixed(1)}
              </div>
            ))}
          </div>
        )}
      </div>

      {r?.loop_warning && (
        <div style={{ background: 'rgba(255,193,7,0.1)', border: '1px solid rgba(255,193,7,0.3)', borderRadius: 12, padding: 14, marginBottom: 16, color: '#FFC107', fontSize: 13 }}>
          ⚠ {r.loop_warning}
        </div>
      )}

      {phase === 'failed' && (
        <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 16, padding: 20, marginBottom: 20 }}>
          {advice && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>AI Advice</div>
              <p style={{ color: '#C0C0E8', fontSize: 14, lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap' }}>{advice}</p>
            </div>
          )}
          {r?.template_suggestions && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#FFC107', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>Try a Template</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {r.template_suggestions.map((t, i) => (
                  <button key={i} onClick={() => setModifyText(`Use this template concept: ${t.story}`)}
                    style={{ padding: '6px 14px', borderRadius: 100, border: '1px solid rgba(255,193,7,0.3)', background: 'rgba(255,193,7,0.08)', color: '#FFC107', fontSize: 12, cursor: 'pointer' }}>
                    {t.genre} — {t.mood}
                  </button>
                ))}
              </div>
            </div>
          )}
          <label style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>What to change?</label>
          <textarea value={modifyText} onChange={e => setModifyText(e.target.value)} rows={3}
            placeholder="Describe what to fix based on the advice above..."
            style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 8, padding: '10px 12px', color: '#F0F0FF', fontSize: 14, fontFamily: 'DM Sans, sans-serif', outline: 'none', resize: 'none', boxSizing: 'border-box' }}
          />
          {error && <div style={{ color: '#FF4D6D', fontSize: 12, marginTop: 8 }}>{error}</div>}
          <button onClick={handleRetry} disabled={!modifyText.trim() || modifying}
            style={{ marginTop: 12, padding: '9px 22px', borderRadius: 10, border: 'none', background: modifyText.trim() && !modifying ? 'linear-gradient(135deg,#6C63FF,#5A54E8)' : 'rgba(108,99,255,0.2)', color: modifyText.trim() && !modifying ? '#fff' : '#50508A', fontSize: 13, fontWeight: 600, cursor: modifyText.trim() && !modifying ? 'pointer' : 'not-allowed' }}>
            {modifying ? '⟳ Modifying & Re-evaluating...' : '↻ Modify & Re-evaluate'}
          </button>
        </div>
      )}

      {(phase === 'awaiting_human' || phase === 'human_failed') && (
        <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(34,212,160,0.2)', borderRadius: 16, padding: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#22D4A0', marginBottom: 4, fontFamily: 'Syne, sans-serif' }}>Human Evaluation</div>
          <p style={{ color: '#50508A', fontSize: 13, margin: '0 0 20px' }}>Check that the storyboard meets your creative vision</p>
          {humanFailed.length > 0 && (
            <div style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.2)', borderRadius: 8, padding: 12, marginBottom: 16, color: '#FF4D6D', fontSize: 13 }}>
              Failed: {humanFailed.join(', ')} — Modify the storyboard to address these before confirming
            </div>
          )}
          {[
            { state: H1, setter: setH1, label: 'H1: Fan Appeal', desc: 'Does this match fan expectations for the genre?' },
            { state: H2, setter: setH2, label: 'H2: Emotional Pacing', desc: 'Does the emotional flow feel natural?' },
            { state: H3, setter: setH3, label: 'H3: Input Faithfulness', desc: 'Does it reflect your original idea?' },
          ].map(({ state, setter, label, desc }) => (
            <label key={label} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', padding: '12px 0', borderBottom: '1px solid rgba(108,99,255,0.1)', cursor: 'pointer' }}>
              <input type="checkbox" checked={state} onChange={e => setter(e.target.checked)} style={{ marginTop: 2, width: 18, height: 18, cursor: 'pointer', accentColor: '#22D4A0' }} />
              <div>
                <div style={{ fontWeight: 600, color: '#F0F0FF', fontSize: 14 }}>{label}</div>
                <div style={{ color: '#50508A', fontSize: 12 }}>{desc}</div>
              </div>
            </label>
          ))}
          <div style={{ marginTop: 16 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>Feedback (optional)</label>
            <textarea value={humanFeedback} onChange={e => setHumanFeedback(e.target.value)} rows={2}
              placeholder="Any additional notes..."
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 8, padding: '10px 12px', color: '#F0F0FF', fontSize: 14, fontFamily: 'DM Sans, sans-serif', outline: 'none', resize: 'none', boxSizing: 'border-box' }}
            />
          </div>
          {error && <div style={{ color: '#FF4D6D', fontSize: 12, marginTop: 8 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <button onClick={() => navigate('/storyboard')}
              style={{ padding: '9px 18px', borderRadius: 10, border: '1px solid rgba(108,99,255,0.3)', background: 'transparent', color: '#A8A4FF', fontSize: 13, cursor: 'pointer' }}>
              ← Back to Storyboard
            </button>
            <button onClick={handleHumanEval} disabled={confirming}
              style={{ flex: 1, padding: '9px 18px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#22D4A0,#00E5FF)', color: '#080810', fontSize: 13, fontWeight: 700, cursor: confirming ? 'not-allowed' : 'pointer' }}>
              {confirming ? '⟳ Confirming...' : '✓ Confirm & Generate Images →'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
