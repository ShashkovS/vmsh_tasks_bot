# Smartphone image conversion

17 November 2026: owner paused deployment documentation and requested latest
source-built ImageMagick/HEIF stack, exclusively used for conversions, plus
direct HEIC → WebP. Current system IM 7.1.2-18 / Ubuntu libheif 1.21.2 is insufficiently
verified against reported real HEIC failures.

Selected official stable versions: IM 7.1.2-36, libheif 1.23.7, libde265 1.1.3,
UltraHDR 2.0.2, FFmpeg 9.0.2. Build recipe: [build.sh](build.sh). Dedicated prefix
and runtime RPATH avoid mixing with old system codecs. Sources/build outputs
must not be added to backups. Pending: build, real HEIC/10-bit corpus conversion,
application direct-WebP path, tests, production switch and short runbook.

Completed:

- All five selected versions built from official sources; checked source SHA-256
  pins now cover every download. No global ld.so/LD_LIBRARY_PATH changes.
- Runtime ldd confirms libheif/libde265/libavcodec/libavutil/libuhdr all resolve
  inside `/opt/vmsh-image-stack/20261117/lib`. Existing ImageMagick policy retained.
- Actual application's converter on 8 public HEIC/HEIF specimens: all passed;
  old `/usr/bin/magick` failed all eight. JPEG with EXIF GPS, JPEG, PNG, WebP also
  passed; independent dwebp decoding, absent profiles/comments, bounds and corrupt
  input rejection checked. [Proof](proof.json), [sources](corpus-sources.json).
- Raster path is one ImageMagick call, first frame, auto-orient/strip/1920px/
  quality 82. No intermediate PNG and no external cwebp. 19 domain tests pass.
- Production's newer diagnostics/TeX fixes were preserved by patching only the
  raster method. Tested source SHA b9d28523cb02f9f87b413a3e68e57281211425c4c7aacec04b65c105098faf2f
  matches deployed source. PWA env and legacy JSON explicitly select
  `/opt/vmsh-image-stack/current/bin/magick`; CLI magick/convert/identify point to
  it as well. Both services restarted, main status/runtime APIs pass, no failed
  systemd units.
- Small source patch, base commit, build recipe/checksums retained in existing
  `backup-local-changes`; no binaries/build trees added to backup inputs. Removed
  516 MB of temporary build sources/objects. [Runbook](README.md).

The exact seven original failed user uploads were not available for replay;
do not describe the public regression corpus as those originals. General
deployment/migration documentation was paused by the owner for this task;
drafts are retained under the parent directory.

Follow-up: a reported Staff attachment GET failure was an older WebP uploaded
before the Beget outage. Authenticated reads return NoSuchKey/404 from both
FirstS3 and Timeweb; the original Beget bucket returns NoSuchBucket/404. No local
copy with that object name was found on either VPS, and the object was absent
from the final migration inventory. This is missing historical object data,
not a HEIC decode failure. No submission/asset rows were modified; recovery
requires an original or another retained copy. Do not claim codec upgrades
recover objects that are no longer in storage.
