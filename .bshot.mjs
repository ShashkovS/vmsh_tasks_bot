import { chromium } from 'playwright'
const out = '/private/tmp/claude-502/-Users-sergeyshashkov-repos-vmsh-tasks-bot/397a03b5-8720-440d-b17b-d069746e276c/scratchpad'
const b = await chromium.launch()
const p = await b.newPage({ viewport:{width:820,height:900}, deviceScaleFactor:2 })
await p.goto('http://127.0.0.1:6106/iframe.html?id=foundations-brand--light&viewMode=story', {waitUntil:'networkidle'})
await p.waitForTimeout(700)
await p.screenshot({path:`${out}/brand.png`, fullPage:true})
await b.close(); console.log('ok')
