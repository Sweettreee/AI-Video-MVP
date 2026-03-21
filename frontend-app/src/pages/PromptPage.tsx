import { useState } from 'react'
import { useNavigate } from 'react-router'
import { generatePlot } from '../api/plot'
import { useProjectStore } from '../stores/project'
import { EXAMPLE_PROMPTS } from '../lib/constants'
import type { PlotRequest } from '../types/api'

const FIELDS: Array<{ key: keyof PlotRequest; label: string; placeholder: string }> = [
  { key: 'genre', label: 'Genre', placeholder: 'kpop, anime, game...' },
  { key: 'character', label: 'Character', placeholder: 'Silver-haired idol, stage outfit...' },
  { key: 'mood', label: 'Mood', placeholder: 'Dramatic, emotional, rainy night...' },
  { key: 'must_have', label: 'Must-have (optional)', placeholder: 'Rain scene, rooftop...' },
]

export function PromptPage() {
  const navigate = useNavigate()
  const { setProjectId, setFormData, setPlainText, setStep } = useProjectStore()

  const [form, setForm] = useState<PlotRequest>({ genre: '', character: '', mood: '', story: '', must_have: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const filled = [form.genre, form.character, form.mood, form.story].filter(Boolean).length
  const canSubmit = filled === 4 && !loading

  function setField(key: keyof PlotRequest, val: string) {
    setForm(f => ({ ...f, [key]: val }))
  }

  function loadExample(ex: typeof EXAMPLE_PROMPTS[0]) {
    setForm({ genre: ex.genre, character: ex.character, mood: ex.mood, story: ex.story, must_have: '' })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    try {
      const res = await generatePlot(form)
      setProjectId(res.project_id)
      setFormData(form)
      setPlainText(res.plain_text)
      setStep(2)
      navigate('/storyboard')
    } catch (err: unknown) {
      const e = err as Error & { detail?: string }
      setError(e.detail ?? e.message ?? 'Failed to generate storyboard')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 16px 80px' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 36, fontWeight: 800, margin: 0, background: 'linear-gradient(135deg,#6C63FF,#00E5FF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Create Your Fan Story
        </h1>
        <p style={{ color: '#50508A', marginTop: 8, fontSize: 15 }}>
          Describe your idea and AI will generate a storyboard for your fan video
        </p>
      </div>

      {/* Example chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 24 }}>
        {EXAMPLE_PROMPTS.map(ex => (
          <button key={ex.label} onClick={() => loadExample(ex)}
            style={{ padding: '6px 14px', borderRadius: 100, border: '1px solid rgba(108,99,255,0.3)', background: 'rgba(108,99,255,0.1)', color: '#A8A4FF', fontSize: 12, cursor: 'pointer', fontFamily: 'DM Sans, sans-serif' }}>
            ✦ {ex.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20 }}>
        {/* Form card */}
        <form onSubmit={handleSubmit}>
          <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 20, padding: 28 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              {FIELDS.map(f => (
                <div key={f.key}>
                  <label style={{ fontSize: 11, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.08em', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                    {f.label}
                  </label>
                  <input
                    value={(form[f.key] as string) ?? ''}
                    onChange={e => setField(f.key, e.target.value)}
                    placeholder={f.placeholder}
                    style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 10, padding: '10px 12px', color: '#F0F0FF', fontSize: 14, fontFamily: 'DM Sans, sans-serif', outline: 'none', boxSizing: 'border-box' }}
                  />
                </div>
              ))}
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <label style={{ fontSize: 11, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  Story *
                </label>
                <span style={{ fontSize: 11, color: '#50508A' }}>{form.story.length}/500</span>
              </div>
              <textarea
                value={form.story}
                onChange={e => setField('story', e.target.value)}
                maxLength={500}
                rows={4}
                placeholder="Describe your story concept, key scenes, emotional arc..."
                style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 10, padding: '10px 12px', color: '#F0F0FF', fontSize: 14, fontFamily: 'DM Sans, sans-serif', outline: 'none', resize: 'none', boxSizing: 'border-box' }}
              />
            </div>

            {error && (
              <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(255,77,109,0.1)', border: '1px solid rgba(255,77,109,0.3)', borderRadius: 8, color: '#FF4D6D', fontSize: 13 }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={!canSubmit}
              style={{
                marginTop: 20, width: '100%', padding: '13px', borderRadius: 12, border: 'none',
                background: canSubmit ? 'linear-gradient(135deg,#6C63FF,#5A54E8)' : 'rgba(108,99,255,0.2)',
                color: canSubmit ? '#fff' : '#50508A', fontSize: 15, fontWeight: 600,
                cursor: canSubmit ? 'pointer' : 'not-allowed', fontFamily: 'Syne, sans-serif',
                boxShadow: canSubmit ? '0 4px 24px rgba(108,99,255,0.3)' : undefined,
                transition: 'all 0.2s',
              }}>
              {loading ? '⟳ Generating Storyboard...' : '✦ Generate Storyboard'}
            </button>
          </div>
        </form>

        {/* Coach panel */}
        <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 20, padding: 24, height: 'fit-content' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', marginBottom: 16, letterSpacing: '0.06em', textTransform: 'uppercase' }}>Prompt Coach</div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: '#50508A' }}>Completeness</span>
              <span style={{ fontSize: 12, color: filled === 4 ? '#22D4A0' : '#FFC107', fontWeight: 600 }}>{filled}/4</span>
            </div>
            <div style={{ height: 4, background: 'rgba(108,99,255,0.15)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${(filled / 4) * 100}%`, background: filled === 4 ? '#22D4A0' : 'linear-gradient(90deg,#6C63FF,#00E5FF)', borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
          </div>
          {[
            { key: 'genre', label: 'Genre', hint: 'Be specific: kpop, anime, game' },
            { key: 'character', label: 'Character', hint: 'Appearance, outfit, name' },
            { key: 'mood', label: 'Mood', hint: 'Emotions, atmosphere' },
            { key: 'story', label: 'Story', hint: 'Plot arc, key scenes' },
          ].map(f => (
            <div key={f.key} style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'flex-start' }}>
              <div style={{ width: 16, height: 16, borderRadius: '50%', background: (form[f.key as keyof PlotRequest] as string) ? '#22D4A0' : 'rgba(108,99,255,0.2)', flexShrink: 0, marginTop: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>
                {(form[f.key as keyof PlotRequest] as string) ? '✓' : ''}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#F0F0FF' }}>{f.label}</div>
                <div style={{ fontSize: 11, color: '#50508A' }}>{f.hint}</div>
              </div>
            </div>
          ))}
          <div style={{ marginTop: 16, fontSize: 11, color: '#50508A', lineHeight: 1.6 }}>
            Tip: The more specific your character description, the better character consistency across all scenes.
          </div>
        </div>
      </div>
    </div>
  )
}
