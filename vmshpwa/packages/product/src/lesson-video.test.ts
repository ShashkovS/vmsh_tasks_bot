import { describe, expect, it } from 'vitest'

import { lessonVideoEmbedUrl, normalizeLessonVideoUrl } from './lesson-video'

describe('lesson video normalization', () => {
  it('extracts the supplied YouTube iframe as normalized data', () => {
    expect(
      normalizeLessonVideoUrl(
        '<iframe width="560" height="315" src="https://www.youtube.com/embed/FTXGKbAk9To?si=QlPSxe22wDSyAwcw" title="YouTube video player" frameborder="0" allowfullscreen></iframe>',
      ),
    ).toEqual({
      type: 'video',
      provider: 'youtube',
      videoId: 'FTXGKbAk9To',
      startSeconds: 0,
      title: 'YouTube video player',
    })
  })

  it('extracts the supplied VK iframe without rendering its source HTML', () => {
    const video = normalizeLessonVideoUrl(
      '<iframe src="https://vkvideo.ru/video_ext.php?oid=-241691838&amp;id=456239017&amp;hd=2" width="853" height="480" allowfullscreen></iframe>',
    )
    expect(video).toEqual({
      type: 'video',
      provider: 'vk',
      ownerId: '-241691838',
      videoId: '456239017',
      accessHash: null,
      hd: 2,
      title: null,
    })
    expect(lessonVideoEmbedUrl(video)).toBe(
      'https://vkvideo.ru/video_ext.php?oid=-241691838&id=456239017&hd=2',
    )
  })

  it('normalizes a YouTube timestamp and rejects deceptive hosts', () => {
    expect(normalizeLessonVideoUrl('https://youtu.be/FTXGKbAk9To?t=1h2m3s')).toMatchObject({
      provider: 'youtube',
      startSeconds: 3723,
    })
    expect(() => normalizeLessonVideoUrl('https://youtube.com.example/FTXGKbAk9To')).toThrow()
    expect(() => normalizeLessonVideoUrl('http://youtu.be/FTXGKbAk9To')).toThrow()
  })
})
