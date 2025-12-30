import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'
import { createEffect, createSignal } from 'solid-js'

interface MarkdownRendererProps {
  content: string
}

const MarkdownRenderer = (props: MarkdownRendererProps) => {
  const [htmlContent, setHtmlContent] = createSignal('')

  createEffect(() => {
    const rawHtml = marked.parse(props.content, { async: false }) as string

    // Добавляем target="_blank" и rel="noopener noreferrer" ко всем ссылкам
    // Обрабатываем случаи, когда ссылка уже может иметь атрибуты target или rel
    const htmlWithTargets = rawHtml.replace(/<a\s+([^>]*?)>/gi, (_match, attributes) => {
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

  return <div innerHTML={htmlContent()} />
}

export default MarkdownRenderer
