import type { NewsPost } from '@vmsh/contracts'

import type { TelegramMedia, TelegramPostView } from './telegram-post'

/** Maps the Phase-8 wire contract to the accepted Telegram-rich product view. */
export function toTelegramPostView(
  post: NewsPost,
  formatMoment: (value: string) => string,
): TelegramPostView {
  const media: TelegramMedia[] = post.media.map((item) => {
    if (item.kind === 'photo') {
      return {
        kind: 'photo',
        alt: item.alt,
        ...(item.previewUrl === null ? {} : { previewUrl: item.previewUrl }),
      }
    }
    if (item.kind === 'video') {
      return {
        kind: 'video',
        ...(item.previewUrl === null ? {} : { previewUrl: item.previewUrl }),
      }
    }
    return {
      kind: 'document',
      name: item.name,
      ...(item.url === null ? {} : { url: item.url }),
    }
  })
  return {
    id: post.postId,
    blocks: post.blocks.map((block) => ({
      kind: 'text' as const,
      text: block.text,
      ...(block.entities === undefined
        ? {}
        : {
            entities: block.entities.map((entity) => ({
              type: entity.type,
              offset: entity.offset,
              length: entity.length,
              ...(entity.href === undefined ? {} : { href: entity.href }),
            })),
          }),
    })),
    media,
    state: post.state,
    at: formatMoment(post.publishedAt),
    ...(post.editedAt === null ? {} : { editedAt: formatMoment(post.editedAt) }),
    ...(post.attribution === null ? {} : { attribution: post.attribution }),
  }
}
