import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'
import { Component, createEffect, createSignal, onMount } from 'solid-js'
import styles from '~/styles/interview.module.css'

interface MessageEditorProps {
  content: string
  onContentChange: (content: string) => void
  onSave: () => void
  onCancel: () => void
}

export const MessageEditor: Component<MessageEditorProps> = (props) => {
  const [editorRef, setEditorRef] = createSignal<HTMLDivElement | undefined>(undefined)
  const [isFocused, setIsFocused] = createSignal(false)
  const [markdownContent, setMarkdownContent] = createSignal(props.content)
  const [isUpdating, setIsUpdating] = createSignal(false)

  // Конвертируем markdown в HTML для отображения
  const markdownToHtml = (markdown: string): string => {
    try {
      const rawHtml = marked.parse(markdown, { async: false }) as string
      const sanitizedHtml = DOMPurify.sanitize(rawHtml, {
        ADD_ATTR: ['target', 'rel']
      })
      return sanitizedHtml
    } catch (e) {
      console.error('Error parsing markdown:', e)
      return markdown
    }
  }

  // Конвертируем HTML обратно в markdown
  const htmlToMarkdown = (html: string): string => {
    const div = document.createElement('div')
    div.innerHTML = html
    return convertHtmlToMarkdown(div)
  }

  // Простая конвертация HTML элементов в markdown
  const convertHtmlToMarkdown = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || ''
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return ''
    }

    const element = node as Element
    const tagName = element.tagName.toLowerCase()
    const children = Array.from(element.childNodes)
      .map((child: Node) => convertHtmlToMarkdown(child))
      .join('')

    switch (tagName) {
      case 'p':
        return `${children}\n\n`
      case 'br':
        return '\n'
      case 'strong':
      case 'b':
        return `**${children}**`
      case 'em':
      case 'i':
        return `*${children}*`
      case 'u':
        return `<u>${children}</u>`
      case 'h1':
        return `# ${children}\n\n`
      case 'h2':
        return `## ${children}\n\n`
      case 'h3':
        return `### ${children}\n\n`
      case 'h4':
        return `#### ${children}\n\n`
      case 'h5':
        return `##### ${children}\n\n`
      case 'h6':
        return `###### ${children}\n\n`
      case 'ul':
        return `${children}\n`
      case 'ol':
        return `${children}\n`
      case 'li': {
        const parent = element.parentElement
        const isOrdered = parent?.tagName.toLowerCase() === 'ol'
        const prefix = isOrdered ? '1. ' : '- '
        return `${prefix}${children}\n`
      }
      case 'a': {
        const href = element.getAttribute('href') || ''
        return `[${children}](${href})`
      }
      case 'code':
        return `\`${children}\``
      case 'pre':
        return `\`\`\`\n${children}\n\`\`\`\n\n`
      case 'blockquote':
        return `> ${children}\n\n`
      case 'hr':
        return '---\n\n'
      default:
        return children
    }
  }

  // Обновляем HTML в редакторе при изменении markdown
  createEffect(() => {
    if (isUpdating() || !editorRef()) return

    const html = markdownToHtml(markdownContent())
    if (editorRef()?.innerHTML !== html) {
      setIsUpdating(true)
      const selection = window.getSelection()
      const range = selection?.rangeCount ? selection.getRangeAt(0) : null
      const cursorPosition = range && editorRef() ? saveCursorPosition(editorRef()!, range) : null

      if (editorRef()) {
        editorRef()!.innerHTML = html
      }

      if (cursorPosition && editorRef()) {
        restoreCursorPosition(editorRef()!, cursorPosition)
      }

      setIsUpdating(false)
    }
  })

  // Сохраняем позицию курсора
  const saveCursorPosition = (container: HTMLElement, range: Range) => {
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(container)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    return preCaretRange.toString().length
  }

  // Восстанавливаем позицию курсора
  const restoreCursorPosition = (container: HTMLElement, position: number) => {
    const range = document.createRange()
    const selection = window.getSelection()
    let charCount = 0
    const nodeStack: Node[] = [container]
    let node: Node | undefined
    let foundStart = false

    while (!foundStart && (node = nodeStack.pop())) {
      if (node.nodeType === Node.TEXT_NODE) {
        const nextCharCount = charCount + (node.textContent?.length || 0)
        if (position <= nextCharCount) {
          range.setStart(node, position - charCount)
          range.setEnd(node, position - charCount)
          foundStart = true
        }
        charCount = nextCharCount
      } else {
        const children = Array.from(node.childNodes)
        for (let i = children.length - 1; i >= 0; i--) {
          const child = children[i]
          if (child) {
            nodeStack.push(child)
          }
        }
      }
    }

    if (foundStart && selection) {
      selection.removeAllRanges()
      selection.addRange(range)
    }
  }

  onMount(() => {
    // Устанавливаем начальное содержимое
    if (editorRef()) {
      editorRef()!.innerHTML = markdownToHtml(props.content)
      setMarkdownContent(props.content)
      // Автофокус и установка курсора в конец
      editorRef()!.focus()
      const range = document.createRange()
      const selection = window.getSelection()
      if (selection && editorRef()!.childNodes.length > 0) {
        range.selectNodeContents(editorRef()!)
        range.collapse(false)
        selection.removeAllRanges()
        selection.addRange(range)
      }
    }
  })

  const handleInput = () => {
    if (isUpdating() || !editorRef()) return

    setIsUpdating(true)
    const html = editorRef()!.innerHTML
    const markdown = htmlToMarkdown(html)
    setMarkdownContent(markdown)
    props.onContentChange(markdown)
    setIsUpdating(false)
  }

  const handlePaste = (e: ClipboardEvent) => {
    e.preventDefault()
    const text = e.clipboardData?.getData('text/plain') || ''
    const html = e.clipboardData?.getData('text/html') || ''

    // Если есть HTML, конвертируем в markdown, иначе используем plain text
    if (html) {
      const tempDiv = document.createElement('div')
      tempDiv.innerHTML = html
      const markdown = htmlToMarkdown(tempDiv.innerHTML)
      // Вставляем markdown как текст
      document.execCommand('insertText', false, markdown)
    } else {
      document.execCommand('insertText', false, text)
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl/Cmd + Enter для сохранения
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSave()
      return
    }
    // Escape для отмены
    if (e.key === 'Escape') {
      e.preventDefault()
      props.onCancel()
      return
    }
    // Ctrl/Cmd + B для bold (markdown **text**)
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault()
      const selection = window.getSelection()
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0)
        if (!range.collapsed) {
          // Выделен текст - применяем форматирование
          document.execCommand('bold', false)
        } else {
          // Курсор без выделения - вставляем markdown синтаксис
          document.execCommand('insertText', false, '****')
          // Перемещаем курсор между звездочками
          const newRange = selection.getRangeAt(0)
          newRange.setStart(newRange.startContainer, newRange.startOffset - 2)
          newRange.collapse(true)
          selection.removeAllRanges()
          selection.addRange(newRange)
        }
      }
      return
    }
    // Ctrl/Cmd + I для italic (markdown *text*)
    if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
      e.preventDefault()
      const selection = window.getSelection()
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0)
        if (!range.collapsed) {
          document.execCommand('italic', false)
        } else {
          document.execCommand('insertText', false, '**')
          const newRange = selection.getRangeAt(0)
          newRange.setStart(newRange.startContainer, newRange.startOffset - 1)
          newRange.collapse(true)
          selection.removeAllRanges()
          selection.addRange(newRange)
        }
      }
      return
    }
    // Ctrl/Cmd + K для ссылки (markdown [text](url))
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      const selection = window.getSelection()
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0)
        const selectedText = range.toString() || 'текст'
        document.execCommand('insertText', false, `[${selectedText}](url)`)
        // Выделяем "url" для замены
        const newRange = selection.getRangeAt(0)
        const urlStart = newRange.startOffset - 4
        newRange.setStart(newRange.startContainer, urlStart)
        newRange.setEnd(newRange.startContainer, urlStart + 3)
        selection.removeAllRanges()
        selection.addRange(newRange)
      }
      return
    }
  }

  const handleFormat = (command: string, value?: string) => {
    document.execCommand(command, false, value)
    editorRef()!.focus()
    // Триггерим обновление markdown после форматирования
    setTimeout(() => {
      if (editorRef()) {
        const html = editorRef()!.innerHTML
        const markdown = htmlToMarkdown(html)
        setMarkdownContent(markdown)
        props.onContentChange(markdown)
      }
    }, 0)
  }

  const handleSave = () => {
    const markdown = markdownContent().trim()
    if (markdown) {
      props.onSave()
    }
  }

  return (
    <div class={styles.editContainer}>
      {/* Панель инструментов форматирования */}
      <div class={styles.editToolbar}>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('bold')}
          title="Жирный (Ctrl+B)"
        >
          <strong>B</strong>
        </button>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('italic')}
          title="Курсив (Ctrl+I)"
        >
          <em>I</em>
        </button>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('underline')}
          title="Подчеркнутый (Ctrl+U)"
        >
          <u>U</u>
        </button>
        <div class={styles.toolbarSeparator} />
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('formatBlock', '<p>')}
          title="Обычный текст"
        >
          P
        </button>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('formatBlock', '<h2>')}
          title="Заголовок 2"
        >
          H2
        </button>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('formatBlock', '<h3>')}
          title="Заголовок 3"
        >
          H3
        </button>
        <div class={styles.toolbarSeparator} />
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('insertUnorderedList')}
          title="Маркированный список"
        >
          •
        </button>
        <button
          type="button"
          class={styles.toolbarButton}
          onClick={() => handleFormat('insertOrderedList')}
          title="Нумерованный список"
        >
          1.
        </button>
      </div>

      {/* Редактор с contenteditable */}
      <div
        ref={setEditorRef}
        contentEditable={true}
        class={`${styles.editTextarea} ${styles.editContentEditable} ${isFocused() ? styles.focused : ''}`}
        onInput={handleInput}
        onPaste={handlePaste}
        onKeyDown={handleKeyDown}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        data-placeholder="Введите текст..."
      />

      <div class={styles.editActions}>
        <button
          class={styles.editButton}
          onClick={handleSave}
          title="Сохранить как новую ноду (Ctrl+Enter)"
        >
          Сохранить
        </button>
        <button class={styles.editButton} onClick={props.onCancel} title="Отменить редактирование (Esc)">
          Отмена
        </button>
      </div>
    </div>
  )
}
