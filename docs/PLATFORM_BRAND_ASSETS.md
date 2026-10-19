# Platform identity assets

The local SVGs in `static/brands/` are derived from [Simple Icons 15.0.0](https://github.com/simple-icons/simple-icons/tree/15.0.0/icons), distributed under [CC0-1.0](https://github.com/simple-icons/simple-icons/blob/15.0.0/LICENSE.md). Brand trademarks remain the property of their respective owners. These marks identify data providers; they do not imply affiliation or a working integration.

Files: `facebook.svg`, `meta.svg`, `tiktok.svg`, `google.svg`, `googleanalytics.svg`, `googlesearchconsole.svg`, `googlesheets.svg`, `youtube.svg`.

Each SVG retains the upstream path geometry, with a fixed fill color. Only SVG/path geometry is copied; scripts, external references and embedded resources are not accepted. Google is rendered in blue; other marks use their corresponding single-color brand treatment. The frontend serves all assets locally and never fetches a logo from a provider or CDN.

`platformLogo()` in `static/ui.js` maps existing source identifiers to an explicit filename allowlist. Unknown identifiers get a generic icon. Logos are decorative beside visible text, with empty alt text and fixed dimensions. Connection, permission, sync and verification states continue to come from existing API responses.
