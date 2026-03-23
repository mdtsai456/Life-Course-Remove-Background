import ImageUploader from './components/ImageUploader'

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Remove Background</h1>
        <p>Upload a PNG, JPEG, or WebP image (max 10 MB) to remove its background.</p>
      </header>
      <main>
        <ImageUploader />
      </main>
    </div>
  )
}
