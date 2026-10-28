# Small logo and browser icon

Created with built-in image generation using `icon.png` as the reference.
The original large application icon is preserved.

- `favicon-source.png`: generated simplified transparent logo.
- `icon-small.png`: 32px PNG version.
- `app-icon.png`: 256px PNG used by the web header and UNRAID template.
- `favicon.ico`: PNG-backed ICO entries at 16, 24, 32, 48, 64, 128 and 256px.

Run `tools/build-favicon.ps1` on Windows to reproduce the PNG size and ICO encoding.

## Generation prompt

Use case: logo-brand. Edit this reference application logo into a radically simplified favicon version that remains clear at 16x16 and 32x32 pixels. Preserve the essential orange front-view 3D printer frame, central nozzle, small orange printed cube, and green status dot at bottom right. Use extremely bold flat geometric shapes, a thick orange squared arch and dark charcoal base, ample clear negative space. Remove all screws, rails, fan spokes, wire loops, reflections, texture, shadows, chrome and small details. Green status dot should be a single simple solid green circle with charcoal outline. No text or letters. Square composition nearly fills canvas with slight transparent padding, genuine transparent background. One single icon, not multiple sizes or contact sheet. This is the compact tab-bar version of the supplied logo, with strong orange silhouette readable on both dark and light browser tabs.
