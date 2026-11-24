/**
 * Keep an in-memory snapshot of a user-selected source. Cloud-backed files may
 * change their browser handle after the picker closes; retrying that handle
 * later otherwise fails with ERR_UPLOAD_FILE_CHANGED.
 */
export async function stableBrowserFile(file: File): Promise<File> {
  return new File([await file.arrayBuffer()], file.name, {
    type: file.type,
    lastModified: file.lastModified,
  })
}
