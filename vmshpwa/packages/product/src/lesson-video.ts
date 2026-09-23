import type { LessonVideoBlock } from '@vmsh/contracts'

const youtubeHosts = new Set([
  'youtube.com',
  'www.youtube.com',
  'm.youtube.com',
  'youtu.be',
  'www.youtube-nocookie.com',
])
const vkHosts = new Set(['vkvideo.ru', 'www.vkvideo.ru', 'vk.com', 'www.vk.com'])

function seconds(value: string): number | null {
  if (/^\d+$/.test(value)) return Number(value)
  const match = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/u.exec(value)
  if (!match || match[0] === '') return null
  return Number(match[1] ?? 0) * 3600 + Number(match[2] ?? 0) * 60 + Number(match[3] ?? 0)
}

function videoTitle(value: string | null | undefined): string | null {
  const title = value?.trim()
  if (!title) return null
  if (title.length > 200) throw new Error('Название видео не должно быть длиннее 200 символов')
  return title
}

function cleanSource(value: string): string {
  return value
    .replace(/&amp;/gu, '&')
    .replace(/&quot;/gu, '"')
    .trim()
}

function iframeSource(value: string): { source: string; title: string | null } | null {
  if (!/^\s*<iframe\b[\s\S]*<\/iframe>\s*$/iu.test(value)) return null
  if (/\bsrcdoc\s*=|\bon\w+\s*=/iu.test(value))
    throw new Error('В iframe нельзя использовать исполняемые атрибуты')
  const tags = [...value.matchAll(/<\s*\/?\s*([a-z][a-z0-9-]*)\b/giu)]
  if (tags.some((tag) => tag[1]?.toLowerCase() !== 'iframe')) {
    throw new Error('Iframe не должен содержать вложенную разметку')
  }
  const sources = [...value.matchAll(/(?:^|\s)src\s*=\s*(["'])([\s\S]*?)\1/giu)]
  if (sources.length !== 1) throw new Error('Iframe должен содержать ровно один src')
  const titles = [...value.matchAll(/(?:^|\s)title\s*=\s*(["'])([\s\S]*?)\1/giu)]
  if (titles.length > 1) throw new Error('Iframe содержит повторяющийся title')
  const titleMatch = titles[0]
  return {
    source: cleanSource(sources[0]?.[2] ?? ''),
    title: titleMatch === undefined ? null : cleanSource(titleMatch[2] ?? ''),
  }
}

/** Parse a provider URL or a provider iframe, never trusting the iframe HTML. */
export function normalizeLessonVideoUrl(raw: string, title?: string | null): LessonVideoBlock {
  const frame = iframeSource(raw)
  let url: URL
  try {
    url = new URL(frame?.source ?? raw.trim())
  } catch {
    throw new Error('Укажите корректную HTTPS-ссылку на YouTube или VK Видео')
  }
  if (url.protocol !== 'https:' || url.username || url.password || url.port)
    throw new Error('Видео должно использовать HTTPS без учётных данных')
  const hostname = url.hostname.toLowerCase()
  const resolvedTitle = videoTitle(title ?? frame?.title)
  if (youtubeHosts.has(hostname)) {
    let videoId: string | null = null
    if (hostname === 'youtu.be') videoId = url.pathname.split('/').filter(Boolean)[0] ?? null
    else if (url.pathname === '/watch') videoId = url.searchParams.get('v')
    else if (/^\/(embed|shorts)\//u.test(url.pathname)) videoId = url.pathname.split('/')[2] ?? null
    if (!videoId || !/^[A-Za-z0-9_-]{11}$/u.test(videoId))
      throw new Error('Идентификатор YouTube-видео некорректен')
    const times = [url.searchParams.get('start'), url.searchParams.get('t')].filter(
      (item): item is string => item !== null,
    )
    const parsed = times.map(seconds)
    if (parsed.some((item) => item === null) || (parsed.length === 2 && parsed[0] !== parsed[1]))
      throw new Error('Время начала YouTube-видео некорректно')
    const startSeconds = parsed[0] ?? 0
    if (startSeconds > 604800) throw new Error('Время начала YouTube-видео слишком велико')
    return { type: 'video', provider: 'youtube', videoId, startSeconds, title: resolvedTitle }
  }
  if (vkHosts.has(hostname)) {
    let ownerId: string | null = null
    let videoId: string | null = null
    let accessHash: string | null = null
    let hd = 2
    if (/\/video_ext\.php$/u.test(url.pathname)) {
      ownerId = url.searchParams.get('oid')
      videoId = url.searchParams.get('id')
      accessHash = url.searchParams.get('hash')
      const rawHd = url.searchParams.get('hd')
      if (rawHd !== null) hd = Number(rawHd)
    } else {
      const match = /^\/video(-?\d+)_([1-9]\d*)(?:_([A-Za-z0-9_-]+))?$/u.exec(url.pathname)
      ownerId = match?.[1] ?? null
      videoId = match?.[2] ?? null
      accessHash = match?.[3] ?? null
    }
    if (
      !ownerId ||
      !/^-?[1-9]\d{0,19}$/u.test(ownerId) ||
      !videoId ||
      !/^[1-9]\d{0,19}$/u.test(videoId) ||
      ![0, 1, 2, 3].includes(hd)
    )
      throw new Error('Ссылка VK Видео некорректна')
    if (accessHash !== null && !/^[A-Za-z0-9_-]{1,256}$/u.test(accessHash))
      throw new Error('Параметр доступа VK Видео некорректен')
    return {
      type: 'video',
      provider: 'vk',
      ownerId,
      videoId,
      accessHash,
      hd: hd as 0 | 1 | 2 | 3,
      title: resolvedTitle,
    }
  }
  throw new Error('Поддерживаются только YouTube и VK Видео')
}

export const parseLessonVideoInput = normalizeLessonVideoUrl

export function lessonVideoEmbedUrl(video: LessonVideoBlock): string {
  if (video.provider === 'youtube')
    return `https://www.youtube.com/embed/${video.videoId}?start=${video.startSeconds}`
  const query = new URLSearchParams({ oid: video.ownerId, id: video.videoId, hd: String(video.hd) })
  if (video.accessHash) query.set('hash', video.accessHash)
  return `https://vkvideo.ru/video_ext.php?${query.toString()}`
}

export function lessonVideoPrintUrl(video: LessonVideoBlock): string {
  if (video.provider === 'youtube')
    return `https://www.youtube.com/watch?v=${video.videoId}${video.startSeconds ? `&t=${video.startSeconds}` : ''}`
  return lessonVideoEmbedUrl(video)
}
