import { createSignal } from 'solid-js'
import { useKnowledgeBase } from '~/contexts/KnowledgeBaseContext'

export const TestSelection = () => {
  const kb = useKnowledgeBase()
  const [testResult, setTestResult] = createSignal<string>('')

  const testSetNodeSelected = async () => {
    try {
      // Попробуем вызвать функцию - если она не определена, получим ошибку
      console.log('Testing setNodeSelected function...')
      console.log('kb.setNodeSelected:', typeof kb.setNodeSelected)

      if (typeof kb.setNodeSelected === 'function') {
        setTestResult('✅ Функция setNodeSelected доступна')
      } else {
        setTestResult('❌ Функция setNodeSelected не является функцией')
      }
    } catch (error) {
      setTestResult(`❌ Ошибка: ${error}`)
    }
  }

  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', margin: '20px' }}>
      <h3>Тест функций выбора</h3>
      <button onClick={testSetNodeSelected}>Протестировать setNodeSelected</button>
      <p>{testResult()}</p>
    </div>
  )
}
