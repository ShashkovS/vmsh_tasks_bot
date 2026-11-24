"""Apply only the raster method delta to the actual deployed source.

Preserve production's newer diagnostics/TeX fixes; do not overwrite it with an
older checkout. Candidate is tested before install. See README.md.
"""
from pathlib import Path
import ast,hashlib
B=Path('/web/vmsh_tasks_bot');R=B/'image-stack'
source=B/'vmsh_tasks_bot/helpers/pwa/content/assets.py'
s=source.read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='656592162d3cc41d9c2909992d3d8c1d32d05d31afed0de87e43c5ca75f95914', 'Production source changed; rebase this small delta'
(R/'assets-before.py').write_text(s)
tree=ast.parse(s)
cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='ContentAssetConverter')
f=next(f for f in cls.body if isinstance(f,ast.AsyncFunctionDef) and f.name=='_raster_to_webp')
lines=s.splitlines(True);body=''.join(lines[f.lineno-1:f.end_lineno])
body=body.replace('            normalized_path = directory / "normalized.png"\n','')
body=body.replace('                    str(input_path),','                    f"{input_path}[0]",')
body=body.replace('                    str(normalized_path),','                    "-quality",\n                    "82",\n                    str(webp_path),',1)
start=body.index('            _assert_command_succeeded(')
end=body.index('        width, height = _webp_dimensions(webp)')
body=body[:start]+'''            # Direct HEIC -> WebP; docs/deploy/vmsh/image-stack/README.md.
            webp = _assert_command_succeeded(
                capability="image-normalization",
                return_code=normalize_result.return_code,
                output_path=webp_path,
                maximum_bytes=_MAX_WEBP_BYTES,
                server_diagnostics=_raster_command_diagnostics(
                    normalize_result, workdir=directory, executable=self.tools.magick,
                ),
            )
'''+body[end:]
assert 'normalized.png' not in body and 'self.tools.cwebp' not in body
s=''.join(lines[:f.lineno-1])+body+''.join(lines[f.end_lineno:])
s=s.replace('cwebp=_configured_tool(self._config, "cwebp_path"),','cwebp="",')
ast.parse(s)
(R/'assets-candidate.py').write_text(s)
print('Candidate staged; production file unchanged; diagnostics preserved')
