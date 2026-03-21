import { useState } from 'react'
import { useNavigate } from 'react-router'
import { modifyPlot } from '../api/plot'
import { useProjectStore } from '../stores/project'
import { parseScenes } from '../lib/utils'

export function StoryboardPage() {
  const navigate = useNavigate()
  const { projectId, plainText, setPlainText, setStep } = useProjectStore()
  const [modifyText, setModifyText] = useState('')
  const [modifying, setModifying] = useState(false)
  const [showModify, setShowModify] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!projectId || !plainText) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: '#50508A' }}>
        No project found. <button onClick={() => navigate('/')} style={{ color: '#6C63FF', background: 'none', border: 'none', cursor: 'pointer' }}>Start over</button>
      </div>
    )
  }

  const scenes = parseScenes(plainText)

  async function handleModify() {
    if (!modifyText.trim() || !projectId) return
    setModifying(true)
    setError(null)
    try {
      const res = await modifyPlot({ project_id: projectId, modification_request: modifyText })
      setPlainText(res.plain_text)
      setModifyText('')
      setShowModify(false)
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? 'Failed to modify storyboard')
    } finally {
      setModifying(false)
    }
  }

  function handleEvaluate() {
    setStep(3)
    navigate('/evaluate')
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px 80px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 24, fontWeight: 700, margin: 0, color: '#F0F0FF' }}>
            Your Storyboard
          </h2>
          <p style={{ color: '#50508A', margin: '4px 0 0', fontSize: 14 }}>
            {scenes.length} cuts generated — review and modify before evaluation
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => setShowModify(s => !s)}
            style={{ padding: '9px 18px', borderRadius: 10, border: '1px solid rgba(108,99,255,0.4)', background: 'transparent', color: '#A8A4FF', fontSize: 13, cursor: 'pointer' }}>
            ✎ Modify
          </button>
          <button onClick={handleEvaluate}
            style={{ padding: '9px 18px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#6C63FF,#5A54E8)', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', boxShadow: '0 4px 16px rgba(108,99,255,0.3)' }}>
            Evaluate →
          </button>
        </div>
      </div>

      {/* Modify panel */}
      {showModify && (
        <div style={{ background: 'rgba(108,99,255,0.08)', border: '1px solid rgba(108,99,255,0.25)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
            Modification Request
          </label>
          <textarea
            value={modifyText}
            onChange={e => setModifyText(e.target.value)}
            rows={3}
            placeholder="e.g. Add more emotional moments in the middle, make the ending more epic..."
            style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 8, padding: '10px 12px', color: '#F0F0FF', fontSize: 14, fontFamily: 'DM Sans, sans-serif', outline: 'none', resize: 'none', boxSizing: 'border-box' }}
          />
          {error && <div style={{ color: '#FF4D6D', fontSize: 12, marginTop: 8 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button onClick={handleModify} disabled={!modifyText.trim() || modifying}
              style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: modifyText.trim() && !modifying ? '#6C63FF' : 'rgba(108,99,255,0.2)', color: modifyText.trim() && !modifying ? '#fff' : '#50508A', fontSize: 13, fontWeight: 600, cursor: modifyText.trim() && !modifying ? 'pointer' : 'not-allowed' }}>
              {modifying ? '⟳ Modifying...' : 'Apply Changes'}
            </button>
            <button onClick={() => setShowModify(false)}
              style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(108,99,255,0.2)', background: 'transparent', color: '#50508A', fontSize: 13, cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Scene cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
        {scenes.map(sc => (
          <div key={sc.cut} style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 16, overflow: 'hidden' }}>
            {/* Thumbnail placeholder */}
            <div style={{ height: 120, background: 'linear-gradient(135deg, rgba(108,99,255,0.2), rgba(0,229,255,0.1))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: '#6C63FF', opacity: 0.6 }}>CUT {sc.cut}</span>
            </div>
            <div style={{ padding: 14 }}>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#6C63FF', marginBottom: 8 }}>
                [Cut {sc.cut}]
              </div>
              {sc.lines.slice(0, 4).map((line, i) => (
                <p key={i} style={{ margin: '3px 0', fontSize: 12, color: line.startsWith('-') || line.includes(':') ? '#A8A4FF' : '#8080A8', lineHeight: 1.5 }}>
                  {line}
                </p>
              ))}
              {sc.lines.length > 4 && (
                <p style={{ margin: '6px 0 0', fontSize: 11, color: '#50508A' }}>+{sc.lines.length - 4} more lines</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Raw text toggle */}
      <details style={{ marginTop: 24 }}>
        <summary style={{ cursor: 'pointer', color: '#50508A', fontSize: 13, padding: '8px 0' }}>View raw storyboard text</summary>
        <pre style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.15)', borderRadius: 12, padding: 20, fontSize: 12, color: '#A8A4FF', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap', marginTop: 8 }}>
          {plainText}
        </pre>
      </details>
    </div>
  )
}
