// Regenerate README screenshots from the running compose stack:
//   node e2e/scripts/screenshots.mjs [baseURL]
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const base = process.argv[2] ?? 'http://localhost:8080'
const shot = (name) => fileURLToPath(new URL(`../../docs/images/${name}.png`, import.meta.url))
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: 'light' })

await page.goto(`${base}/login`)
await page.getByLabel('Username').fill('mlopez')
await page.getByLabel('Password').fill('demo-pass-1234')
await page.getByRole('button', { name: 'Sign in' }).click()
await page.getByRole('heading', { name: 'Quality dashboard' }).waitFor()
await page.screenshot({ path: shot('dashboard') })

await page.goto(`${base}/defects?status=verification`)
await page.getByRole('link', { name: /^DEF-/ }).first().click()
await page.locator('.timeline li').first().waitFor()
await page.screenshot({ path: shot('defect'), fullPage: true })

await page.goto(`${base}/defects`)
await page.locator('tbody tr').first().waitFor()
await page.screenshot({ path: shot('list') })
await browser.close()
console.log('screenshots written to docs/images')
