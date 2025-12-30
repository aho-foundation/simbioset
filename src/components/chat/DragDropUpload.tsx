import { Component, createSignal } from 'solid-js'
import styles from '~/styles/DragDropUpload.module.css'

interface DragDropUploadProps {
  onFilesDrop: (files: File[]) => void
}

const DragDropUpload: Component<DragDropUploadProps> = (props) => {
  const [isDragging, setIsDragging] = createSignal(false)

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    if (e.dataTransfer?.files) {
      props.onFilesDrop(Array.from(e.dataTransfer.files))
    }
  }

  const handleFileInput = (e: Event) => {
    const target = e.target as HTMLInputElement
    if (target.files) {
      props.onFilesDrop(Array.from(target.files))
    }
  }

  return (
    <div
      class={`${styles.dragDropArea} ${isDragging() ? styles.dragging : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div class={styles.dragDropContent}>
        <svg
          class="w-12 h-12 mx-auto mb-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p>Перетащите файлы сюда или нажмите для выбора</p>
        <input type="file" class={styles.fileInput} multiple onChange={handleFileInput} />
      </div>
    </div>
  )
}

export default DragDropUpload
