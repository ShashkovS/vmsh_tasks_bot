import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import type { ReactNode } from 'react'
import { SemanticMathDocument } from '@vmsh/content'
import type { WhiteboardExport, WebContentBlock } from '@vmsh/contracts'
import './whiteboard-export.css'

export function exportPrefix(data: WhiteboardExport) {
  const safe = (s: string) => s.replace(/[^\p{L}\p{N}_-]/gu, '_')
  return `${safe(data.sheet.courseCode)}_${String(data.sheet.lessonNumber).padStart(2, '0')}${safe(data.sheet.groupCode)}`
}

function validateBlocks(blocks: WebContentBlock[]) {
  for (const block of blocks) {
    if (block.type === 'figure' && block.asset.status !== 'available')
      throw new Error('Рисунок недоступен')
    if (block.type === 'subpart' || block.type === 'callout') validateBlocks(block.blocks)
    if (block.type === 'list') block.items.forEach(validateBlocks)
  }
}

// Export-only React root, not a Fast Refresh component module.
// eslint-disable-next-line react-refresh/only-export-components
function Statistics({ data }: { data: WhiteboardExport }) {
  const stats = data.statistics!
  const number = (n: number) => n.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  return (
    <>
      <h1>
        {data.sheet.courseName} · Занятие {data.sheet.lessonNumber} · {data.sheet.groupName}
      </h1>
      {data.sheet.lessonTitle && <p>{data.sheet.lessonTitle}</p>}
      <p>Сформировано {new Date(stats.generatedAt).toLocaleString('ru-RU')}</p>
      <table>
        <thead>
          <tr>
            {['Задача', 'Название', 'Баллы', 'Пробовали', 'Участников', 'Доля'].map((t) => (
              <th key={t}>{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stats.problems.map((p) => (
            <tr key={p.problemId}>
              <td>{p.label}</td>
              <td>{p.title}</td>
              <td>{number(p.points)}</td>
              <td>{p.tried}</td>
              <td>{stats.participantCount}</td>
              <td>{p.tried === 0 || p.share === null ? '—' : `${number(p.share)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

// DOM capture must run on the main thread; ZIP work runs in the cancellable worker.
// See docs/whiteboard-export.md for size limits and all-or-nothing download.
export async function generateWhiteboard(
  data: WhiteboardExport,
  signal: AbortSignal,
  progress: (text: string) => void,
) {
  const { toCanvas, getFontEmbedCSS } = await import('html-to-image')
  signal.throwIfAborted()
  const host = document.createElement('div')
  host.style.cssText = 'position:fixed;left:-10000px;top:0;width:800px;pointer-events:none;'
  host.setAttribute('aria-hidden', 'true')
  host.inert = true
  document.body.append(host)
  async function resources<T>(promise: Promise<T>): Promise<T> {
    signal.throwIfAborted()
    let timeout: ReturnType<typeof setTimeout> | undefined
    let abort: (() => void) | undefined
    try {
      return await Promise.race([
        promise,
        new Promise<never>((_, reject) => {
          abort = () => reject(new DOMException('Отменено', 'AbortError'))
          signal.addEventListener('abort', abort, { once: true })
          timeout = setTimeout(
            () => reject(new Error('Ресурсы не загрузились за 30 секунд')),
            30_000,
          )
        }),
      ])
    } finally {
      clearTimeout(timeout)
      if (abort) signal.removeEventListener('abort', abort)
    }
  }
  const root = createRoot(host)
  const files: Record<string, Uint8Array> = {}
  const prefix = exportPrefix(data)
  let current = 'Введение'
  try {
    async function capture(name: string, node: ReactNode, blocks: WebContentBlock[] = []) {
      signal.throwIfAborted()
      validateBlocks(blocks)
      flushSync(() => root.render(<div className="vmsh-export-paper">{node}</div>))
      const paper = host.firstElementChild as HTMLElement
      await resources(document.fonts.ready)
      await Promise.all(
        Array.from(paper.querySelectorAll('img')).map(async (img) => {
          await resources(img.decode())
          if (!img.naturalWidth) throw new Error('Рисунок не загрузился')
        }),
      )
      signal.throwIfAborted()
      if (paper.querySelector('.vmsh-figure-missing')) throw new Error('Рисунок не загрузился')
      const height = Math.ceil(paper.getBoundingClientRect().height)
      if (height * 2 > 16000 || height * 800 * 4 > 16_000_000 || paper.scrollWidth > 800) {
        throw new Error('Условие превышает допустимый размер изображения')
      }
      const fontEmbedCSS = await resources(getFontEmbedCSS(paper))
      signal.throwIfAborted()
      // WebKit can omit raster <img> inside SVG foreignObject. Keep the
      // measured image slots and composite decoded assets directly instead.
      const bounds = paper.getBoundingClientRect()
      const pictures = Array.from(paper.querySelectorAll('img')).map((img) => {
        const rect = img.getBoundingClientRect()
        return {
          img,
          x: rect.left - bounds.left,
          y: rect.top - bounds.top,
          width: rect.width,
          height: rect.height,
        }
      })
      const canvas = await toCanvas(paper, {
        width: 800,
        height,
        pixelRatio: 2,
        backgroundColor: '#fff',
        fontEmbedCSS,
        skipAutoScale: true,
        filter: (node) => !(node instanceof HTMLImageElement),
      })
      try {
        signal.throwIfAborted()
        const context = canvas.getContext('2d')
        if (!context) throw new Error('Canvas недоступен')
        for (const picture of pictures) {
          context.drawImage(
            picture.img,
            picture.x * 2,
            picture.y * 2,
            picture.width * 2,
            picture.height * 2,
          )
        }
        const blob = await new Promise<Blob>((resolve, reject) =>
          canvas.toBlob(
            (b) => (b ? resolve(b) : reject(new Error('Не удалось создать PNG'))),
            'image/png',
          ),
        )
        files[name] = new Uint8Array(await blob.arrayBuffer())
      } finally {
        canvas.width = 0
        canvas.height = 0
      }
    }
    const base = { ...data.document, title: null, introduction: [], problems: [] }
    if (data.document.introduction.some((b) => b.type !== 'divider' && b.type !== 'heading')) {
      progress(current)
      await capture(
        `${prefix}_введение.png`,
        <SemanticMathDocument
          document={{ ...base, introduction: data.document.introduction }}
          imageLoading="eager"
        />,
        data.document.introduction,
      )
    }
    for (const [index, problem] of data.document.problems.entries()) {
      current = `Задача ${problem.taskReference ?? problem.ordinal}`
      progress(`Задача ${index + 1} из ${data.document.problems.length}`)
      await capture(
        `${prefix}.${String(problem.ordinal).padStart(2, '0')}.png`,
        <SemanticMathDocument document={{ ...base, problems: [problem] }} imageLoading="eager" />,
        [...(problem.preambleBlocks ?? []), ...problem.blocks, ...(problem.trailingBlocks ?? [])],
      )
    }
    if (data.statistics) {
      current = 'Статистика'
      progress(current)
      await capture(`${prefix}_статистика.png`, <Statistics data={data} />)
    }
    signal.throwIfAborted()
    if (Object.keys(files).length === 0) throw new Error('В листке нет условий для экспорта')
    progress('Собираем ZIP…')
    const Worker = (await import('./whiteboard-zip.worker?worker')).default
    const worker = new Worker()
    try {
      const bytes = await new Promise<Uint8Array<ArrayBuffer>>((resolve, reject) => {
        const abort = () => reject(new DOMException('Отменено', 'AbortError'))
        signal.addEventListener('abort', abort, { once: true })
        worker.onmessage = (event: MessageEvent<Uint8Array<ArrayBuffer>>) => {
          signal.removeEventListener('abort', abort)
          resolve(event.data)
        }
        worker.onerror = () => {
          signal.removeEventListener('abort', abort)
          reject(new Error('Не удалось собрать ZIP'))
        }
        worker.postMessage(
          files,
          Object.values(files).map((f) => f.buffer),
        )
        if (signal.aborted) abort()
      })
      signal.throwIfAborted()
      return {
        blob: new Blob([bytes], { type: 'application/zip' }),
        filename: `${prefix}_разбор.zip`,
      }
    } finally {
      worker.terminate()
    }
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error(
      `${current}: ${error instanceof Error ? error.message : 'не удалось создать изображение'}`,
    )
  } finally {
    root.unmount()
    host.remove()
  }
}
