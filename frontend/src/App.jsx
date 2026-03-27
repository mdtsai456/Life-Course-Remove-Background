import { useState } from 'react'
import ImageUploader from './components/ImageUploader'
import VoiceCloner from './components/VoiceCloner'
import ImageTo3D from './components/ImageTo3D'

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
          <button
            className={`nav-tab${activeTab === 'image-to-3d' ? ' active' : ''}`}
            onClick={() => setActiveTab('image-to-3d')}
          >
            Image to 3D
          </button>
        </nav>
      </header>
      <main>
        <div style={{ display: activeTab === 'remove-bg' ? 'block' : 'none' }}>
          <ImageUploader visible={activeTab === 'remove-bg'} />
        </div>
        <div style={{ display: activeTab === 'voice-clone' ? 'block' : 'none' }}>
          <VoiceCloner visible={activeTab === 'voice-clone'} />
        </div>
        <div style={{ display: activeTab === 'image-to-3d' ? 'block' : 'none' }}>
          <ImageTo3D visible={activeTab === 'image-to-3d'} />
        </div>
      </main>
    </div>
  )
}
