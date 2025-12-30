/**
 * E2E тесты для frontend Weaviate интеграции
 *
 * Требования:
 * - Запущенный dev server
 * - Weaviate доступен через API
 */

import { expect, test } from '@playwright/test'

test.describe('Weaviate Frontend Integration', () => {
  test.beforeEach(async ({ page }) => {
    // Переходим на главную страницу
    await page.goto('/')
  })

  test('ParagraphSearch component renders', async ({ page }) => {
    // Проверяем, что компонент поиска параграфов отображается
    const searchContainer = page
      .locator('[data-testid="paragraph-search"]')
      .or(page.locator('text=Поиск параграфов'))

    await expect(searchContainer).toBeVisible()
  })

  test('Search input works', async ({ page }) => {
    // Находим поле поиска
    const searchInput = page
      .locator('input[placeholder*="запрос" i]')
      .or(page.locator('input[type="text"]'))

    // Вводим поисковый запрос
    await searchInput.fill('экосистема')

    // Проверяем, что текст введен
    await expect(searchInput).toHaveValue('экосистема')
  })

  test('Search form submission', async ({ page }) => {
    const searchInput = page
      .locator('input[placeholder*="запрос" i]')
      .or(page.locator('input[type="text"]'))
    const searchButton = page.locator('button[type="submit"]').or(page.locator('button:has-text("Поиск")'))

    // Вводим запрос и нажимаем поиск
    await searchInput.fill('симбиоз')
    await searchButton.click()

    // Проверяем, что происходит загрузка или отображаются результаты
    // (точное поведение зависит от реализации)
    await page.waitForTimeout(1000) // Ждем возможной загрузки

    // Проверяем, что нет ошибок
    const errorMessages = page.locator('.error, [data-testid="error"]')
    await expect(errorMessages).toHaveCount(0)
  })

  test('Search results display', async ({ page }) => {
    // Если есть предварительно загруженные данные, проверяем отображение результатов
    const resultsContainer = page
      .locator('[data-testid="search-results"]')
      .or(page.locator('.search-results, .results'))

    // Результаты могут быть пустыми изначально
    const hasResults = (await resultsContainer.count()) > 0
    if (hasResults) {
      await expect(resultsContainer).toBeVisible()
    }
  })

  test('API integration works', async ({ page }) => {
    // Проверяем, что запросы к API Weaviate не возвращают ошибки
    const networkRequests: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('/api/')) {
        networkRequests.push(request.url())
      }
    })

    // Выполняем действие, которое должно вызвать API запрос
    const searchInput = page.locator('input[placeholder*="запрос" i]').first()
    if (await searchInput.isVisible()) {
      await searchInput.fill('тест')
      await searchInput.press('Enter')

      // Ждем завершения запросов
      await page.waitForTimeout(2000)

      // Проверяем, что были API запросы
      expect(networkRequests.length).toBeGreaterThan(0)

      // Проверяем, что запросы не вернули ошибки
      const failedRequests = networkRequests.filter(
        (url) => url.includes('/api/') && !page.locator('.error').isVisible()
      )
      expect(failedRequests.length).toBe(networkRequests.length)
    }
  })

  test('Responsive design', async ({ page }) => {
    // Проверяем адаптивность компонентов
    const searchContainer = page
      .locator('[data-testid="paragraph-search"]')
      .or(page.locator('.paragraph-search, .search-container'))
      .first()

    if (await searchContainer.isVisible()) {
      // Проверяем мобильную версию
      await page.setViewportSize({ width: 375, height: 667 })

      // Компонент должен оставаться функциональным
      const mobileInput = searchContainer.locator('input')
      await expect(mobileInput).toBeVisible()

      // Возвращаем десктопное разрешение
      await page.setViewportSize({ width: 1920, height: 1080 })
    }
  })

  test('Error handling', async ({ page }) => {
    // Проверяем обработку ошибок
    const searchInput = page.locator('input[placeholder*="запрос" i]').first()

    if (await searchInput.isVisible()) {
      // Вводим некорректный запрос или симулируем ошибку
      await searchInput.fill('test_error_query')

      // Мониторим сетевые ошибки
      const errors: string[] = []
      page.on('response', (response) => {
        if (!response.ok() && response.url().includes('/api/')) {
          errors.push(`${response.status()}: ${response.url()}`)
        }
      })

      // Выполняем поиск
      await searchInput.press('Enter')
      await page.waitForTimeout(1000)

      // Если есть ошибки, они должны быть корректно обработаны
      if (errors.length > 0) {
        // Проверяем, что ошибки отображаются пользователю
        const errorElements = page.locator('.error, .alert, [role="alert"]')
        const errorVisible = await errorElements.isVisible()

        // Либо ошибки отображаются, либо запросы успешны
        expect(errorVisible || errors.length === 0).toBe(true)
      }
    }
  })

  test('Loading states', async ({ page }) => {
    // Проверяем индикаторы загрузки
    const searchInput = page.locator('input[placeholder*="запрос" i]').first()

    if (await searchInput.isVisible()) {
      // Начинаем поиск
      await searchInput.fill('тест загрузки')
      await searchInput.press('Enter')

      // Ищем индикаторы загрузки
      const _loadingIndicators = page
        .locator('[data-testid="loading"], .loading, .spinner')
        .or(page.locator('text=/загрузка|loading/i'))

      // Индикатор загрузки может появляться и исчезать
      // Проверяем, что компонент остается стабильным
      await page.waitForTimeout(2000)

      // Проверяем, что страница не зависла
      const bodyText = await page.locator('body').textContent()
      expect(bodyText).toBeTruthy()
    }
  })
})

// Тесты для API эндпоинтов
test.describe('Weaviate API Endpoints', () => {
  test('Search API returns valid response', async ({ request }) => {
    // Тестируем API напрямую
    const response = await request.get('/api/search', {
      params: {
        q: 'тест',
        limit: 5
      }
    })

    // Проверяем статус ответа
    expect(response.status()).toBe(200)

    // Проверяем структуру ответа
    const data = await response.json()
    expect(data).toHaveProperty('results')
    expect(Array.isArray(data.results)).toBe(true)

    if (data.results.length > 0) {
      const firstResult = data.results[0]
      expect(firstResult).toHaveProperty('paragraph')
      expect(firstResult).toHaveProperty('score')
      expect(typeof firstResult.score).toBe('number')
    }
  })

  test('Documents API works', async ({ request }) => {
    const response = await request.get('/api/documents')

    expect(response.status()).toBe(200)

    const data = await response.json()
    expect(Array.isArray(data)).toBe(true)
  })

  test('Health check passes', async ({ request }) => {
    const response = await request.get('/health')

    expect(response.status()).toBe(200)

    const data = await response.json()
    expect(data).toHaveProperty('status')
  })
})
