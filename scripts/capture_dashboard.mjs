// Screenshot the deployed dashboard with Playwright (headless Chromium).
//
//   node scripts/capture_dashboard.mjs [outDir]
//
// Needs the `playwright` package (npm i -g playwright, or NODE_PATH pointing at a node_modules
// that has it) and a Chromium that matches it (npx playwright install chromium).
// The API sits on a scale-to-zero Container App, so each page is retried until the data has
// rendered (no skeletons, no error banner) before the shot is taken.
import { mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'

// CommonJS resolution honours NODE_PATH; ES `import` does not.
const { chromium } = createRequire(import.meta.url)('playwright')

const BASE = process.env.DASHBOARD_URL ?? 'https://air-quality-risk-forecasting.vercel.app'
const OUT = process.argv[2] ?? 'portfolio/images'
const PAGES = [
  ['overview', '/'],
  ['stations', '/stations'],
  // Operations is off by default (set CAPTURE_OPERATIONS=1 to include it).
  ...(process.env.CAPTURE_OPERATIONS ? [['operations', '/operations']] : []),
  ['model_health', '/model-health'],
]
const VIEWPORTS = [
  ['desktop', { width: 1440, height: 900 }],
  ['mobile', { width: 390, height: 844 }],
]
const ATTEMPTS = 6
const SETTLE_MS = 20_000

async function settled(page) {
  // Loaded when no skeleton is animating and the page has not flagged a data error.
  return page.evaluate(() => {
    const busy = document.querySelector('[aria-busy="true"], [data-skeleton], .animate-pulse')
    const failed =
      document.querySelector('[data-error]') || document.body.innerText.includes('Could not load this section')
    return !busy && !failed
  })
}

mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()
let failures = 0
for (const [vname, viewport] of VIEWPORTS) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, colorScheme: 'light' })
  for (const [pname, path] of PAGES) {
    const page = await context.newPage()
    let ok = false
    for (let attempt = 1; attempt <= ATTEMPTS && !ok; attempt++) {
      await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 90_000 }).catch(() => {})
      const deadline = Date.now() + SETTLE_MS
      while (Date.now() < deadline && !(ok = await settled(page))) await page.waitForTimeout(1000)
      if (!ok) await page.waitForTimeout(5000 * attempt) // cold API: back off, then reload
    }
    const file = join(OUT, `dashboard_${pname}_${vname}.png`)
    await page.waitForTimeout(800) // let chart transitions finish
    await page.screenshot({ path: file, fullPage: true })
    console.log(`${ok ? 'wrote' : 'WROTE (not settled)'} ${file}`)
    if (!ok) failures++
    await page.close()
  }
  await context.close()
}
await browser.close()
process.exit(failures ? 1 : 0)
