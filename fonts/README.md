# Thai font for PDF reports

The PDF calculation sheets in `reports/pdf_generator.py` use a Unicode
TrueType font so that Thai text renders correctly. The standard core
fonts bundled with `fpdf` are Latin-only.

## Required file

Place this file in **this folder** (`fonts/`):

```
fonts/THSarabunNew.ttf
```

Optional (used automatically if present) for bold / italic text:

```
fonts/THSarabunNew Bold.ttf
fonts/THSarabunNew Italic.ttf
fonts/THSarabunNew BoldItalic.ttf
```

If `THSarabunNew.ttf` is missing, the reports are still generated, but
Thai characters will not display correctly and the app shows a warning.

## Where to download

**TH Sarabun New** (recommended – official Thai national font, free):

- Thailand SIPA / Government release:
  https://www.f0nt.com/release/th-sarabun-new/
- Google Fonts mirror ("Sarabun", similar family):
  https://fonts.google.com/specimen/Sarabun
  (download the ZIP, then copy `Sarabun-Regular.ttf` and rename it to
  `THSarabunNew.ttf`, or edit `FONT_REGULAR` in `reports/pdf_generator.py`)

**Alternative – Tahoma** (already on most Windows machines, has Thai glyphs):

1. Copy `C:\Windows\Fonts\tahoma.ttf` into this folder.
2. Rename it to `THSarabunNew.ttf`
   *or* change `FONT_REGULAR` in `reports/pdf_generator.py` to point at
   `tahoma.ttf` and `FONT_BOLD` to `tahomabd.ttf`.

## After adding the font

Restart Streamlit (`streamlit run main.py`). The per-module warning
disappears and PDF downloads contain proper Thai text.
