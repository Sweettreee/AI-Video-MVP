import { STEPS } from '../../lib/constants'

interface Props { currentStep: number }

export function StepBar({ currentStep }: Props) {
  return (
    <div className="flex items-center justify-center gap-0 py-4">
      {STEPS.map((s, i) => {
        const done = currentStep > s.id
        const active = currentStep === s.id
        return (
          <div key={s.id} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: done ? '#22D4A0' : active ? '#6C63FF' : 'rgba(108,99,255,0.15)',
                border: `2px solid ${done ? '#22D4A0' : active ? '#6C63FF' : 'rgba(108,99,255,0.25)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700, color: done || active ? '#fff' : '#50508A',
                boxShadow: active ? '0 0 12px rgba(108,99,255,0.5)' : undefined,
                transition: 'all 0.3s',
              }}>
                {done ? '✓' : s.id}
              </div>
              <span style={{ fontSize: 10, color: active ? '#F0F0FF' : done ? '#22D4A0' : '#50508A', fontWeight: active ? 600 : 400 }}>
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ width: 40, height: 2, background: currentStep > s.id ? '#22D4A0' : 'rgba(108,99,255,0.2)', transition: 'background 0.3s', marginBottom: 14 }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
