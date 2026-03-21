import { Outlet, useLocation } from 'react-router'
import { useEffect } from 'react'
import { Navbar } from './components/layout/Navbar'
import { StepBar } from './components/layout/StepBar'
import { BloomBg } from './components/layout/BloomBg'
import { useProjectStore } from './stores/project'

const ROUTE_STEPS: Record<string, number> = {
  '/': 1,
  '/storyboard': 2,
  '/evaluate': 3,
  '/images': 4,
  '/generating': 5,
  '/result': 6,
}

export default function App() {
  const { currentStep, setStep } = useProjectStore()
  const location = useLocation()

  useEffect(() => {
    const step = ROUTE_STEPS[location.pathname]
    if (step) setStep(step)
  }, [location.pathname])

  return (
    <div style={{ minHeight: '100vh', background: '#080810', position: 'relative' }}>
      <BloomBg />
      <Navbar />
      <div style={{ position: 'relative', zIndex: 1, paddingTop: 56 }}>
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '0 16px' }}>
          <StepBar currentStep={currentStep} />
        </div>
        <Outlet />
      </div>
    </div>
  )
}
