# Editable v4 manual source

Edit `manual-content.json` for workflow pages and `capability-reference.json` for the control finder. Run `python docs/manual-source/render_manual.py` from the extension root to rebuild the PDF and Markdown manual. `page-map.json` is regenerated.

The renderer uses Python 3.10+, ReportLab and DejaVu Sans fonts from `/usr/share/fonts/truetype/dejavu`. Change the FONT path in the renderer on other systems. It reuses the Toolkit's own `js/assets/StudioHeaderTexture.png`. These authoring dependencies are not needed to run the Toolkit.

The PDF includes clickable contents and document bookmarks. The Markdown version provides searchable text and editable tables. The diagrams describe real connections; they are not screenshots of a Desktop session.
