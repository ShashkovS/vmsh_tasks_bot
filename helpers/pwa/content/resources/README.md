# Chess contours

`chess-pieces.tex` contains native TikZ paths for six white and six black
pieces. Public syntax and placement are documented in
[the chess contract](../../../../vmshpwa/docs/tikz-chess.md).

The contours were derived offline from the author's 12 PNGs in the supplied
`ВМШ 5-7 2026-2027/pictures` directory, retaining their familiar appearance.
ImageMagick produced a silhouette from alpha and an ink mask over white
(threshold 50%); Potrace 1.16 traced these as Bézier paths (optimization
 tolerance 1). Coordinates preserve the original square canvas, normalized
 to −0.5…0.5. Each piece uses a white silhouette and a black ink layer with
 the even-odd fill rule. The original PNGs are not bundled or read at runtime.

These are editable TikZ coordinates; neither tracing tools nor a special font
are runtime dependencies. Preview PNGs under `vmshpwa/dev/assets/tikz-chess`
are documentation screenshots only.
