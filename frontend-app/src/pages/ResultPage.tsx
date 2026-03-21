import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useProjectStore } from '../stores/project'

export function ResultPage() {
  const navigate = useNavigate()
  const { projectId, clipUrls, scenes, evalResult, reset } = useProjectStore()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentClip, setCurrentClip] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [downloaded, setDownloaded] = useState(false)

  const totalDuration = scenes.reduce((sum) => sum + 5, 0) // estimate

  function handleEnded() {
    if (currentClip < clipUrls.length - 1) {
      setCurrentClip(i => i + 1)
    } else {
      setPlaying(false)
    }
  }

  function handlePlayPause() {
    const v = videoRef.current
    if (!v) return
    if (playing) { v.pause(); setPlaying(false) }
    else { v.play(); setPlaying(true) }
  }

  function handleDownload() {
    if (!clipUrls[0]) return
    // MVP: download first clip
    const a = document.createElement('a')
    a.href = clipUrls[currentClip]
    a.download = `fanframe_cut_${currentClip + 1}`
    a.click()
    setDownloaded(true)
    setTimeout(() => setDownloaded(false), 3000)
  }

  function handleRegenerate() {
    reset()
    navigate('/')
  }

  if (!projectId || clipUrls.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: '#50508A' }}>
        No video result. <button onClick={() => navigate('/')} style={{ color: '#6C63FF', background: 'none', border: 'none', cursor: 'pointer' }}>Start over</button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 16px 80px' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <h2 style={{ fontFamily: 'Syne, sans-serif', fontSize: 28, fontWeight: 800, margin: 0, background: 'linear-gradient(135deg,#22D4A0,#00E5FF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Your Fan Video is Ready!
        </h2>
        <p style={{ color: '#50508A', marginTop: 8, fontSize: 14 }}>
          {clipUrls.length} clips generated — watch them individually or download
        </p>
      </div>

      {/* Video player */}
      <div style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(34,212,160,0.2)', borderRadius: 20, overflow: 'hidden', marginBottom: 24, boxShadow: '0 4px 40px rgba(34,212,160,0.1)' }}>
        <div style={{ position: 'relative', aspectRatio: '16/9', background: '#000' }}>
          <video
            ref={videoRef}
            src={clipUrls[currentClip]}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            onEnded={handleEnded}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
          {/* Play button overlay when paused */}
          {!playing && (
            <button onClick={handlePlayPause}
              style={{ position: 'absolute', inset: 0, background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(34,212,160,0.9)', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)' }}>
                <span style={{ fontSize: 24, color: '#080810', marginLeft: 4 }}>▶</span>
              </div>
            </button>
          )}
          {/* Clip indicator */}
          <div style={{ position: 'absolute', top: 12, right: 12, padding: '4px 10px', borderRadius: 100, background: 'rgba(8,8,16,0.8)', color: '#F0F0FF', fontSize: 12 }}>
            Cut {currentClip + 1} / {clipUrls.length}
          </div>
        </div>

        {/* Controls */}
        <div style={{ padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 12, borderTop: '1px solid rgba(108,99,255,0.1)' }}>
          <button onClick={() => setCurrentClip(i => Math.max(0, i - 1))} disabled={currentClip === 0}
            style={{ background: 'none', border: 'none', color: currentClip === 0 ? '#3A3A6A' : '#F0F0FF', fontSize: 18, cursor: currentClip === 0 ? 'not-allowed' : 'pointer' }}>⏮</button>
          <button onClick={handlePlayPause}
            style={{ background: 'rgba(34,212,160,0.15)', border: '1px solid rgba(34,212,160,0.3)', borderRadius: 8, color: '#22D4A0', fontSize: 18, padding: '4px 14px', cursor: 'pointer' }}>
            {playing ? '⏸' : '▶'}
          </button>
          <button onClick={() => setCurrentClip(i => Math.min(clipUrls.length - 1, i + 1))} disabled={currentClip === clipUrls.length - 1}
            style={{ background: 'none', border: 'none', color: currentClip === clipUrls.length - 1 ? '#3A3A6A' : '#F0F0FF', fontSize: 18, cursor: currentClip === clipUrls.length - 1 ? 'not-allowed' : 'pointer' }}>⏭</button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: '#50508A', fontFamily: 'JetBrains Mono, monospace' }}>
            {clipUrls.length} clips · ~{totalDuration}s
          </span>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 28 }}>
        <button onClick={handleDownload}
          style={{ flex: 1, padding: '12px', borderRadius: 12, border: 'none', background: downloaded ? 'rgba(34,212,160,0.2)' : 'linear-gradient(135deg,#22D4A0,#00E5FF)', color: downloaded ? '#22D4A0' : '#080810', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Syne, sans-serif' }}>
          {downloaded ? '✓ Downloaded!' : '⬇ Download Current Clip'}
        </button>
        <button onClick={handleRegenerate}
          style={{ padding: '12px 20px', borderRadius: 12, border: '1px solid rgba(108,99,255,0.3)', background: 'transparent', color: '#A8A4FF', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
          ↺ Regenerate
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
        {[
          { label: 'Scenes', value: `${clipUrls.length}/${scenes.length}` },
          { label: 'Eval Score', value: evalResult ? `${evalResult.total_average.toFixed(1)}/10` : '—' },
          { label: 'Status', value: 'Complete' },
          { label: 'Clips Ready', value: String(clipUrls.length) },
        ].map(s => (
          <div key={s.label} style={{ background: 'rgba(12,12,22,0.95)', border: '1px solid rgba(108,99,255,0.18)', borderRadius: 14, padding: '14px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#22D4A0', fontFamily: 'Syne, sans-serif' }}>{s.value}</div>
            <div style={{ fontSize: 11, color: '#50508A', marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Clip grid */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#6C63FF', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 12 }}>All Clips</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
          {clipUrls.map((_url, i) => (
            <button key={i} onClick={() => setCurrentClip(i)}
              style={{ background: 'transparent', border: `2px solid ${currentClip === i ? '#22D4A0' : 'rgba(108,99,255,0.2)'}`, borderRadius: 12, overflow: 'hidden', cursor: 'pointer', padding: 0 }}>
              <div style={{ height: 90, background: 'linear-gradient(135deg,rgba(34,212,160,0.15),rgba(0,229,255,0.08))', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {scenes[i]?.image_url
                  ? <img src={scenes[i].image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  : <span style={{ fontSize: 18, opacity: 0.4 }}>▶</span>
                }
                {currentClip === i && (
                  <div style={{ position: 'absolute', inset: 0, border: '2px solid #22D4A0', borderRadius: 10 }} />
                )}
              </div>
              <div style={{ padding: '6px 10px', textAlign: 'left' }}>
                <div style={{ fontSize: 11, color: '#22D4A0', fontFamily: 'JetBrains Mono, monospace' }}>Cut {i + 1}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
