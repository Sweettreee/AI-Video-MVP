import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router'
import './index.css'
import App from './App'
import { PromptPage } from './pages/PromptPage'
import { StoryboardPage } from './pages/StoryboardPage'
import { EvaluatePage } from './pages/EvaluatePage'
import { ImagesPage } from './pages/ImagesPage'
import { GeneratingPage } from './pages/GeneratingPage'
import { ResultPage } from './pages/ResultPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<PromptPage />} />
          <Route path="storyboard" element={<StoryboardPage />} />
          <Route path="evaluate" element={<EvaluatePage />} />
          <Route path="images" element={<ImagesPage />} />
          <Route path="generating" element={<GeneratingPage />} />
          <Route path="result" element={<ResultPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
