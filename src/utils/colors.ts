// Цветовая схема по типам узлов
export const NODE_COLOR_HEX = {
  question: '#3b82f6',
  answer: '#10b981',
  fact: '#8b5cf6',
  opinion: '#f59e0b',
  solution: '#06b6d4',
  message: '#6b7280',
  default: '#9ca3af'
} as const

// Функция получения HEX цвета узла
export function getNodeColorHex(type: string): string {
  return NODE_COLOR_HEX[type as keyof typeof NODE_COLOR_HEX] || NODE_COLOR_HEX.default
}
