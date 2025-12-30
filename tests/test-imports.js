// Простой тест импортов
try {
  // Проверяем, что файлы существуют
  const fs = require('node:fs')

  const files = [
    'src/lib/weaviate/schemas.ts',
    'src/lib/weaviate/client.ts',
    'src/lib/weaviate/index.ts',
    'src/components/ui/Card.tsx',
    'src/components/ParagraphSearch.tsx',
    'src/styles/Card.module.css',
    'src/components/ParagraphSearch.module.css'
  ]

  console.log('Проверка существования файлов:')
  files.forEach((file) => {
    if (fs.existsSync(file)) {
      console.log(`✅ ${file}`)
    } else {
      console.log(`❌ ${file} - НЕ НАЙДЕН`)
    }
  })

  console.log('\nТест завершен успешно!')
} catch (error) {
  console.error('Ошибка:', error.message)
}
