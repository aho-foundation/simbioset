import { createSignal, Show } from 'solid-js'
import './ConceptDropZone.css'

export function ConceptDropZone() {
  const [isDragging, setIsDragging] = createSignal(false)
  const [isProcessing, setIsProcessing] = createSignal(false)
  const [message, setMessage] = createSignal('')

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = e.dataTransfer?.files
    if (!files || files.length === 0) return

    setIsProcessing(true)
    setMessage('Processing file...')

    try {
      const file = files[0]

      // Upload file to server - it will parse, vectorize, and save
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/chat/upload-file', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`)
      }

      const result = await response.json()

      setMessage(`✓ Added "${file.name}" to concept tree (${result.paragraph_count} paragraphs)`)
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      console.error('Error uploading file:', error)
      setMessage('⚠️ Error processing file')
      setTimeout(() => setMessage(''), 3000)
    }

    setIsProcessing(false)
  }

  return (
    <div
      class={`concept-drop-zone ${isDragging() ? 'dragging' : ''} ${isProcessing() ? 'processing' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div class="drop-content">
        <Show
          when={!isProcessing()}
          fallback={
            <div class="processing-indicator">
              <div class="spinner" />
              <p>Processing...</p>
            </div>
          }
        >
          <div class="drop-icon">📁</div>
          <h2>Drop files here to create concepts</h2>
          <p>Drag and drop files to add them to your concept tree</p>
        </Show>
      </div>

      <Show when={message()}>
        <div class="drop-message">{message()}</div>
      </Show>
    </div>
  )
}
