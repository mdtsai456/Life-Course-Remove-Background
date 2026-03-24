import { useState } from 'react'
import ImageUploader from './components/ImageUploader'
import VoiceCloner from './components/VoiceCloner'

export default function App() {
  const [activeTab, setActiveTab] = useState('remove-bg')

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI 工具箱</h1>
        <nav className="nav-tabs">
          <button
            className={`nav-tab${activeTab === 'remove-bg' ? ' active' : ''}`}
            onClick={() => setActiveTab('remove-bg')}
          >
            Remove Background
          </button>
          <button
            className={`nav-tab${activeTab === 'voice-clone' ? ' active' : ''}`}
            onClick={() => setActiveTab('voice-clone')}
          >
            Voice Clone
          </button>
        </nav>
      </header>
      <main>
        {activeTab === 'remove-bg' && <ImageUploader />}
        {activeTab === 'voice-clone' && <VoiceCloner />}
      </main>
    </div>
  )
}
