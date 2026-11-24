#!/usr/bin/env bash
# Reproducible smartphone image stack; see README.md. Run as root on Ubuntu.
set -euo pipefail
umask 022
ROOT=/web/vmsh_tasks_bot/image-stack
PREFIX=/opt/vmsh-image-stack/20261117
JOBS=2
mkdir -p "$ROOT/src" "$ROOT/logs" "$PREFIX"
ln -sfn /opt/vmsh-image-stack "$ROOT/installed"
export DEBIAN_FRONTEND=noninteractive
# Grafana's unrelated repository can return 403 from this hosting network.
# Update only the signed Ubuntu sources needed for build dependencies.
mkdir -p "$ROOT/ubuntu-sources"
for source in /etc/apt/sources.list.d/[Rr]esolute*.sources /etc/apt/sources.list.d/ubuntu.sources; do
  test ! -f "$source" || ln -sfn "$source" "$ROOT/ubuntu-sources/$(basename "$source")"
done
apt-get -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts="$ROOT/ubuntu-sources" update
apt-get install -y build-essential pkg-config cmake ninja-build nasm git curl \
  libx265-dev libdav1d-dev libaom-dev libjpeg-dev libpng-dev libtiff-dev \
  libwebp-dev libgif-dev libjxl-dev libopenjp2-7-dev libraw-dev libopenexr-dev \
  libsharpyuv-dev libbrotli-dev zlib1g-dev libzstd-dev libxml2-dev \
  liblqr-1-0-dev librsvg2-dev libfreetype-dev libfontconfig1-dev liblcms2-dev libraqm-dev
cd "$ROOT/src"
fetch() {
  local name=$1 url=$2 digest=$3
  if ! test -f "$name"; then
    curl -fsSL --connect-timeout 10 --max-time 180 --retry 3 "$url" -o "$name.partial"
    mv "$name.partial" "$name"
  fi
  if test -n "$digest"; then printf '%s  %s\n' "$digest" "$name" | sha256sum -c -; fi
  sha256sum "$name" >> "$ROOT/source-sha256.txt"
}
fetch libde265-1.1.3.tar.gz https://github.com/strukturag/libde265/releases/download/v1.1.3/libde265-1.1.3.tar.gz 554228bd17788c99a7e63b37ab5634722190e6e2bf60c1dcb01cef328e133905
fetch libheif-1.23.7.tar.gz https://github.com/strukturag/libheif/releases/download/v1.23.7/libheif-1.23.7.tar.gz f7483e818503ea6224c8863e4a56ac02c7089021a98472c811c12aa19faf2475
fetch ultrahdr-2.0.2.tar.gz https://api.github.com/repos/google/libultrahdr/tarball/v2.0.2 cb5accda6efd45e71c0edc165f5a141ce6a7fc907c808422d73783a3c4a05cf4
fetch ffmpeg-9.0.2.tar.gz https://api.github.com/repos/FFmpeg/FFmpeg/tarball/n9.0.2 f20424606b11f5ec5f3444e5b3e826a9b4f9cb97cddeae71011f2dc86db2a498
fetch imagemagick-7.1.2-36.tar.gz https://api.github.com/repos/ImageMagick/ImageMagick/tarball/7.1.2-36 ebbffeefd0fd1e5b4329e407ed84c23a6fa6ddddde38a3a21f1ddd6e61499988
unpack() {
  local archive=$1 dir=$2
  if ! test -d "$dir"; then mkdir "$dir"; tar -xf "$archive" --strip-components=1 -C "$dir"; fi
}
unpack libde265-1.1.3.tar.gz de265
unpack libheif-1.23.7.tar.gz heif
unpack ultrahdr-2.0.2.tar.gz uhdr
unpack ffmpeg-9.0.2.tar.gz ffmpeg
unpack imagemagick-7.1.2-36.tar.gz imagemagick
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export CPPFLAGS="-I$PREFIX/include"
export LDFLAGS="-L$PREFIX/lib -Wl,-rpath,$PREFIX/lib"
common=(-G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_INSTALL_RPATH="$PREFIX/lib" -DBUILD_SHARED_LIBS=ON)
cmake -S de265 -B de265/build "${common[@]}" -DENABLE_SDL=OFF -DENABLE_DECODER=OFF -DENABLE_ENCODER=OFF
cmake --build de265/build -j "$JOBS"
cmake --install de265/build
cmake -S uhdr -B uhdr/build "${common[@]}" -DUHDR_BUILD_DEPS=OFF \
  -DUHDR_BUILD_EXAMPLES=OFF -DUHDR_BUILD_TESTS=OFF -DUHDR_ENABLE_INSTALL=ON
cmake --build uhdr/build -j "$JOBS"
cmake --install uhdr/build
(
  cd ffmpeg
  ./configure --prefix="$PREFIX" --libdir="$PREFIX/lib" \
    --enable-shared --disable-static --enable-pic --disable-doc --disable-programs \
    --disable-everything --disable-autodetect --disable-network \
    --disable-avdevice --disable-avformat --disable-avfilter --disable-swresample \
    --disable-swscale --enable-avcodec --enable-avutil --enable-decoder=hevc \
    --enable-parser=hevc --extra-ldflags="-Wl,-rpath,$PREFIX/lib"
  make -j "$JOBS"
  make install
)
cmake -S heif -B heif/build "${common[@]}" -DCMAKE_PREFIX_PATH="$PREFIX" \
  -DENABLE_PLUGIN_LOADING=OFF -DWITH_LIBDE265=ON -DWITH_LIBDE265_PLUGIN=OFF \
  -DWITH_FFMPEG_DECODER=ON -DWITH_FFMPEG_DECODER_PLUGIN=OFF \
  -DWITH_X265=ON -DWITH_X265_PLUGIN=OFF -DWITH_DAV1D=ON -DWITH_DAV1D_PLUGIN=OFF \
  -DWITH_AOM_DECODER=ON -DWITH_AOM_DECODER_PLUGIN=OFF -DWITH_AOM_ENCODER=OFF \
  -DWITH_JPEG_DECODER=ON -DWITH_JPEG_ENCODER=ON -DWITH_UNCOMPRESSED_CODEC=ON \
  -DWITH_LIBSHARPYUV=ON -DENABLE_MULTITHREADING_SUPPORT=ON \
  -DENABLE_PARALLEL_TILE_DECODING=ON -DENABLE_EXPERIMENTAL_FEATURES=OFF \
  -DWITH_EXAMPLES=ON -DBUILD_TESTING=OFF
cmake --build heif/build -j "$JOBS"
cmake --install heif/build
(
  cd imagemagick
  ./configure --prefix="$PREFIX" --with-heic=yes --with-uhdr=yes --with-jxl=yes \
    --with-webp=yes --with-raw=yes --without-perl --disable-docs
  make -j "$JOBS"
  make install
)
# Preserve the existing upload policy instead of enabling an unrestricted build.
install -m 0644 /etc/ImageMagick-7/policy.xml "$PREFIX/etc/ImageMagick-7/policy.xml"
"$PREFIX/bin/magick" -version
"$PREFIX/bin/magick" -list format > "$ROOT/formats.txt"
"$PREFIX/bin/magick" -list policy > "$ROOT/policy.txt"
pkg-config --modversion libheif libde265 libuhdr libavcodec > "$ROOT/library-versions.txt"
echo 'Build complete; validate conversions before changing current/app configuration.'
