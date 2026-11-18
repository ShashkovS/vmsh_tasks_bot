#!/usr/bin/env bash
set -euo pipefail

LIBHEIF_PREFIX=/opt/libheif-1.23.1
UHDR_PREFIX=/opt/libuhdr-2.0
IM_PREFIX=/opt/imagemagick-7-smartphone

# HEAD google/libultrahdr на 2026-08-10.
UHDR_COMMIT=c0bbdcb16351d087ebacc4fa198340f2a1c7b16a

sudo apt update

sudo apt install -y \
  git ca-certificates build-essential pkg-config cmake ninja-build \
  ffmpeg libavcodec-dev libavutil-dev \
  libde265-dev libx265-dev libdav1d-dev libaom-dev \
  libopenh264-dev libx264-dev \
  libsvtav1enc-dev librav1e-dev \
  libjpeg-dev libpng-dev libtiff-dev libwebp-dev libgif-dev \
  libjxl-dev libopenjp2-7-dev libopenjph-dev \
  libraw-dev libopenexr-dev \
  libsharpyuv-dev libbrotli-dev zlib1g-dev libzstd-dev \
  libxml2-dev liblqr-1-0-dev librsvg2-dev \
  libfreetype-dev libfontconfig1-dev liblcms2-dev libraqm-dev libwebm-dev aom-tools libyuv-dev


###############################################################################
# Google libultrahdr
###############################################################################

cd /tmp
rm -rf libultrahdr

git clone https://github.com/google/libultrahdr.git
cd libultrahdr
git checkout "$UHDR_COMMIT"

cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$UHDR_PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=ON \
  -DUHDR_BUILD_DEPS=OFF \
  -DUHDR_BUILD_EXAMPLES=OFF \
  -DUHDR_BUILD_TESTS=OFF \
  -DUHDR_ENABLE_INSTALL=ON

ninja -C build
sudo ninja -C build install


###############################################################################
# libheif 1.23.1
###############################################################################

cd /tmp
rm -rf libheif

git clone --depth 1 \
  --branch v1.23.1 \
  https://github.com/strukturag/libheif.git

cd libheif

cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$LIBHEIF_PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  \
  -DENABLE_PLUGIN_LOADING=OFF \
  \
  -DWITH_LIBDE265=ON \
  -DWITH_X265=ON \
  \
  -DWITH_FFMPEG_DECODER=ON \
  \
  -DWITH_DAV1D=ON \
  -DWITH_AOM_DECODER=ON \
  -DWITH_AOM_ENCODER=ON \
  -DWITH_SvtEnc=ON \
  -DWITH_RAV1E=ON \
  \
  -DWITH_OpenH264_DECODER=ON \
  -DWITH_X264=ON \
  \
  -DWITH_JPEG_DECODER=ON \
  -DWITH_JPEG_ENCODER=ON \
  \
  -DWITH_OpenJPEG_DECODER=ON \
  -DWITH_OpenJPEG_ENCODER=ON \
  -DWITH_OPENJPH_ENCODER=ON \
  \
  -DWITH_UNCOMPRESSED_CODEC=ON \
  -DWITH_HEADER_COMPRESSION=ON \
  \
  -DWITH_LIBSHARPYUV=ON \
  \
  -DENABLE_MULTITHREADING_SUPPORT=ON \
  -DENABLE_PARALLEL_TILE_DECODING=ON \
  -DENABLE_EXPERIMENTAL_FEATURES=OFF \
  \
  -DWITH_EXAMPLES=ON

ninja -C build
sudo ninja -C build install


###############################################################################
# Dynamic loader
###############################################################################

printf '%s\n' \
  "$LIBHEIF_PREFIX/lib" \
  "$UHDR_PREFIX/lib" \
  | sudo tee /etc/ld.so.conf.d/imagemagick-smartphone.conf >/dev/null

sudo ldconfig


###############################################################################
# ImageMagick 7.1.2-29
###############################################################################

cd /tmp
rm -rf ImageMagick

git clone --depth 1 \
  --branch 7.1.2-29 \
  https://github.com/ImageMagick/ImageMagick.git

cd ImageMagick

export PKG_CONFIG_PATH="$LIBHEIF_PREFIX/lib/pkgconfig:$UHDR_PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

# Не даём runtime случайно подцепить Ubuntu libheif вместо нашей.
export LDFLAGS="-Wl,-rpath,$LIBHEIF_PREFIX/lib -Wl,-rpath,$UHDR_PREFIX/lib ${LDFLAGS:-}"

./configure \
  --prefix="$IM_PREFIX" \
  --with-heic=yes \
  --with-uhdr=yes \
  --with-jxl=yes \
  --with-webp=yes \
  --with-raw=yes

make -j"$(nproc)"
sudo make install
sudo ldconfig


###############################################################################
# Verification
###############################################################################

MAGICK="$IM_PREFIX/bin/magick"

echo
echo '=== ImageMagick version / delegates ==='
"$MAGICK" -version

echo
echo '=== Smartphone-related formats ==='
"$MAGICK" -list format \
  | grep -Ei '(^|[[:space:]])(AVIF|HEIC|HEIF|UHDR|JXL|WEBP|DNG|RAW|JPEG|JPG|PNG|TIFF|JP2|J2K)([[:space:]]|$)' \
  || true

echo
echo '=== pkg-config versions ==='
PKG_CONFIG_PATH="$PKG_CONFIG_PATH" \
  pkg-config --modversion libheif libuhdr libjxl

echo
echo '=== Runtime libraries ==='
MAGICKCORE="$(find "$IM_PREFIX/lib" -type f -name 'libMagickCore-*.so.*' | head -n1)"

ldd "$MAGICKCORE" \
  | grep -Ei 'heif|uhdr|jxl|webp|raw|jpeg|png|tiff|openjp' \
  || true

echo
echo '=== Smoke tests: HEIC / AVIF / JXL / WebP ==='

rm -rf /tmp/imagemagick-smartphone-smoke
mkdir -p /tmp/imagemagick-smartphone-smoke

"$MAGICK" -size 64x64 gradient: \
  /tmp/imagemagick-smartphone-smoke/test.heic

"$MAGICK" \
  /tmp/imagemagick-smartphone-smoke/test.heic \
  null:

"$MAGICK" -size 64x64 gradient: \
  /tmp/imagemagick-smartphone-smoke/test.avif

"$MAGICK" \
  /tmp/imagemagick-smartphone-smoke/test.avif \
  null:

"$MAGICK" -size 64x64 gradient: \
  /tmp/imagemagick-smartphone-smoke/test.jxl

"$MAGICK" \
  /tmp/imagemagick-smartphone-smoke/test.jxl \
  null:

"$MAGICK" -size 64x64 gradient: \
  /tmp/imagemagick-smartphone-smoke/test.webp

"$MAGICK" \
  /tmp/imagemagick-smartphone-smoke/test.webp \
  null:

echo
echo 'OK'

echo 'symlinking'
sudo ln -sfn /opt/imagemagick-7-smartphone/bin/magick /usr/local/bin/magick
for f in /opt/imagemagick-7-smartphone/bin/*; do
    sudo ln -sfn "$f" "/usr/local/bin/$(basename "$f")"
done
