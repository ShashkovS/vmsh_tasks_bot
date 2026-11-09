# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-isolation.spec.ts >> family: a byte-different built worker reaches prompt and controls the page (another tab)
- Location: e2e/runtime-isolation.spec.ts:566:3

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: "pw-chromium-1791465305838"
Received: "baseline"

Call Log:
- Timeout 5000ms exceeded while waiting on the predicate
```

# Page snapshot

```yaml
- generic [ref=e2]:
  - status [ref=e3]:
    - paragraph [ref=e4]: Доступно обновление.
    - generic [ref=e5]:
      - button "Обновить сейчас" [ref=e6]
      - button "Скрыть" [ref=e7]
  - main [ref=e8]:
    - alert [ref=e10]:
      - img [ref=e11]
      - generic [ref=e13]:
        - heading "Не удалось безопасно открыть кабинет" [level=1] [ref=e14]
        - paragraph [ref=e15]: Сервер не подтвердил настройки этого раздела. Повторите попытку.
        - button "Повторить" [ref=e16]
```

# Test source

```ts
  602 |     ).toBe(true)
  603 | 
  604 |     const initialPrompt = page.getByTestId('pwa-update-state')
  605 |     if (await initialPrompt.isVisible()) {
  606 |       const dismiss = initialPrompt.getByRole('button', { name: /Скрыть|Закрыть/ })
  607 |       await dismiss.click()
  608 |     }
  609 |     const controlToken = process.env.VMSH_E2E_GATEWAY_CONTROL_TOKEN
  610 |     expect(controlToken).toBeTruthy()
  611 |     const generation = `pw-${test.info().project.name}-${Date.now()}`.toLowerCase()
  612 |     const controlResult = await page.evaluate(
  613 |       async ({ audience, controlToken, generation }) => {
  614 |         const response = await fetch(`/__e2e__/service-worker-generation/${audience}`, {
  615 |           method: 'POST',
  616 |           credentials: 'same-origin',
  617 |           headers: {
  618 |             'Content-Type': 'application/json',
  619 |             'X-VMSH-E2E-Control': controlToken,
  620 |           },
  621 |           body: JSON.stringify({ generation }),
  622 |         })
  623 |         const payload: unknown = await response.json()
  624 |         return { status: response.status, payload }
  625 |       },
  626 |       { audience, controlToken: controlToken!, generation },
  627 |     )
  628 |     expect(controlResult).toEqual({
  629 |       status: 200,
  630 |       payload: { ok: true, audience, generation },
  631 |     })
  632 | 
  633 |     const runtimeModeResult = await page.evaluate(
  634 |       async ({ audience, controlToken }) => {
  635 |         const response = await fetch(`/__e2e__/runtime-mode/${audience}`, {
  636 |           method: 'POST',
  637 |           credentials: 'same-origin',
  638 |           headers: {
  639 |             'Content-Type': 'application/json',
  640 |             'X-VMSH-E2E-Control': controlToken,
  641 |           },
  642 |           body: JSON.stringify({ mode: 'incompatible' }),
  643 |         })
  644 |         const payload: unknown = await response.json()
  645 |         return { status: response.status, payload }
  646 |       },
  647 |       { audience, controlToken: controlToken! },
  648 |     )
  649 |     expect(runtimeModeResult).toEqual({
  650 |       status: 200,
  651 |       payload: { ok: true, audience, mode: 'incompatible' },
  652 |     })
  653 | 
  654 |     await page.reload()
  655 |     await expect(page.getByRole('alert')).toContainText('Не удалось безопасно открыть кабинет')
  656 | 
  657 |     await page.evaluate(async (expectedScope) => {
  658 |       const registration = (await navigator.serviceWorker.getRegistrations()).find(
  659 |         (item) => item.scope === expectedScope,
  660 |       )
  661 |       if (!registration) throw new Error(`Missing registration for ${expectedScope}`)
  662 |       await registration.update()
  663 |     }, `${gatewayOrigin}/${audience}/`)
  664 |     await expect(page.getByText('Доступно обновление.')).toBeVisible({
  665 |       timeout: 20_000,
  666 |     })
  667 |     await expect
  668 |       .poll(() =>
  669 |         page.evaluate(async (expectedScope) => {
  670 |           const registration = (await navigator.serviceWorker.getRegistrations()).find(
  671 |             (item) => item.scope === expectedScope,
  672 |           )
  673 |           return registration?.waiting?.state ?? null
  674 |         }, `${gatewayOrigin}/${audience}/`),
  675 |       )
  676 |       .toBe('installed')
  677 |     // Reproduce a stale banner: a different tab claims the already downloaded update.
  678 |     if (activation === 'another tab') {
  679 |       const other = await context.newPage()
  680 |       await other.goto('/staff/login')
  681 |       await other.evaluate(async (audience) => {
  682 |         const registration = await navigator.serviceWorker.getRegistration(`/${audience}/`)
  683 |         if (!registration?.waiting) throw new Error('Expected waiting worker')
  684 |         registration.waiting.postMessage({ type: 'SKIP_WAITING' })
  685 |       }, audience)
  686 |       // testing-strategy.md: a controller can become redundant between the
  687 |       // probe and its response. Poll readiness through that handover; the
  688 |       // final assertion still requires the replacement worker's exact nonce.
  689 |       await expect
  690 |         .poll(async () => {
  691 |           try {
  692 |             return await activeWorkerGeneration(page)
  693 |           } catch (error) {
  694 |             if (
  695 |               error instanceof Error &&
  696 |               error.message.includes('Service Worker generation probe timed out')
  697 |             )
  698 |               return null
  699 |             throw error
  700 |           }
  701 |         })
> 702 |         .toBe(generation)
      |          ^ Error: expect(received).toBe(expected) // Object.is equality
  703 |       await expect(page.getByText('Доступно обновление.')).toBeVisible()
  704 |       await other.close()
  705 |     }
  706 |     // The product reloads exactly once after the replacement worker really
  707 |     // becomes this document's controller. Arm the observer before the click:
  708 |     // a test-side reload would hide whether the real update UX works.
  709 |     // Authentication may already have replaced the route with its audience-
  710 |     // local login URL while RuntimeBootstrap shows the incompatible-runtime
  711 |     // fallback. A reload must preserve that exact current URL, not force root.
  712 |     const currentUrl = page.url()
  713 |     const updateNavigation = page.waitForEvent('framenavigated', {
  714 |       predicate: (frame) => frame === page.mainFrame() && frame.url() === currentUrl,
  715 |       timeout: 30_000,
  716 |     })
  717 |     await Promise.all([
  718 |       updateNavigation,
  719 |       page.getByRole('button', { name: 'Обновить сейчас' }).click(),
  720 |     ])
  721 |     await page.waitForLoadState('domcontentloaded')
  722 |     await expect(page.getByRole('alert')).toContainText('Не удалось безопасно открыть кабинет')
  723 |     await expect
  724 |       .poll(
  725 |         async () => {
  726 |           try {
  727 |             return await activeWorkerGeneration(page)
  728 |           } catch {
  729 |             return null
  730 |           }
  731 |         },
  732 |         { timeout: 20_000 },
  733 |       )
  734 |       .toBe(generation)
  735 |     const readyRegistration = await page.evaluate(async () => {
  736 |       const registration = await navigator.serviceWorker.ready
  737 |       return {
  738 |         scope: registration.scope,
  739 |         script: registration.active?.scriptURL ?? null,
  740 |       }
  741 |     })
  742 |     // WebKit can retain an `activating` state wrapper after `ready` resolves.
  743 |     // The ready registration plus a generation response from the page's
  744 |     // controller are the interoperable proof that the new worker owns it.
  745 |     expect(readyRegistration).toEqual({
  746 |       scope: `${gatewayOrigin}/${audience}/`,
  747 |       script: `${gatewayOrigin}/${audience}/sw.js`,
  748 |     })
  749 |     await expect
  750 |       .poll(() => page.evaluate((cacheName) => caches.has(cacheName), obsoleteCacheName))
  751 |       .toBe(false)
  752 |     await expect
  753 |       .poll(() => page.evaluate((cacheName) => caches.has(cacheName), legacyUnscopedCacheName))
  754 |       .toBe(false)
  755 |     await expect
  756 |       .poll(() => page.evaluate((cacheName) => caches.has(cacheName), legacyRecentMediaCacheName))
  757 |       .toBe(false)
  758 |     expect(await page.evaluate((cacheName) => caches.has(cacheName), otherAudienceSentinel)).toBe(
  759 |       true,
  760 |     )
  761 |     expect(
  762 |       await page.evaluate((cacheName) => caches.has(cacheName), otherAudienceRecentMediaSentinel),
  763 |     ).toBe(true)
  764 |   })
  765 | }
  766 | 
  767 | for (const audience of audiences) {
  768 |   test(`${audience}: product realtime reconnects with cursor and refetches HTTP authority`, async ({
  769 |     page,
  770 |   }) => {
  771 |     // This observes the socket created by RealtimeProvider in the production
  772 |     // bundle. Unit tests own timing edge cases; here real aiohttp proves the
  773 |     // browser composition and mandatory reconnect refetch from Phase 1.
  774 |     await installProductRealtimeProbe(page)
  775 |     let authMeRequests = 0
  776 |     page.on('request', (request) => {
  777 |       const url = new URL(request.url())
  778 |       if (request.method() === 'GET' && url.pathname === `/${audience}/api/v1/auth/me`) {
  779 |         authMeRequests += 1
  780 |       }
  781 |     })
  782 |     await loginThroughUi(page, websocketPersona[audience])
  783 |     await expect
  784 |       .poll(() => productRealtimeSnapshot(page))
  785 |       .toEqual([
  786 |         {
  787 |           url: `${gatewayOrigin.replace('http:', 'ws:')}/${audience}/ws`,
  788 |           // Other specs use the same real event fan-out. An owner-scoped
  789 |           // invalidation may legitimately arrive before this probe closes the
  790 |           // socket; connection establishment is the invariant under test.
  791 |           receivedTypes: expect.arrayContaining(['connected']),
  792 |           closeCode: null,
  793 |         },
  794 |       ])
  795 |     const authorityBaseline = authMeRequests
  796 | 
  797 |     await closeLatestProductRealtimeSocket(page)
  798 |     await expect
  799 |       .poll(() => productRealtimeSnapshot(page))
  800 |       .toEqual([
  801 |         {
  802 |           url: `${gatewayOrigin.replace('http:', 'ws:')}/${audience}/ws`,
```