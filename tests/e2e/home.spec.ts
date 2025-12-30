import { expect, test } from '@playwright/test'

test.describe('Home Page', () => {
  test('should load home page and display main content', async ({ page }) => {
    // Navigate to home page
    await page.goto('/')

    // Check that the page title contains "Симбиосеть"
    await expect(page.locator('h1')).toContainText('Симбиосеть')

    // Check that the subtitle is present
    await expect(page.locator('._heroSubtitle_nhpad_40')).toContainText('Улучшаем качества биосферы')

    // Check that navigation links are present
    await expect(page.locator('a[href="/sources"]')).toBeVisible()
    await expect(page.locator('a[href="/knowledge"]')).toBeVisible()
    await expect(page.locator('a[href="/funds"]')).toBeVisible()

    // Check that features section is present
    await expect(page.locator('text=Агрегация открытых данных')).toBeVisible()
    await expect(page.locator('text=Визуализация данных')).toBeVisible()
    await expect(page.locator('text=Дерево знаний')).toBeVisible()
  })

  test('should navigate to knowledge page', async ({ page }) => {
    await page.goto('/knowledge')
    await expect(page).toHaveURL(/.*knowledge/)
  })

  test('should navigate to funding page', async ({ page }) => {
    await page.goto('/funds')
    await expect(page).toHaveURL(/.*funds/)
  })
})
