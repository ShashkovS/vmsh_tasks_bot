import type { SolutionTextEdit, TextOrigin } from '@vmsh/contracts'

/** docs/paste-evidence.md: provenance follows edits, not cumulative paste size. */
export function packTextOrigin(flags: Uint8Array): TextOrigin {
  const bytes = new Uint8Array(Math.ceil(flags.length / 8))
  for (let index = 0; index < flags.length; index += 1) {
    if (flags[index]) bytes[index >> 3]! |= 1 << (index % 8)
  }
  return { version: 1, utf16Length: flags.length, bits: btoa(String.fromCharCode(...bytes)) }
}

function unpack(origin: TextOrigin): Uint8Array {
  const bytes = atob(origin.bits)
  return Uint8Array.from(
    { length: origin.utf16Length },
    (_, index) => (bytes.charCodeAt(index >> 3) >> (index % 8)) & 1,
  )
}

interface Snapshot {
  text: string
  origin: TextOrigin | null
}

export class TextOriginHistory {
  private snapshots: Snapshot[] = []
  private position = -1

  private remember(text: string, origin: TextOrigin | null) {
    this.snapshots = this.snapshots.slice(0, this.position + 1)
    this.snapshots.push({ text, origin })
    let bytes = this.snapshots.reduce(
      (sum, item) => sum + item.text.length * 2 + (item.origin?.bits.length ?? 0) * 2,
      0,
    )
    while (this.snapshots.length > 1 && (this.snapshots.length > 101 || bytes > 5 * 1024 * 1024)) {
      const first = this.snapshots.shift()!
      bytes -= first.text.length * 2 + (first.origin?.bits.length ?? 0) * 2
    }
    this.position = this.snapshots.length - 1
  }

  edit(
    previous: string,
    next: string,
    origin: TextOrigin | null,
    change?: SolutionTextEdit,
  ): TextOrigin | null {
    if (
      this.snapshots[this.position]?.text !== previous ||
      this.snapshots[this.position]?.origin?.bits !== origin?.bits
    ) {
      this.snapshots = []
      this.position = -1
      this.remember(previous, origin)
    }
    if (change?.inputType === 'historyUndo' || change?.inputType === 'historyRedo') {
      const direction = change.inputType === 'historyUndo' ? -1 : 1
      for (
        let index = this.position + direction;
        index >= 0 && index < this.snapshots.length;
        index += direction
      ) {
        if (this.snapshots[index]!.text === next) {
          this.position = index
          return this.snapshots[index]!.origin
        }
      }
      this.remember(next, null)
      return next === '' ? packTextOrigin(new Uint8Array()) : null
    }
    if (!origin && previous !== '') {
      const result = next === '' ? packTextOrigin(new Uint8Array()) : null
      this.remember(next, result)
      return result
    }
    const oldFlags = origin ? unpack(origin) : new Uint8Array(previous.length)
    let start = 0
    let end = previous.length
    let newEnd = next.length
    // Selection disambiguates inserting/replacing repeated text, including a
    // paste that leaves the visible value unchanged.
    if (
      change &&
      change.start >= 0 &&
      change.end >= change.start &&
      change.end <= previous.length &&
      next.startsWith(previous.slice(0, change.start)) &&
      next.endsWith(previous.slice(change.end)) &&
      next.length >= previous.length - (change.end - change.start)
    ) {
      start = change.start
      end = change.end
      newEnd = next.length - (previous.length - end)
    } else {
      while (start < previous.length && start < next.length && previous[start] === next[start])
        start += 1
      while (end > start && newEnd > start && previous[end - 1] === next[newEnd - 1]) {
        end -= 1
        newEnd -= 1
      }
    }
    const flags = new Uint8Array(next.length)
    flags.set(oldFlags.subarray(0, start))
    if (change?.pasted || change?.inputType === 'insertFromPaste') flags.fill(1, start, newEnd)
    flags.set(oldFlags.subarray(end), newEnd)
    const result = packTextOrigin(flags)
    this.remember(next, result)
    return result
  }
}
