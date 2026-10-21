import { expect, test, type Page } from '@playwright/test'

// Demo users seeded by the compose stack (TRACKER_SEED_DEMO=true).
const PASSWORD = 'demo-pass-1234'

async function login(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
}

async function logout(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Username').fill('kgibson')
  await page.getByLabel('Password').fill('wrong-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Incorrect username or password')
  await expect(page).toHaveURL(/\/login$/)
})

test('deep link survives the login redirect', async ({ page }) => {
  await page.goto('/defects?severity=critical')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Username').fill('achen')
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/defects\?severity=critical$/)
  await expect(page.getByLabel('Severity')).toHaveValue('critical')
})

test('viewer has read-only access', async ({ page }) => {
  await login(page, 'viewer')
  await expect(page.getByRole('link', { name: 'Report defect' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Defects', exact: true }).click()
  await page.getByRole('link', { name: /^DEF-/ }).first().click()
  await expect(page.getByText('Read-only access.')).toBeVisible()
})

test('defect goes from report to independent closure', async ({ page }) => {
  const title = `Gimbal stall during slew ${Date.now()}`

  // engineer reports and works the defect
  await login(page, 'kgibson')
  await page.getByRole('link', { name: 'Report defect' }).click()
  await page.getByLabel('Title').fill(title)
  await page.getByLabel('Severity').selectOption('critical')
  await page.getByLabel('Component').fill('gimbal')
  await page.getByLabel('Failure mode').fill('Slew time exceeds 2.0 s')
  await page.getByLabel('Assignee').selectOption('kgibson')
  await page.getByRole('button', { name: 'Create defect' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  const key = (await page.locator('.detail-head .key').textContent())!.trim()

  // the workflow explains what is missing before allowing each step
  await page.getByRole('button', { name: 'Move to Investigating' }).click()
  await expect(page.locator('.detail-head')).toContainText('Investigating')
  await expect(page.getByText('record the root cause category and description')).toBeVisible()

  await page.getByLabel('Root cause category').selectOption('material')
  await page.getByLabel('Root cause', { exact: true }).fill('Motor lot G-2603 has low torque margin')
  await page.getByRole('button', { name: 'Save investigation' }).click()
  await page.getByRole('button', { name: 'Move to Root cause identified' }).click()

  await page.getByLabel('Action description').fill('Quarantine lot G-2603 and return to supplier')
  await page.getByLabel('Action owner').selectOption('achen')
  await page.getByRole('button', { name: 'Add action' }).click()
  await page.getByRole('button', { name: 'Move to Corrective action' }).click()
  await page.getByRole('button', { name: 'Mark complete' }).click()
  await page.getByRole('button', { name: 'Move to Verification' }).click()

  await page.getByLabel('Verification evidence').fill('Slew 1.52 s on 3 units from lot G-2604')
  await page.getByRole('button', { name: 'Save investigation' }).click()
  // the assignee is an engineer: closing needs a lead, and someone else
  await expect(page.getByRole('button', { name: 'Move to Closed' })).toBeDisabled()
  await expect(page.getByText('requires a lead or admin')).toBeVisible()
  await logout(page)

  // a lead verifies and closes
  await login(page, 'mlopez')
  await page.goto(`/defects/${key}`)
  await page.getByRole('button', { name: 'Move to Closed' }).click()
  await expect(page.locator('.detail-head')).toContainText('Closed')
  await expect(page.locator('.timeline')).toContainText('moved Verification to Closed')
  await expect(page.getByRole('button', { name: 'Save investigation' })).toHaveCount(0) // locked
})

test('sending work back requires a reason', async ({ page }) => {
  await login(page, 'mlopez')
  await page.goto('/defects?status=verification')
  await page.getByRole('link', { name: /^DEF-/ }).first().click()
  const back = page.getByRole('button', { name: 'Back to Corrective action' })
  await expect(back).toBeDisabled()
  await page.getByLabel('Reason for Corrective action').fill('Unit 4 still outside limits on retest')
  await back.click()
  await expect(page.locator('.detail-head')).toContainText('Corrective action')
  await expect(page.locator('.timeline')).toContainText('Unit 4 still outside limits on retest')
})

test('dashboard shows metrics with table views', async ({ page }) => {
  await login(page, 'achen')
  await expect(page.getByRole('heading', { name: 'Quality dashboard' })).toBeVisible()
  await expect(page.getByText('open defects', { exact: true })).toBeVisible()
  const pareto = page.locator('section', { has: page.getByRole('heading', { name: 'Failure Pareto (top 10)' }) })
  await pareto.getByText('Table view').click()
  await expect(pareto.locator('table tbody tr').first()).toBeVisible()
})
