import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'
import { createEffect, createSignal, onMount } from 'solid-js'

interface MarkdownRendererProps {
  content: string
  onTextSelection?: (selectedText: string) => void
  messageId?: string | number
}

const MarkdownRenderer = (props: MarkdownRendererProps) => {
  const [htmlContent, setHtmlContent] = createSignal('')
  const [containerRef, setContainerRef] = createSignal<HTMLDivElement | null>(null)

  createEffect(() => {
    // Удаляем раздел "## Источники" из markdown перед парсингом
    // Это предотвращает дублирование источников (они показываются отдельным блоком)
    let contentToRender = props.content
    // Удаляем раздел источников в разных вариантах (заголовок + список)
    // Паттерн: заголовок "## Источники" + все до следующего заголовка или конца текста
    contentToRender = contentToRender.replace(
      /(^|\n)##+\s*Источники:?\s*\n[\s\S]*?(?=\n##+|\n###+|Z)/gi,
      ''
    )
    // Удаляем лишние пустые строки
    contentToRender = contentToRender.trim()

    const rawHtml = marked.parse(contentToRender, { async: false }) as string

    // Дополнительная очистка: удаляем заголовки "Источники" и списки из HTML (на случай если они проскочили)
    // Удаляем заголовок "Источники" и следующий за ним список
    const htmlWithoutSources = rawHtml
      .replace(/<h[2-6][^>]*>.*?Источники:?.*?<\/h[2-6]>\s*<ul[^>]*>[\s\S]*?<\/ul>/gi, '')
      .replace(
        // Удаляем оставшиеся заголовки "Источники" без списков
        /<h[2-6][^>]*>.*?Источники:?.*?<\/h[2-6]>/gi,
        ''
      )

    // Добавляем target="_blank" и rel="noopener noreferrer" ко всем ссылкам
    // Обрабатываем случаи, когда ссылка уже может иметь атрибуты target или rel
    const htmlWithTargets = htmlWithoutSources.replace(/<a\s+([^>]*?)>/gi, (_match, attributes) => {
      // Проверяем, есть ли уже target или rel
      const hasTarget = /target\s*=/i.test(attributes)
      const hasRel = /rel\s*=/i.test(attributes)

      let newAttributes = attributes.trim()

      // Добавляем target="_blank" если его нет
      if (!hasTarget) {
        newAttributes += ' target="_blank"'
      } else {
        // Заменяем существующий target на _blank
        newAttributes = newAttributes.replace(/target\s*=\s*["'][^"']*["']/i, 'target="_blank"')
      }

      // Добавляем rel="noopener noreferrer" если его нет
      if (!hasRel) {
        newAttributes += ' rel="noopener noreferrer"'
      } else {
        // Добавляем noopener noreferrer к существующему rel, если их там нет
        const relMatch = newAttributes.match(/rel\s*=\s*["']([^"']*)["']/i)
        if (relMatch) {
          const existingRel = relMatch[1]
          if (!existingRel.includes('noopener')) {
            newAttributes = newAttributes.replace(
              /rel\s*=\s*["']([^"']*)["']/i,
              `rel="${existingRel} noopener noreferrer"`
            )
          }
        }
      }

      return `<a ${newAttributes}>`
    })

    // Настраиваем DOMPurify для разрешения атрибутов target и rel
    const sanitizedHtml = DOMPurify.sanitize(htmlWithTargets, {
      ADD_ATTR: ['target', 'rel']
    })
    setHtmlContent(sanitizedHtml)
  })

  // Обработчик выделения текста
  const handleSelection = () => {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const selectedText = selection.toString().trim()
      if (selectedText && props.onTextSelection) {
        props.onTextSelection(selectedText)
      }
    }
  }

  // Обработчик двойного клика для быстрого выделения слова/фразы
  const handleDoubleClick = (e: MouseEvent) => {
    // Даем браузеру выделить слово, затем вызываем обработчик
    setTimeout(handleSelection, 10)
  }

  onMount(() => {
    const container = containerRef()
    if (container) {
      // Добавляем обработчики выделения текста
      container.addEventListener('mouseup', handleSelection)
      container.addEventListener('dblclick', handleDoubleClick)

      // Обработка клавиш для выделения (Ctrl+A, etc.)
      container.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
          setTimeout(handleSelection, 10)
        }
      })
    }
  })

  return (
    <div
      ref={setContainerRef}
      innerHTML={htmlContent()}
      class="markdown-content"
      style="user-select: text; cursor: text;"
    />
  )
}

export default MarkdownRenderer
