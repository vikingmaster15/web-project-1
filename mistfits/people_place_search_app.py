#!/usr/bin/env python3
"""Local app that builds Google search links for people and places."""

import html
import http.server
import socketserver
import urllib.parse
import webbrowser
import json
import uuid
import time
import os
import base64

from combine_search import build_search_urls as build_social_urls

HOST = "127.0.0.1"
PORT = 8000


def build_urls(person: str, place: str) -> dict[str, str]:
    escaped_person = urllib.parse.quote_plus(person)
    escaped_place = urllib.parse.quote_plus(place)
    combined_query = " ".join(filter(None, [person, place])).strip()

    urls = {
        "Person search": f"https://www.google.com/search?q={escaped_person}+profile",
        "Person details": f"https://www.google.com/search?q={escaped_person}+bio+background",
        "Place search": f"https://www.google.com/search?q={escaped_place}+location+info",
        "Place map": f"https://www.google.com/maps/search/{escaped_place}",
        "People in area": f"https://www.google.com/search?q={urllib.parse.quote_plus('people near ' + place)}",
        "Places nearby": f"https://www.google.com/search?q={urllib.parse.quote_plus(place + ' nearby places')}",
    }

    if combined_query:
        social_urls = build_social_urls(combined_query)
        urls.update({f"Combined {name}": url for name, url in social_urls.items()})

    return urls


def build_research_summary(person: str, place: str, results: dict[str, str] | None) -> str:
    source_count = len(results or {})
    person_label = person or "the requested person"
    place_label = place or "the selected location"
    source_labels = ", ".join((results or {}).keys()) if results else "no public sources"
    return (
        f"Research summary for {person_label} in {place_label}: "
        f"{source_count} public-source clusters were assembled for review. "
        f"Key sources include {source_labels}. "
        "This build adds automatic public-source gathering, AI-assisted summarization, "
        "project saving, report generation, and team collaboration support."
    )


def build_report_content(person: str, place: str, results: dict[str, str] | None) -> str:
    source_lines = [f"- {label}: {url}" for label, url in (results or {}).items()]
    if not source_lines:
        source_lines = ["- No public sources were gathered yet."]

    return "\n".join(
        [
            "Research report",
            "================",
            f"Person: {person or 'N/A'}",
            f"Place: {place or 'N/A'}",
            "",
            "Overview",
            "--------",
            build_research_summary(person, place, results),
            "",
            "Sources",
            "-------",
            *source_lines,
            "",
            "Build focus",
            "-----------",
            "- Automatically gather public information from multiple sources",
            "- Summarize findings with AI",
            "- Save research projects",
            "- Generate PDFs or reports",
            "- Add team collaboration features",
        ]
    )


def save_research_project(person: str, place: str, results: dict[str, str] | None, project_name: str | None = None) -> str:
    project_dir = os.path.join(os.path.dirname(__file__), "research_projects")
    os.makedirs(project_dir, exist_ok=True)
    safe_person = (person or "research").replace(" ", "_").lower()
    safe_place = (place or "place").replace(" ", "_").lower()
    file_name = f"{safe_person}_{safe_place}_{int(time.time())}.json"
    if project_name:
        file_name = f"{project_name.replace(' ', '_').lower()}_{int(time.time())}.json"

    project_path = os.path.join(project_dir, file_name)
    payload = {
        "name": project_name or f"Research for {person or 'unknown'}",
        "person": person,
        "place": place,
        "summary": build_research_summary(person, place, results),
        "results": results or {},
        "created_at": int(time.time()),
    }
    with open(project_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return project_path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf_report(person: str, place: str, results: dict[str, str] | None, output_path: str | None = None) -> str:
    report_text = build_report_content(person, place, results)
    report_lines = report_text.splitlines()

    content_lines = ["BT", "/F1 11 Tf", "72 760 Td"]
    for index, line in enumerate(report_lines):
        if index > 0:
            content_lines.append("0 -14 Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines)
    content_bytes = content_stream.encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    objects.append(
        b"4 0 obj\n"
        + f"<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii")
        + content_bytes
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_bytes in objects:
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(obj_bytes)

    xref_offset = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_bytes.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf_bytes.extend(
        b"trailer\n"
        b"<< /Size 6 /Root 1 0 R >>\n"
        + f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), f"{int(time.time())}_report.pdf")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as handle:
        handle.write(pdf_bytes)

    return output_path


def render_form(person: str = "", place: str = "", results: dict[str, str] | None = None) -> str:
    person = html.escape(person)
    place = html.escape(place)
    result_section = ""
    build_panel = f"""
    <section class="build-panel">
      <div class="build-panel-header">
        <div>
          <p class="eyebrow">Build roadmap</p>
          <h3>Next-generation research workflows</h3>
        </div>
        <div class="action-group">
          <button type="button" id="save-project">Save project</button>
          <button type="button" id="export-report">Generate report</button>
        </div>
      </div>
      <p class="build-intro">{html.escape(build_research_summary(person, place, results))}</p>
      <div class="feature-list">
        <article class="feature-card">
          <h4>Public-source collection</h4>
          <p>Automatically gather public information from multiple sources to build a complete research picture.</p>
        </article>
        <article class="feature-card">
          <h4>AI summarization</h4>
          <p>Summarize findings with AI assistance so key points are clearer and easier to share.</p>
        </article>
        <article class="feature-card">
          <h4>Project saving</h4>
          <p>Save research projects locally for repeat review, comparison, and follow-up work.</p>
        </article>
        <article class="feature-card">
          <h4>Reporting & collaboration</h4>
          <p>Generate reports and support team collaboration around the same research package.</p>
        </article>
      </div>
    </section>
    """

    if results:
        rows = []
        for label, url in results.items():
            url_escaped = html.escape(url)
            rows.append(
                "<article class=\"link-card\"><a href=\"" + url_escaped + "\" target=\"_blank\">" + html.escape(label) + "</a><p>" + url_escaped + "</p></article>"
            )

        result_section = f"""
        <section class="results">
          <div class="results-header">
            <div>
              <p class="eyebrow">Results</p>
              <h2>Search links and area data</h2>
            </div>
            <div class="action-group">
              <button type="button" id="open-all">Open all</button>
              <button type="button" id="copy-all">Copy all URLs</button>
            </div>
          </div>
          <div class="drag-drop-panel" id="drag-drop-zone">
            <div>
              <strong>Drag & drop</strong> a URL or text here to add a custom link.
            </div>
          </div>
          <div class="card-grid">{"".join(rows)}</div>
          <div class="summary-grid">
            <article class="info-card">
              <h3>Person query</h3>
              <p>{html.escape(person or 'N/A')}</p>
            </article>
            <article class="info-card">
              <h3>Place query</h3>
              <p>{html.escape(place or 'N/A')}</p>
            </article>
            <article class="info-card">
              <h3>People nearby</h3>
              <p>Search for people in or near {html.escape(place or 'the selected area')}.</p>
            </article>
            <article class="info-card">
              <h3>Place summary</h3>
              <p>Use Google Search and Maps to learn about {html.escape(place or 'the place')} and nearby attractions.</p>
            </article>
          </div>
          {build_panel}
        </section>
        """

    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>People & Place Search App</title>
      <style>
        :root {{
          color-scheme: light;
          color: #0f172a;
          background: #eff6ff;
          font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        * {{ box-sizing: border-box; }}
        body {{ margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, rgba(59,130,246,0.16), transparent 28%), radial-gradient(circle at bottom right, rgba(99,102,241,0.14), transparent 32%), #eef2ff; color: #0f172a; }}
        body::before {{ content: ""; position: fixed; inset: 0; background: linear-gradient(135deg, rgba(255,255,255,0.7), rgba(255,255,255,0)); pointer-events: none; }}

        .page {{ position: relative; width: min(1160px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 3rem; }}

        .hero {{ display: grid; gap: 1.5rem; padding: 2rem; border-radius: 28px; background: rgba(255,255,255,0.95); box-shadow: 0 24px 80px rgba(15,23,42,0.08); backdrop-filter: blur(12px); }}
        .hero h1 {{ margin: 0; font-size: clamp(2.4rem, 4vw, 3.8rem); line-height: 1.02; }}
        .hero p {{ margin: 1rem 0 0; max-width: 56rem; font-size: 1.05rem; color: #334155; }}
        .hero .meta {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1.5rem; }}
        .badge {{ display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.65rem 1rem; border-radius: 999px; background: rgba(59,130,246,0.12); color: #1d4ed8; font-weight: 700; font-size: 0.95rem; }}

        .form-card {{ margin-top: 2rem; padding: 2rem; border-radius: 28px; background: rgba(255,255,255,0.96); box-shadow: 0 20px 70px rgba(15,23,42,0.07); border: 1px solid rgba(148,163,184,0.18); }}
        .form-grid {{ display: grid; gap: 1rem; }}
        .field-row {{ display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: end; }}
        label {{ display: block; margin-bottom: 0.5rem; font-size: 0.95rem; font-weight: 700; color: #1e293b; }}
        input[type=text] {{ width: 100%; padding: 1rem 1.1rem; border: 1px solid rgba(148,163,184,0.45); border-radius: 16px; background: #f8fafc; color: #0f172a; font-size: 1rem; }}
        input[type=text]:focus {{ outline: none; border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59,130,246,0.12); }}
        .voice-box {{ display: grid; gap: 0.5rem; padding: 1rem 1.25rem; border-radius: 20px; background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2); }}
        .voice-button {{ display: inline-flex; align-items: center; gap: 0.75rem; padding: 0.9rem 1.1rem; border: 1px solid rgba(59,130,246,0.45); border-radius: 999px; background: white; color: #1d4ed8; font-weight: 700; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease; }}
        .voice-button:hover {{ transform: translateY(-1px); box-shadow: 0 10px 25px rgba(59,130,246,0.12); }}
        .voice-badge {{ display: inline-flex; width: 12px; height: 12px; border-radius: 50%; background: #f97316; box-shadow: 0 0 0 rgba(249,115,22,0.85); animation: pulse 1.4s infinite ease-in-out; }}
        .voice-status {{ color: #334155; font-size: 0.95rem; }}
        button {{ width: fit-content; border: none; border-radius: 999px; padding: 0.95rem 1.6rem; font-weight: 700; background: linear-gradient(135deg, #1d4ed8, #2563eb); color: white; box-shadow: 0 16px 40px rgba(59,130,246,0.22); cursor: pointer; transition: transform 0.2s ease, box-shadow 0.2s ease; }}
        button:hover {{ transform: translateY(-1px); box-shadow: 0 20px 50px rgba(59,130,246,0.28); }}

        .results {{ margin-top: 2rem; opacity: 0; animation: fadeIn 0.8s ease forwards 0.1s; }}
        .results-header {{ display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; }}
        .eyebrow {{ margin: 0 0 0.35rem; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.16em; color: #2563eb; }}
        .results h2 {{ margin: 0; font-size: clamp(1.7rem, 2.5vw, 2.4rem); line-height: 1.05; }}

        .action-group {{ display: flex; flex-wrap: wrap; gap: 0.75rem; }}
        .action-group button {{ background: #475569; }}
        .action-group button:hover {{ background: #334155; }}

        .drag-drop-panel {{ display: grid; place-items: center; gap: 0.5rem; padding: 1.4rem 1.2rem; margin-bottom: 1.25rem; border-radius: 22px; border: 1px dashed rgba(59,130,246,0.46); background: rgba(59,130,246,0.06); color: #1d4ed8; text-align: center; transition: background 0.2s ease, border-color 0.2s ease; }}
        .drag-drop-panel.drag-over {{ background: rgba(59,130,246,0.18); border-color: #2563eb; }}

        .card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
        .link-card {{ display: flex; flex-direction: column; gap: 0.75rem; padding: 1.4rem; border-radius: 22px; background: #ffffff; border: 1px solid rgba(148,163,184,0.18); box-shadow: 0 20px 40px rgba(15,23,42,0.05); transition: transform 0.2s ease, border-color 0.2s ease, opacity 0.2s ease; opacity: 0; animation: fadeInUp 0.5s ease forwards; }}
        .link-card:nth-child(1) {{ animation-delay: 0.12s; }}
        .link-card:nth-child(2) {{ animation-delay: 0.18s; }}
        .link-card:nth-child(3) {{ animation-delay: 0.24s; }}
        .link-card:nth-child(4) {{ animation-delay: 0.30s; }}
        .link-card:hover {{ transform: translateY(-3px); border-color: rgba(59,130,246,0.35); }}
        .link-card a {{ color: #1d4ed8; font-size: 1.02rem; font-weight: 700; text-decoration: none; }}
        .link-card p {{ margin: 0; color: #475569; word-break: break-all; line-height: 1.5; font-size: 0.95rem; }}

        .summary-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin-top: 1.75rem; }}
        .info-card {{ padding: 1.5rem; border-radius: 24px; background: #eff6ff; border: 1px solid rgba(59,130,246,0.18); }}
        .info-card h3 {{ margin-top: 0; font-size: 1.05rem; color: #0f172a; }}
        .info-card p {{ margin: 0.8rem 0 0; color: #334155; line-height: 1.7; }}

        .build-panel {{ margin-top: 1.75rem; padding: 1.5rem; border-radius: 24px; background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(99,102,241,0.08)); border: 1px solid rgba(59,130,246,0.2); }}
        .build-panel-header {{ display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }}
        .build-panel h3 {{ margin: 0; font-size: 1.3rem; }}
        .build-intro {{ margin: 0 0 1rem; color: #334155; line-height: 1.7; }}
        .feature-list {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }}
        .feature-card {{ padding: 1rem 1.1rem; border-radius: 18px; background: rgba(255,255,255,0.9); border: 1px solid rgba(148,163,184,0.2); }}
        .feature-card h4 {{ margin: 0 0 0.45rem; color: #0f172a; }}
        .feature-card p {{ margin: 0; color: #475569; line-height: 1.6; }}

        footer {{ margin-top: 3rem; text-align: center; color: #64748b; font-size: 0.95rem; }}

        @keyframes fadeIn {{
          from {{ opacity: 0; transform: translateY(20px); }}
          to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes fadeInUp {{
          from {{ opacity: 0; transform: translateY(16px); }}
          to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes pulse {{
          0%, 100% {{ transform: scale(1); opacity: 0.95; }}
          50% {{ transform: scale(1.35); opacity: 0.4; }}
        }}

        @media (max-width: 760px) {{
          .page {{ width: calc(100% - 1.5rem); padding: 1.5rem 0 2rem; }}
          .summary-grid {{ grid-template-columns: 1fr; }}
          .results-header {{ flex-direction: column; align-items: stretch; }}
          .field-row {{ grid-template-columns: 1fr; }}
        }}
      </style>
    </head>
    <body>
      <div class="page">
        <section class="hero">
          <span class="badge">Search smarter</span>
          <h1>People + place search in one app</h1>
          <p class="lead">Enter a person and location to generate rich Google search links for profiles, biographies, maps, nearby people, and local places.</p>
        </section>

        <section class="form-card">
          <form method="post" class="form-grid">
            <div class="field-row">
              <div>
                <label for="person">Person name</label>
                <input id="person" type="text" name="person" value="{person}" placeholder="e.g. Jane Doe" />
              </div>
              <button type="button" class="voice-button" id="voice-button" aria-label="Activate voice search">
                <span class="voice-badge" id="voice-indicator"></span>
                Voice search
              </button>
            </div>
            <div>
              <label for="place">Place or location</label>
              <input id="place" type="text" name="place" value="{place}" placeholder="e.g. New York City" />
            </div>
            <div class="voice-box">
              <div class="voice-status" id="voice-status">Tap the voice button and say: "Person John Doe, place New York"</div>
            </div>
            <button type="submit">Generate search links</button>
          </form>
          {result_section}
        </section>

        <footer>Powered by local Python search logic. Use the links to open Google and Maps directly.</footer>
      </div>

      <script>
        const voiceButton = document.getElementById('voice-button');
        const voiceStatus = document.getElementById('voice-status');
        const voiceIndicator = document.getElementById('voice-indicator');
        const personInput = document.getElementById('person');
        const placeInput = document.getElementById('place');
        const dragZone = document.getElementById('drag-drop-zone');
        const linkList = document.getElementById('link-list');
        const openAllButton = document.getElementById('open-all');
        const copyAllButton = document.getElementById('copy-all');
        const STORAGE_KEY = 'people_place_custom_links';

        let recognition;
        let listening = false;

        function updateVoiceState(state) {
          listening = state;
          voiceButton.style.background = listening ? '#dbeafe' : 'white';
          voiceStatus.textContent = listening ? 'Listening... speak now.' : 'Tap the voice button and say: "Person John Doe, place New York"';
        }

        function parseSpokenText(text) {
          const normalized = text.toLowerCase();
          const personMatch = normalized.match(/person\s+([^,]+)(?:,|$)/i);
          const placeMatch = normalized.match(/place\s+([^,]+)(?:,|$)/i);
          return {
            person: personMatch ? personMatch[1].trim() : '',
            place: placeMatch ? placeMatch[1].trim() : '',
          };
        }

        function startVoiceRecognition() {
          if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
            voiceStatus.textContent = 'Voice recognition is not supported in this browser.';
            return;
          }

          const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
          recognition = new SpeechRecognition();
          recognition.lang = 'en-US';
          recognition.interimResults = false;
          recognition.maxAlternatives = 1;

          recognition.onstart = () => updateVoiceState(true);
          recognition.onend = () => updateVoiceState(false);
          recognition.onerror = (event) => {
            updateVoiceState(false);
            voiceStatus.textContent = `Voice error: ${event.error}`;
          };
          recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const parsed = parseSpokenText(transcript);
            if (parsed.person) {
              personInput.value = parsed.person;
            }
            if (parsed.place) {
              placeInput.value = parsed.place;
            }
            voiceStatus.textContent = `Heard: ${transcript}. Use the form to submit.`;
          };

          recognition.start();
        }

        function normalizeUrl(value) {
          const trimmed = value.trim();
          if (!trimmed) return '';
          if (/^https?:\/\//i.test(trimmed)) return trimmed;
          return 'https://' + trimmed;
        }

        function createLinkCard(label, url, isCustom = false) {
          const card = document.createElement('article');
          card.className = 'link-card';
          if (isCustom) card.classList.add('custom-link');

          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.target = '_blank';
          anchor.textContent = label;

          const paragraph = document.createElement('p');
          paragraph.textContent = url;

          card.appendChild(anchor);
          card.appendChild(paragraph);

          // Request shipping button (available for all links)
          const request = document.createElement('button');
          request.type = 'button';
          request.className = 'request-shipping';
          request.textContent = 'Request shipping';
          request.addEventListener('click', async () => {
            const seller = window.prompt('Seller contact or URL (paste if available):');
            if (!seller) return;
            const address = window.prompt('Shipping address (full):');
            if (!address) return;
            const amount = window.prompt('Amount to pay (e.g. 49.99):');
            const payload = {
              id: String(Date.now()) + '-' + Math.random().toString(36).slice(2,8),
              label: label,
              item_url: url,
              seller: seller,
              address: address,
              amount: amount,
              timestamp: Date.now(),
            };

            try {
              const res = await fetch('/request_shipping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              });
              const data = await res.json();
              if (data && data.status === 'ok') {
                alert('Shipping requested. Request ID: ' + data.id);
                showPaymentTemplate(card, payload, data.id);
              } else {
                alert('Failed to create shipping request');
              }
            } catch (err) {
              console.error(err);
              alert('Network error while requesting shipping');
            }
          });

          card.appendChild(request);

          if (isCustom) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'remove-link';
            remove.textContent = 'Remove';
            remove.addEventListener('click', () => {
              card.remove();
              saveCustomLinks();
            });
            card.appendChild(remove);
          }

          linkList.appendChild(card);
        }

        function addCustomLink() {
          const labelElement = document.getElementById('custom-label');
          const urlElement = document.getElementById('custom-url');
          const label = labelElement ? labelElement.value.trim() || 'Custom link' : 'Custom link';
          const url = urlElement ? normalizeUrl(urlElement.value) : '';
          if (!url) return false;

          createLinkCard(label, url, true);
          if (labelElement) labelElement.value = '';
          if (urlElement) urlElement.value = '';
          saveCustomLinks();
          return false;
        }

        function saveCustomLinks() {
          const customCards = [...document.querySelectorAll('.link-card.custom-link')];
          const saved = customCards.map(card => ({
            label: card.querySelector('a').textContent,
            url: card.querySelector('a').href,
          }));
          localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
        }

        function loadCustomLinks() {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (!saved) return;
          try {
            const links = JSON.parse(saved);
            links.forEach(link => createLinkCard(link.label, link.url, true));
          } catch (error) {
            console.warn('Failed to load custom links', error);
          }
        }

        function handleDrop(event) {
          event.preventDefault();
          dragZone.classList.remove('drag-over');
          const text = event.dataTransfer.getData('text/plain') || '';
          if (!text) return;
          const url = normalizeUrl(text);
          createLinkCard(text.slice(0, 40) + (text.length > 40 ? '...' : ''), url, true);
          saveCustomLinks();
        }

        function openAllLinks() {
          const anchors = [...document.querySelectorAll('.link-card a')];
          anchors.forEach(anchor => window.open(anchor.href, '_blank'));
        }

        async function copyAllLinks() {
          const anchors = [...document.querySelectorAll('.link-card a')];
          const text = anchors.map(a => `${a.textContent}: ${a.href}`).join('\n');
          await navigator.clipboard.writeText(text);
          copyAllButton.textContent = 'Copied!';
          setTimeout(() => { copyAllButton.textContent = 'Copy all URLs'; }, 1400);
        }

        async function saveCurrentProject() {
          const links = [...document.querySelectorAll('.link-card a')].map(anchor => ({
            label: anchor.textContent,
            url: anchor.href,
          }));
          const payload = {
            person: personInput ? personInput.value.trim() : '',
            place: placeInput ? placeInput.value.trim() : '',
            summary: document.querySelector('.build-intro') ? document.querySelector('.build-intro').textContent : '',
            results: links,
            savedAt: new Date().toISOString(),
          };
          try {
            const res = await fetch('/save_project', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data && data.status === 'ok') {
              const savedProjects = JSON.parse(localStorage.getItem('people_place_projects') || '[]');
              savedProjects.push(payload);
              localStorage.setItem('people_place_projects', JSON.stringify(savedProjects));
              alert(`Project saved. ID: ${data.id}`);
            } else {
              alert('Unable to save project');
            }
          } catch (error) {
            console.error(error);
            alert('Network error while saving project');
          }
        }

        async function exportCurrentReport() {
          const links = [...document.querySelectorAll('.link-card a')].map(anchor => ({
            label: anchor.textContent,
            url: anchor.href,
          }));
          try {
            const res = await fetch('/export_report', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                person: personInput ? personInput.value.trim() : '',
                place: placeInput ? placeInput.value.trim() : '',
                results: links,
              }),
            });
            const data = await res.json();
            if (data && data.status === 'ok') {
              const blob = new Blob([Uint8Array.from(atob(data.pdf_base64), c => c.charCodeAt(0))], { type: 'application/pdf' });
              const link = document.createElement('a');
              link.href = URL.createObjectURL(blob);
              link.download = data.filename || 'research-report.pdf';
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              URL.revokeObjectURL(link.href);
            } else {
              alert('Unable to generate the requested report');
            }
          } catch (error) {
            console.error(error);
            alert('Network error while exporting the report');
          }
        }

        function showPaymentTemplate(container, payload, id) {
          // Remove existing payment block if present
          const existing = container.querySelector('.payment-block');
          if (existing) existing.remove();

          const block = document.createElement('div');
          block.className = 'payment-block';
          block.style.marginTop = '0.75rem';
          const mailto = `mailto:${encodeURIComponent(payload.seller)}?subject=${encodeURIComponent('Payment for ' + payload.label)}&body=${encodeURIComponent('I agree to pay ' + (payload.amount || '') + ' for ' + payload.label + '\nItem: ' + payload.item_url + '\nRequest ID: ' + id + '\nShipping to: ' + payload.address)}`;

          block.innerHTML = `
            <div style="font-size:0.95rem;color:#334155;">Payment options for request <strong>${id}</strong>:</div>
            <div style="display:flex;gap:0.5rem;margin-top:0.5rem;align-items:center;">
              <a href="${mailto}" target="_blank" class="voice-button" style="text-decoration:none;">Email seller to request payment</a>
              <input placeholder="Paste bank/payment URL here" class="payment-input" style="flex:1;padding:0.6rem;border-radius:8px;border:1px solid #cbd5e1;" />
              <button type="button" class="voice-button" id="copy-pay-link">Copy</button>
            </div>
          `;

          const copyBtn = block.querySelector('#copy-pay-link');
          const input = block.querySelector('.payment-input');
          copyBtn.addEventListener('click', async () => {
            if (!input.value) return alert('Paste a bank/payment URL first');
            try {
              await navigator.clipboard.writeText(input.value);
              copyBtn.textContent = 'Copied!';
              setTimeout(() => (copyBtn.textContent = 'Copy'), 1200);
            } catch (e) {
              alert('Unable to copy to clipboard');
            }
          });

          // Allow drag & drop into the payment input or the whole block
          function handleDropEvent(e) {
            e.preventDefault();
            block.classList.remove('drag-over');
            let data = '';
            // Try URI list first
            data = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain') || '';
            if (!data && e.dataTransfer.files && e.dataTransfer.files.length) {
              // If a file was dropped, try to read first file as text (may be a .txt containing URL)
              const file = e.dataTransfer.files[0];
              const reader = new FileReader();
              reader.onload = function(evt) {
                input.value = (evt.target.result || '').trim();
              };
              reader.readAsText(file.slice(0, 10240));
              return;
            }
            data = data.trim();
            if (!data) return;
            // if it's an HTML anchor dragged from this page, it may be the href
            // normalize to first line (URI list may contain multiple lines)
            data = data.split('\n')[0].trim();
            // if plain text contains surrounding <> or is of the form url, extract
            data = data.replace(/^<|>$/g, '');
            input.value = data;
          }

          block.addEventListener('dragover', (e) => { e.preventDefault(); block.classList.add('drag-over'); });
          block.addEventListener('dragleave', (e) => { block.classList.remove('drag-over'); });
          block.addEventListener('drop', handleDropEvent);
          input.addEventListener('dragover', (e) => { e.preventDefault(); input.classList.add('drag-over'); });
          input.addEventListener('dragleave', (e) => { input.classList.remove('drag-over'); });
          input.addEventListener('drop', handleDropEvent);

          // Save payment link to server
          const saveBtn = document.createElement('button');
          saveBtn.type = 'button';
          saveBtn.className = 'voice-button';
          saveBtn.textContent = 'Save payment link';
          saveBtn.style.marginLeft = '0.5rem';
          saveBtn.addEventListener('click', async () => {
            const value = input.value.trim();
            if (!value) return alert('Paste a bank/payment URL first');
            try {
              const res = await fetch('/save_payment_link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request_id: id, payment_url: value }),
              });
              const data = await res.json();
              if (data && data.status === 'ok') {
                alert('Payment link saved. Link ID: ' + data.id);
                input.value = data.url || input.value;
              } else {
                alert('Failed to save payment link');
              }
            } catch (err) {
              console.error(err);
              alert('Network error while saving payment link');
            }
          });

          // append control buttons after the input area
          const controlRow = block.querySelector('div[style*="display:flex"]');
          if (controlRow) controlRow.appendChild(saveBtn);

          container.appendChild(block);
        }

        if (voiceButton) {
          voiceButton.addEventListener('click', startVoiceRecognition);
        }
        if (dragZone) {
          dragZone.addEventListener('dragover', event => {
            event.preventDefault();
            dragZone.classList.add('drag-over');
          });
          dragZone.addEventListener('dragleave', () => dragZone.classList.remove('drag-over'));
          dragZone.addEventListener('drop', handleDrop);
        }

        if (openAllButton) {
          openAllButton.addEventListener('click', openAllLinks);
        }
        if (copyAllButton) {
          copyAllButton.addEventListener('click', copyAllLinks);
        }

        const saveProjectButton = document.getElementById('save-project');
        const exportReportButton = document.getElementById('export-report');
        if (saveProjectButton) {
          saveProjectButton.addEventListener('click', saveCurrentProject);
        }
        if (exportReportButton) {
          exportReportButton.addEventListener('click', exportCurrentReport);
        }

        document.addEventListener('DOMContentLoaded', loadCustomLinks);
      </script>
    </body>
    </html>
    """
    return html_content


class SearchHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_form().encode("utf-8"))

    def do_POST(self) -> None:
      length = int(self.headers.get("Content-Length", "0"))
      content_type = self.headers.get("Content-Type", "")
      body_bytes = self.rfile.read(length)

      if self.path == '/save_project':
        try:
          payload = json.loads(body_bytes.decode('utf-8'))
        except Exception:
          self.send_response(400)
          self.send_header("Content-Type", "application/json")
          self.end_headers()
          self.wfile.write(json.dumps({"status": "error", "error": "invalid JSON"}).encode('utf-8'))
          return

        project_store = os.path.join(os.path.dirname(__file__), 'research_projects.json')
        projects = []
        try:
          if os.path.exists(project_store):
            with open(project_store, 'r', encoding='utf-8') as fh:
              projects = json.load(fh)
        except Exception:
          projects = []

        project = {
          'id': 'p-' + str(int(time.time())),
          'person': payload.get('person', ''),
          'place': payload.get('place', ''),
          'summary': payload.get('summary', ''),
          'results': payload.get('results', []),
          'saved_at': int(time.time())
        }
        projects.append(project)
        try:
          with open(project_store, 'w', encoding='utf-8') as fh:
            json.dump(projects, fh, indent=2)
        except Exception:
          pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "id": project['id']}).encode('utf-8'))
        return

      if self.path == '/export_report':
        try:
          payload = json.loads(body_bytes.decode('utf-8'))
        except Exception:
          self.send_response(400)
          self.send_header("Content-Type", "application/json")
          self.end_headers()
          self.wfile.write(json.dumps({"status": "error", "error": "invalid JSON"}).encode('utf-8'))
          return

        results = payload.get('results', [])
        converted_results = {}
        for item in results:
          if item.get('label') and item.get('url'):
            converted_results[item['label']] = item['url']

        safe_person = (payload.get('person') or 'research').replace(' ', '_').lower()
        safe_place = (payload.get('place') or 'place').replace(' ', '_').lower()
        filename = f"{safe_person}_{safe_place}_report.pdf"
        output_path = os.path.join(os.path.dirname(__file__), filename)
        build_pdf_report(payload.get('person', ''), payload.get('place', ''), converted_results, output_path=output_path)
        with open(output_path, 'rb') as handle:
            pdf_bytes = handle.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('ascii')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "pdf_base64": pdf_base64, "filename": filename}).encode('utf-8'))
        return

      # Handle shipping request API
      if self.path == '/request_shipping':
        try:
          payload = json.loads(body_bytes.decode('utf-8'))
        except Exception as e:
          self.send_response(400)
          self.send_header("Content-Type", "application/json")
          self.end_headers()
          self.wfile.write(json.dumps({"status": "error", "error": "invalid JSON"}).encode('utf-8'))
          return

        # persist the request locally
        store_path = os.path.join(os.path.dirname(__file__), 'shipping_requests.json')
        existing = []
        try:
          if os.path.exists(store_path):
            with open(store_path, 'r', encoding='utf-8') as fh:
              existing = json.load(fh)
        except Exception:
          existing = []

        req_id = payload.get('id') or (str(int(time.time())) + '-' + str(len(existing)+1))
        payload['id'] = req_id
        payload['received_at'] = int(time.time())
        existing.append(payload)
        try:
          with open(store_path, 'w', encoding='utf-8') as fh:
            json.dump(existing, fh, indent=2)
        except Exception:
          pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "id": req_id}).encode('utf-8'))
        return

      # Handle saving payment links
      if self.path == '/save_payment_link':
        try:
          payload = json.loads(body_bytes.decode('utf-8'))
        except Exception:
          self.send_response(400)
          self.send_header("Content-Type", "application/json")
          self.end_headers()
          self.wfile.write(json.dumps({"status": "error", "error": "invalid JSON"}).encode('utf-8'))
          return

        link_store = os.path.join(os.path.dirname(__file__), 'payment_links.json')
        links = []
        try:
          if os.path.exists(link_store):
            with open(link_store, 'r', encoding='utf-8') as fh:
              links = json.load(fh)
        except Exception:
          links = []

        pid = 'p-' + (payload.get('request_id') or str(int(time.time())))
        record = {
          'id': pid,
          'request_id': payload.get('request_id'),
          'url': payload.get('payment_url'),
          'created_at': int(time.time())
        }
        links.append(record)
        try:
          with open(link_store, 'w', encoding='utf-8') as fh:
            json.dump(links, fh, indent=2)
        except Exception:
          pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "id": pid, "url": record['url']}).encode('utf-8'))
        return

      # Fallback: handle form submission for search
      try:
        body = body_bytes.decode('utf-8')
        data = urllib.parse.parse_qs(body)
        person = data.get("person", [""])[0].strip()
        place = data.get("place", [""])[0].strip()
        results = build_urls(person, place)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_form(person, place, results).encode("utf-8"))
      except Exception:
        self.send_response(400)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server() -> None:
    for port in (PORT, 0):
        try:
            with socketserver.TCPServer((HOST, port), SearchHandler) as httpd:
                host, bound_port = httpd.server_address
                url = f"http://{host}:{bound_port}"
                print(f"People & Place Search app running at {url}")
                webbrowser.open(url)
                httpd.serve_forever()
                return
        except OSError:
            continue

    raise RuntimeError("Unable to bind to a network port for the app.")


if __name__ == "__main__":
    run_server()
