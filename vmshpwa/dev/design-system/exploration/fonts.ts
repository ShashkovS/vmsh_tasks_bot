/**
 * Self-hosted OFL faces used by the phase 1 candidates. Each package ships
 * `unicode-range` subsets, so a browser downloads only the Cyrillic and Latin
 * slices actually rendered (15–37 KB each). Phase 2 decides which single pair
 * survives, prunes the rest and moves the import into the app entry with a
 * precache rule.
 */
import '@fontsource-variable/inter/wght.css'
import '@fontsource-variable/literata/wght.css'
import '@fontsource-variable/literata/wght-italic.css'
import '@fontsource-variable/source-serif-4/wght.css'
import '@fontsource-variable/source-serif-4/wght-italic.css'
import '@fontsource-variable/golos-text/wght.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/pt-serif/400.css'
import '@fontsource/pt-serif/700.css'
import '@fontsource/pt-serif/400-italic.css'
