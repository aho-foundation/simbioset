import { expect, test } from '@playwright/test'

test.describe('Router Navigation', () => {
  test('should navigate to sources page', async ({ page }) => {
    await page.goto('/sources')

    // Check URL and that page loads (lazy loaded component)
    await expect(page).toHaveURL(/.*sources/)
    await page.waitForTimeout(1000) // Wait for lazy component to load
    // Check that page loaded without errors (basic smoke test)
    await expect(page.locator('body')).toBeVisible()
  })

  test('should navigate to funds page', async ({ page }) => {
    await page.goto('/funds')

    // Check URL and content
    await expect(page).toHaveURL(/.*funds/)
    await expect(page.locator('text=Самоорганизация')).toBeVisible()
  })

  test('should navigate to knowledge page', async ({ page }) => {
    await page.goto('/knowledge')

    // Check URL and content
    await expect(page).toHaveURL(/.*knowledge/)
    await expect(page.locator('text=Интерактивное дерево знаний')).toBeVisible()
  })

  test('should show 404 page for non-existent routes', async ({ page }) => {
    await page.goto('/non-existent-route')

    // Check that 404 page is shown
    await expect(page.locator('text=404')).toBeVisible()
  })

  test('should handle direct navigation to all routes', async ({ page }) => {
    const routes = [
      { path: '/sources', content: 'body' },
      { path: '/funds', content: 'text=Самоорганизация' },
      { path: '/knowledge', content: 'text=Интерактивное дерево знаний' }
    ]

    for (const route of routes) {
      // Navigate directly to route
      await page.goto(route.path)

      // Verify URL and basic content loading
      await expect(page).toHaveURL(new RegExp(route.path.slice(1)))

      if (route.path === '/sources') {
        await page.waitForTimeout(1000) // Wait for lazy component
      }
      await expect(page.locator(route.content)).toBeVisible()
    }
  })
})
