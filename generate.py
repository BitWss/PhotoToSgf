# -*- coding: utf-8 -*-
import os
import re

PDF_ROOT = "pdfs"

def slugify(name):
    name = name.lower()
    lt_map = str.maketrans("ąčęėįšųūž", "aceeisuuz")
    name = name.translate(lt_map)
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name

def folder_to_title(folder):
    return folder.replace("-", " ").replace("_", " ")

def pdf_to_label(filename):
    name = os.path.splitext(filename)[0]
    return name.replace("-", " ").replace("_", " ")

# ── CSS ───────────────────────────────────────────────────────────────────────
SHARED_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #f4f6f9;
      color: #2c3e50;
      padding: 40px 20px;
    }
    h1 {
      text-align: center;
      font-size: 2rem;
      margin-bottom: 8px;
      color: #1a252f;
      letter-spacing: 0.03em;
    }
    .subtitle {
      text-align: center;
      font-size: 0.9rem;
      color: #95a5a6;
      margin-bottom: 40px;
      letter-spacing: 0.02em;
    }
    .back-link {
      display: inline-block;
      margin-bottom: 28px;
      font-size: 0.88rem;
      color: #2980b9;
      text-decoration: none;
      letter-spacing: 0.02em;
    }
    .back-link:hover { text-decoration: underline; }
    .section {
      background: #ffffff;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.07);
      margin-bottom: 28px;
      overflow: hidden;
    }
    .section-header {
      background: #1a252f;
      color: #f0f4f8;
      padding: 16px 24px;
      font-size: 1.05rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      transition: background 0.2s;
    }
    .section-header:hover { background: #2c3e50; }
    .section-header .arrow { transition: transform 0.3s; font-size: 0.75rem; opacity: 0.7; }
    .section-header.open .arrow { transform: rotate(180deg); }
    .section-body { display: none; padding: 24px; gap: 20px; flex-direction: column; }
    .section-body.open { display: flex; }
    .pdf-item { border: 1px solid #dce3ea; border-radius: 6px; overflow: hidden; }
    .pdf-label {
      background: #f0f4f8;
      padding: 10px 16px;
      font-weight: 600;
      font-size: 0.9rem;
      border-bottom: 1px solid #dce3ea;
      display: flex;
      justify-content: space-between;
      align-items: center;
      letter-spacing: 0.02em;
    }
    .pdf-label a { font-size: 0.82rem; color: #2980b9; text-decoration: none; font-weight: 400; }
    .pdf-label a:hover { text-decoration: underline; }
    iframe.pdf-viewer { width: 100%; height: 600px; border: none; display: block; }
"""

INDEX_EXTRA_CSS = """
    .classes-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 20px;
      margin-bottom: 40px;
    }
    .class-card {
      background: #ffffff;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.07);
      padding: 28px 24px;
      text-align: center;
      text-decoration: none;
      color: #1a252f;
      border-top: 3px solid #1a252f;
      transition: transform 0.15s, box-shadow 0.15s;
      display: block;
    }
    .class-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 18px rgba(0,0,0,0.11);
    }
    .class-card .card-title {
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .class-card .card-meta { font-size: 0.8rem; color: #95a5a6; }
    .feedback-box {
      background: #ffffff;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.07);
      padding: 32px;
      margin-bottom: 32px;
      border-top: 3px solid #1a252f;
    }
    .feedback-box h2 {
      font-size: 1.05rem;
      margin-bottom: 6px;
      color: #1a252f;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .feedback-box p { font-size: 0.88rem; color: #7f8c8d; margin-bottom: 18px; line-height: 1.5; }
    .feedback-box textarea {
      width: 100%; height: 110px; padding: 12px 14px;
      border: 1px solid #dce3ea; border-radius: 6px;
      font-family: inherit; font-size: 0.92rem; resize: vertical;
      outline: none; color: #2c3e50; transition: border-color 0.2s;
    }
    .feedback-box textarea:focus { border-color: #1a252f; }
    .feedback-box button {
      margin-top: 12px; padding: 10px 28px;
      background: #1a252f; color: #f0f4f8; border: none;
      border-radius: 6px; font-size: 0.9rem; font-weight: 600;
      letter-spacing: 0.05em; text-transform: uppercase;
      cursor: pointer; transition: background 0.2s;
    }
    .feedback-box button:hover { background: #2c3e50; }
    .feedback-note { margin-top: 10px; font-size: 0.78rem; color: #b0b8c1; }
"""

# ── Class page ────────────────────────────────────────────────────────────────
def build_class_page(class_folder, class_title, themes):
    sections_html = ""
    for theme_folder, pdfs in themes:
        theme_title = folder_to_title(theme_folder)
        pdf_items = ""
        for pdf in pdfs:
            path = f"{PDF_ROOT}/{class_folder}/{theme_folder}/{pdf}"
            label = pdf_to_label(pdf)
            pdf_items += f"""
      <div class="pdf-item">
        <div class="pdf-label">
          {label}
          <a href="{path}" target="_blank">Atsisiųsti</a>
        </div>
        <iframe class="pdf-viewer" src="{path}"></iframe>
      </div>"""

        sections_html += f"""
  <div class="section">
    <div class="section-header" onclick="toggleSection(this)">
      {theme_title}
      <span class="arrow">&#9660;</span>
    </div>
    <div class="section-body">
{pdf_items}
    </div>
  </div>
"""

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{class_title}</title>
  <style>{SHARED_CSS}  </style>
</head>
<body>

  <a class="back-link" href="index.html">&larr; Grįžti į pradžią</a>
  <h1>{class_title}</h1>
  <p class="subtitle">Pasirinkite temą</p>

{sections_html}
  <script>
    function toggleSection(header) {{
      header.classList.toggle('open');
      header.nextElementSibling.classList.toggle('open');
    }}
  </script>

</body>
</html>
"""

# ── index.html ────────────────────────────────────────────────────────────────
def build_index(classes):
    cards_html = ""
    for class_folder, class_title, slug, theme_count in classes:
        cards_html += f"""    <a class="class-card" href="{slug}.html">
      <div class="card-title">{class_title}</div>
      <div class="card-meta">{theme_count} tema{"" if theme_count == 1 else "s"}</div>
    </a>
"""

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Matematikos užduotys</title>
  <style>{SHARED_CSS}{INDEX_EXTRA_CSS}  </style>
</head>
<body>

  <h1>Matematikos užduotys</h1>
  <p class="subtitle">Pasirinkite klasę</p>

  <div class="classes-grid">
{cards_html}  </div>

  <div class="feedback-box">
    <h2>Pasiūlymai ir pastabos</h2>
    <p>Turite idėjų, ką pakeisti ar patobulinti? Rašykite – atsakysiu kuo greičiau.</p>
    <textarea id="feedbackText" placeholder="Jūsų žinutė..."></textarea>
    <br/>
    <button onclick="sendFeedback()">Siųsti</button>
    <p class="feedback-note">
      Paspaudus „Siųsti" atsidarys jūsų el. pašto programa su užpildyta žinute.
      Jūsų el. pašto adreso įvesti nereikia.
    </p>
  </div>

  <script>
    function sendFeedback() {{
      const msg = document.getElementById('feedbackText').value.trim();
      if (!msg) {{ alert('Prašome įvesti žinutę prieš siunčiant.'); return; }}
      const to      = 'simas.stockus@mif.stud.vu.lt';
      const subject = encodeURIComponent('Pastaba / pasiūlymas dėl svetainės');
      const body    = encodeURIComponent(msg);
      window.location.href = `mailto:${{to}}?subject=${{subject}}&body=${{body}}`;
    }}
  </script>

</body>
</html>
"""

# ── Main ──────────────────────────────────────────────────────────────────────
def build():
    if not os.path.isdir(PDF_ROOT):
        os.makedirs(PDF_ROOT)
        print(f"Sukurtas aplankas '{PDF_ROOT}/'. Pridėkite klasių aplankus su temų poaplankiais.")
        return

    class_folders = sorted([
        f for f in os.listdir(PDF_ROOT)
        if os.path.isdir(os.path.join(PDF_ROOT, f))
    ])

    if not class_folders:
        print("Nerasta klasių aplankų aplanke pdfs/.")
        return

    index_classes = []

    for class_folder in class_folders:
        class_path = os.path.join(PDF_ROOT, class_folder)
        class_title = folder_to_title(class_folder)
        slug = slugify(class_folder)

        theme_folders = sorted([
            t for t in os.listdir(class_path)
            if os.path.isdir(os.path.join(class_path, t))
        ])

        themes = []
        for theme_folder in theme_folders:
            theme_path = os.path.join(class_path, theme_folder)
            pdfs = sorted([
                f for f in os.listdir(theme_path)
                if f.lower().endswith(".pdf")
            ])
            themes.append((theme_folder, pdfs))

        page_html = build_class_page(class_folder, class_title, themes)
        filename = f"{slug}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(page_html)

        index_classes.append((class_folder, class_title, slug, len(themes)))
        print(f"  Sugeneruota: {filename}  ({len(themes)} temos)")

    index_html = build_index(index_classes)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"\nindex.html sugeneruotas. Klasių skaičius: {len(class_folders)}.")

if __name__ == "__main__":
    build()
