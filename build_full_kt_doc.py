import os
import re
import html

# Read source files
with open('DEPLOYMENT.md', 'r', encoding='utf-8') as f:
    deployment_md = f.read()

with open('Flaky Test Detector_README.md', 'r', encoding='utf-8') as f:
    readme_md = f.read()

with open('prompts_archive.md', 'r', encoding='utf-8') as f:
    prompts_md = f.read()

# Build prompts HTML from prompts_archive.md
prompt_sections = re.split(r'## Prompt\s+(\d+)', prompts_md)
prompts_html_blocks = []

if len(prompt_sections) > 1:
    for i in range(1, len(prompt_sections), 2):
        p_num = prompt_sections[i]
        p_content = prompt_sections[i+1].strip()
        # Clean backticks
        p_clean = p_content.strip('`').strip()
        if not p_clean:
            continue
        escaped_p = html.escape(p_clean)
        prompts_html_blocks.append(f"""
        <div class="prompt-box">
          <div class="prompt-header" onclick="togglePrompt(this)">
            <span><span class="badge badge-blue">Prompt {p_num}</span> {html.escape(p_clean[:70])}...</span>
            <span>▼</span>
          </div>
          <div class="prompt-body">
            <pre><code>{escaped_p}</code></pre>
          </div>
        </div>
        """)
else:
    prompts_html_blocks.append(f"<pre><code>{html.escape(prompts_md)}</code></pre>")

# Recent prompts (69 - 85)
recent_prompts = [
    (69, "Render Out-of-Memory (502 Bad Gateway) Debugging", 
     "Render instance crashed with 502 Bad Gateway due to SentenceTransformers / PyTorch memory overhead exceeding 512MB RAM free tier limit.\n\nSolution: Removed PyTorch dependency from Dockerfile, refactored to Groq Cloud API for Llama 3.1 inference, and reduced container footprint to ~35MB RAM."),
    (70, "Persistent SQLite Disk & Seed Protection (/data/.seeded)",
     "Real test data from CI was being overwritten by seed data whenever Render container rebooted.\n\nSolution: Mounted Render persistent disk volume at /data, configured DB_PATH=/data/flaky_test_detector.db, and added one-time .seeded marker file check."),
    (71, "Step Failure Breakdown & Step Variance Analysis",
     "Add step failure breakdown table inside the test detail panel showing run frequency per step and a variance concentration score.\n\nSolution: Added step analysis extracting stack trace lines and evaluating whether failures are concentrated at one step (>=75%) or scattered across steps."),
    (72, "Actionable Code-Level Suggestions for Playwright, Selenium, Tosca",
     "The AI recommendation was giving generic text. We need tool-grounded code fixes tailored to the specific error and framework.\n\nSolution: Rewrote Groq prompt and fallback categorizer to emit concrete syntax (e.g. await page.locator('#btn').waitFor({ state: 'visible' }) or WebDriverWait(driver, 10).until(...))."),
    (73, "Right-Side Slide-Over Drawer UI (Eliminating Bottom Scrolling)",
     "When clicking a test row, the detail panel opened below the 100-row table, forcing the user to scroll down every time.\n\nSolution: Transformed detail panel into a modern 720px right-side slide-over drawer with backdrop blur, sticky header, and body scroll lock."),
    (74, "Table Column Sorting with Multi-Type Tie-Breaking",
     "Implement clickable column header sorting for Test Name, History, Score, Pass/Fail, and Last Run, defaulting to most recent run first.\n\nSolution: Added applySortingAndRender() with getSortValue() supporting alphanumeric, numeric, and timestamp comparisons."),
    (75, "Demo Test Suite Expansion (tests/demo.spec.js with 15 Scenarios)",
     "Add realistic flaky test patterns (timing, network 503, session expiry, real bugs, stable baseline) with retries: 2 enabled.\n\nSolution: Authored tests/demo.spec.js with 15 realistic production scenarios and updated playwright.config.js."),
    (76, "LocalStorage Caching & 4-Stage Render Wakeup Retry",
     "On page refresh, if Render is sleeping, the dashboard fell back to sample data instead of showing the 91 real runs.\n\nSolution: Cached real API responses in localStorage (ftd-cached-runs) for instant 0-second render, with 4 background retries (0s, 8s, 15s, 20s) and a live status banner."),
    (77, "Verdict-Aware Score Badge Colors (Green / Amber / Red)",
     "Make the score badge color reflect the test's true verdict category, so broken tests (passCount=0) don't look green just because flip score is 0.0%.\n\nSolution: Created verdictBadgeClass() -> Green for always passing, Red for always failing (Real Bug), Amber for mixed pass/fail (Flaky)."),
    (78, "Local Timezone Engine (UTC to IST Conversion)",
     "Last run column showed 02:13 instead of 07:44 IST because UTC strings without 'Z' were treated as naive local time.\n\nSolution: Implemented parseUTCDate() which standardizes ISO strings to UTC and lets the browser Date object format local hours and minutes accurately."),
    (79, "Universal Framework Tag Cleaner (clean_test_name)",
     "Playwright tag annotations like '@demo' and '@smoke' were appearing in the test names in the UI.\n\nSolution: Added clean_test_name() regex filter at the JUnit XML parsing layer in both tools/junit_xml_to_ingest.py and backend/src/services/junit_parser.py."),
    (80, "Dedicated Fast LIVE DEMO Workflow (Under 15 Seconds)",
     "The full 25-minute test suite is too slow for a live 10-minute presentation demo. Create a dedicated fast demo path.\n\nSolution: Tagged representative tests with @demo and created .github/workflows/live-demo-fast.yml running npx playwright test --grep @demo in 12-15 seconds."),
    (81, "24/7 Render Keep-Awake Cron Workflow (keep-awake.yml)",
     "Render Free Tier spins down after 15 minutes of inactivity, causing cold-start loading screens.\n\nSolution: Added .github/workflows/keep-awake.yml scheduled every 10 minutes to ping /health and keep Render active 24/7."),
    (82, "Cross-Repository Ingestion Hook for Advance-Playwright-Framework",
     "Enable tests running in Advance-Playwright-Framework repo to ingest into the same central detector dashboard alongside demo tests.\n\nSolution: Configured playwright.yml with JUnit XML reporter and curl ingestion script forwarding results to the Render endpoint.")
]

for p_num, title, desc in recent_prompts:
    escaped_desc = html.escape(desc)
    prompts_html_blocks.append(f"""
    <div class="prompt-box">
      <div class="prompt-header" onclick="togglePrompt(this)">
        <span><span class="badge badge-flaky">Prompt {p_num}</span> <strong>{html.escape(title)}</strong></span>
        <span>▼</span>
      </div>
      <div class="prompt-body">
        <pre><code>{escaped_desc}</code></pre>
      </div>
    </div>
    """)

all_prompts_html = "\n".join(prompts_html_blocks)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Flaky Test Detector — Complete Knowledge Transfer (KT) & Technical Master Document</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #1D4ED8;
      --primary-hover: #1E40AF;
      --primary-light: #EFF6FF;
      --primary-border: #BFDBFE;
      --accent-blue: #3B82F6;
      --sidebar-bg: linear-gradient(180deg, #EBF3FA 0%, #D8E7F6 100%);
      --sidebar-border: #CBD5E1;
      --sidebar-text: #1E293B;
      --sidebar-active-bg: #FFFFFF;
      --sidebar-active-text: #1D4ED8;
      
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --border: #E2E8F0;
      
      --text-main: #0F172A;
      --text-muted: #475569;
      --text-soft: #94A3B8;
      
      --teal-bg: #ECFDF5;
      --teal-border: #A7F3D0;
      --teal-text: #065F46;
      --amber-bg: #FFFBEB;
      --amber-border: #FDE68A;
      --amber-text: #92400E;
      --coral-bg: #FEF2F2;
      --coral-border: #FECACA;
      --coral-text: #991B1B;
      --code-bg: #0F172A;
      --code-text: #F8FAFC;
      --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      font-family: var(--font-sans);
      background: var(--bg);
      color: var(--text-main);
      line-height: 1.65;
      display: flex;
      min-height: 100vh;
    }}

    .sidebar {{
      width: 310px;
      flex-shrink: 0;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--sidebar-border);
      position: fixed;
      top: 0; left: 0; bottom: 0;
      display: flex; flex-direction: column;
      z-index: 100;
      overflow-y: auto;
      box-shadow: 2px 0 12px rgba(0, 0, 0, 0.03);
    }}

    .sidebar-header {{
      padding: 1.5rem 1.25rem 1rem 1.25rem;
      border-bottom: 1px solid rgba(203, 213, 225, 0.6);
      background: rgba(255, 255, 255, 0.5);
      backdrop-filter: blur(8px);
      position: sticky; top: 0; z-index: 10;
    }}

    .sidebar-brand {{
      display: flex; align-items: center; gap: 0.65rem;
      font-size: 1.15rem; font-weight: 800; color: var(--primary);
    }}

    .sidebar-subtitle {{
      font-size: 0.78rem; color: var(--text-muted); margin-top: 0.25rem; font-weight: 500;
    }}

    .sidebar-search {{ margin-top: 0.9rem; position: relative; }}
    .sidebar-search input {{
      width: 100%; padding: 0.45rem 0.75rem 0.45rem 2rem;
      border-radius: 0.5rem; border: 1px solid #CBD5E1;
      font-size: 0.82rem; background: #FFFFFF; outline: none;
      font-family: var(--font-sans); transition: all 0.2s ease;
    }}
    .sidebar-search input:focus {{
      border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
    }}
    .sidebar-search svg {{
      position: absolute; left: 0.65rem; top: 50%; transform: translateY(-50%);
      width: 14px; height: 14px; color: var(--text-soft);
    }}

    .sidebar-nav {{
      padding: 1rem 0.75rem 2rem 0.75rem;
      display: flex; flex-direction: column; gap: 0.25rem; flex: 1;
    }}

    .nav-group-title {{
      font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--text-muted);
      padding: 0.75rem 0.65rem 0.35rem 0.65rem;
    }}

    .nav-item {{
      display: flex; align-items: center; gap: 0.6rem;
      padding: 0.55rem 0.75rem; border-radius: 0.5rem;
      font-size: 0.86rem; font-weight: 600; color: var(--sidebar-text);
      text-decoration: none; transition: all 0.2s ease;
    }}
    .nav-item:hover {{
      background: rgba(255, 255, 255, 0.7); color: var(--primary); transform: translateX(2px);
    }}
    .nav-item.active {{
      background: var(--sidebar-active-bg); color: var(--sidebar-active-text);
      box-shadow: 0 2px 6px rgba(37, 99, 235, 0.08); border-left: 3px solid var(--primary);
    }}

    .content-wrapper {{
      margin-left: 310px; flex: 1; padding: 2.5rem 3.5rem; max-width: 1250px;
    }}

    .hero-header {{
      background: linear-gradient(135deg, #FFFFFF 0%, #EFF6FF 100%);
      border: 1px solid var(--primary-border);
      border-radius: 1rem; padding: 2.5rem; margin-bottom: 3rem;
      box-shadow: 0 4px 20px rgba(37, 99, 235, 0.05); position: relative; overflow: hidden;
    }}
    .hero-badge {{
      display: inline-flex; align-items: center; gap: 0.4rem;
      background: var(--primary-light); border: 1px solid var(--primary-border);
      color: var(--primary); font-size: 0.8rem; font-weight: 700;
      padding: 0.25rem 0.75rem; border-radius: 999px; margin-bottom: 1rem;
      text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .hero-title {{
      font-size: 2.3rem; font-weight: 800; color: #0F172A; letter-spacing: -0.02em; line-height: 1.2; margin-bottom: 0.75rem;
    }}
    .hero-description {{ font-size: 1.05rem; color: var(--text-muted); max-width: 850px; line-height: 1.6; }}
    .hero-meta {{
      display: flex; flex-wrap: wrap; gap: 1.5rem; margin-top: 1.5rem;
      padding-top: 1.25rem; border-top: 1px solid rgba(191, 219, 254, 0.5);
      font-size: 0.85rem; color: var(--text-muted);
    }}

    .section-block {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 0.85rem; padding: 2.25rem; margin-bottom: 2.5rem;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02); scroll-margin-top: 2rem;
    }}
    .section-title {{
      font-size: 1.55rem; font-weight: 800; color: #0F172A; letter-spacing: -0.02em;
      margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.65rem;
      border-bottom: 2px solid var(--primary-light); padding-bottom: 0.75rem;
    }}
    .section-subtitle {{ font-size: 0.95rem; color: var(--text-muted); margin-bottom: 1.5rem; }}

    h3 {{ font-size: 1.18rem; font-weight: 700; color: #1E293B; margin: 1.6rem 0 0.75rem 0; }}
    h4 {{ font-size: 1rem; font-weight: 700; color: #334155; margin: 1.2rem 0 0.5rem 0; }}
    p {{ margin-bottom: 1rem; color: var(--text-main); font-size: 0.96rem; }}

    .callout {{
      padding: 1.1rem 1.3rem; border-radius: 0.65rem; margin: 1.25rem 0;
      font-size: 0.92rem; line-height: 1.55; display: flex; gap: 0.85rem; align-items: flex-start;
    }}
    .callout-info {{ background: #EFF6FF; border-left: 4px solid #3B82F6; color: #1E40AF; }}
    .callout-success {{ background: var(--teal-bg); border-left: 4px solid #10B981; color: var(--teal-text); }}
    .callout-warning {{ background: var(--amber-bg); border-left: 4px solid #F59E0B; color: var(--amber-text); }}
    .callout-danger {{ background: var(--coral-bg); border-left: 4px solid #EF4444; color: var(--coral-text); }}
    .callout-icon {{ font-size: 1.2rem; line-height: 1; flex-shrink: 0; }}

    .table-container {{
      width: 100%; overflow-x: auto; margin: 1.25rem 0;
      border: 1px solid var(--border); border-radius: 0.5rem;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; text-align: left; }}
    thead {{ background: #F1F5F9; color: #334155; font-weight: 700; }}
    th, td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }}
    tr:last-child td {{ border-bottom: none; }}
    tbody tr:hover {{ background: #F8FAFC; }}

    .badge {{
      display: inline-block; padding: 0.2rem 0.55rem; border-radius: 0.35rem;
      font-size: 0.78rem; font-weight: 700; font-family: var(--font-mono);
      text-transform: uppercase; letter-spacing: 0.03em;
    }}
    .badge-pass {{ background: var(--teal-bg); border: 1px solid var(--teal-border); color: var(--teal-text); }}
    .badge-flaky {{ background: var(--amber-bg); border: 1px solid var(--amber-border); color: var(--amber-text); }}
    .badge-fail {{ background: var(--coral-bg); border: 1px solid var(--coral-border); color: var(--coral-text); }}
    .badge-blue {{ background: #EFF6FF; border: 1px solid #BFDBFE; color: #1E40AF; }}

    pre {{
      background: var(--code-bg); color: var(--code-text);
      padding: 1.25rem; border-radius: 0.65rem; font-family: var(--font-mono);
      font-size: 0.85rem; line-height: 1.6; overflow-x: auto; margin: 1.1rem 0;
    }}
    code {{
      font-family: var(--font-mono); font-size: 0.87em; background: #EEF2F6;
      color: #0F172A; padding: 0.15rem 0.35rem; border-radius: 0.25rem; border: 1px solid #E2E8F0;
    }}
    pre code {{ background: transparent; color: inherit; padding: 0; border: none; }}

    .code-header {{
      display: flex; justify-content: space-between; align-items: center;
      background: #1E293B; color: #94A3B8; font-family: var(--font-mono);
      font-size: 0.78rem; padding: 0.45rem 1rem; border-top-left-radius: 0.65rem;
      border-top-right-radius: 0.65rem; margin-bottom: -1.1rem;
    }}
    .code-header + pre {{ border-top-left-radius: 0; border-top-right-radius: 0; }}

    .cards-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.25rem; margin: 1.5rem 0;
    }}
    .feature-card {{
      background: #FFFFFF; border: 1px solid var(--border); border-radius: 0.65rem;
      padding: 1.35rem; transition: all 0.2s ease; position: relative; border-top: 3px solid var(--accent-blue);
    }}
    .feature-card:hover {{ box-shadow: 0 6px 16px rgba(37, 99, 235, 0.08); transform: translateY(-2px); }}
    .feature-card-icon {{ font-size: 1.5rem; margin-bottom: 0.6rem; }}
    .feature-card-title {{ font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 0.4rem; }}
    .feature-card-text {{ font-size: 0.88rem; color: var(--text-muted); line-height: 1.5; }}

    .diagram-container {{
      background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 0.75rem;
      padding: 1.5rem; margin: 1.5rem 0; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03); overflow-x: auto;
    }}
    .diagram-title {{
      font-size: 0.95rem; font-weight: 700; color: #1E293B; margin-bottom: 1rem;
      display: flex; align-items: center; gap: 0.5rem;
    }}
    svg.flow-svg {{ width: 100%; min-width: 700px; height: auto; display: block; }}

    .tabs-nav {{
      display: flex; gap: 0.5rem; border-bottom: 2px solid var(--border); margin-bottom: 1rem; overflow-x: auto;
    }}
    .tab-btn {{
      padding: 0.6rem 1.1rem; border: none; background: transparent;
      font-family: var(--font-sans); font-size: 0.88rem; font-weight: 600;
      color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent;
      margin-bottom: -2px; transition: all 0.2s ease; white-space: nowrap;
    }}
    .tab-btn:hover {{ color: var(--primary); }}
    .tab-btn.active {{
      color: var(--primary); border-bottom-color: var(--primary); background: var(--primary-light);
      border-top-left-radius: 0.4rem; border-top-right-radius: 0.4rem;
    }}
    .tab-pane {{ display: none; }}
    .tab-pane.active {{ display: block; }}

    .prompt-box {{
      border: 1px solid var(--border); border-radius: 0.65rem;
      margin-bottom: 0.75rem; overflow: hidden; background: #FFFFFF;
    }}
    .prompt-header {{
      background: #F8FAFC; padding: 0.85rem 1.25rem; font-weight: 700;
      font-size: 0.88rem; color: #1E293B; cursor: pointer; display: flex;
      justify-content: space-between; align-items: center; transition: background 0.2s ease;
      border-bottom: 1px solid transparent;
    }}
    .prompt-header:hover {{ background: var(--primary-light); color: var(--primary); }}
    .prompt-box.open .prompt-header {{
      border-bottom-color: var(--border); background: var(--primary-light); color: var(--primary);
    }}
    .prompt-body {{ padding: 1.25rem; display: none; font-size: 0.9rem; background: #FFFFFF; }}
    .prompt-box.open .prompt-body {{ display: block; }}

    .timeline-item {{
      border-left: 3px solid var(--primary); padding-left: 1.25rem;
      margin-bottom: 1.5rem; position: relative;
    }}
    .timeline-item::before {{
      content: ''; position: absolute; left: -7px; top: 0;
      width: 11px; height: 11px; border-radius: 50%; background: var(--primary);
    }}
    .timeline-date {{ font-size: 0.78rem; font-weight: 700; color: var(--primary); text-transform: uppercase; }}
    .timeline-title {{ font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0.2rem 0 0.4rem 0; }}

    footer {{
      margin-top: 4rem; padding-top: 2rem; border-top: 1px solid var(--border);
      color: var(--text-muted); font-size: 0.85rem; text-align: center;
    }}

    @media (max-width: 900px) {{
      .sidebar {{ display: none; }}
      .content-wrapper {{ margin-left: 0; padding: 1.5rem; }}
    }}
  </style>
</head>
<body>

  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-brand">🧪 FlakyTest Master KT</div>
      <div class="sidebar-subtitle">Complete Architecture & History</div>
      <div class="sidebar-search">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input type="text" id="sidebar-filter" placeholder="Filter sections & prompts..." onkeyup="filterSidebar(this.value)">
      </div>
    </div>

    <nav class="sidebar-nav" id="sidebar-menu">
      <div class="nav-group-title">1. Architecture & Core</div>
      <a href="#overview" class="nav-item active">📋 Executive Summary</a>
      <a href="#architecture-diagram" class="nav-item">🏗️ System Architecture</a>
      <a href="#decision-tree" class="nav-item">🌳 Classification Tree</a>
      <a href="#scoring-math" class="nav-item">📊 Scoring & Variance Math</a>

      <div class="nav-group-title">2. Complete Embedded Docs</div>
      <a href="#full-readme" class="nav-item">📄 README.md (Full)</a>
      <a href="#full-deployment" class="nav-item">☁️ DEPLOYMENT.md (Full)</a>
      <a href="#ci-workflows" class="nav-item">⚙️ CI/CD Workflows Hub</a>

      <div class="nav-group-title">3. Timeline & Discussions</div>
      <a href="#evolution-timeline" class="nav-item">⏳ Evolution Timeline</a>
      <a href="#troubleshooting-log" class="nav-item">🛠️ QA & Bug Log</a>

      <div class="nav-group-title">4. Prompts Archive</div>
      <a href="#prompts-archive" class="nav-item">📜 Prompts Archive (1–85)</a>
    </nav>
  </aside>

  <main class="content-wrapper">

    <header class="hero-header">
      <div class="hero-badge">Comprehensive Engineering Master Document</div>
      <h1 class="hero-title">Flaky Test Detector — Master KT & Evolution Log</h1>
      <p class="hero-description">
        The definitive technical source of truth for the Flaky Test Detector platform. Contains complete markdown document embeds, end-to-end SVG architecture diagrams, multi-framework CI workflows, and the unabridged prompt history from inception to demo-readiness.
      </p>
      <div class="hero-meta">
        <div class="hero-meta-item"><strong>Author:</strong> QA Automation & AI Agentic Team</div>
        <div class="hero-meta-item"><strong>Backend:</strong> FastAPI • SQLite (Persistent Disk) • Qdrant • Groq Llama 3.1</div>
        <div class="hero-meta-item"><strong>Live URL:</strong> <a href="https://flaky-test-detector-kbpc.onrender.com" target="_blank" style="color:var(--primary);text-decoration:none;font-weight:600;">flaky-test-detector-kbpc.onrender.com</a></div>
      </div>
    </header>

    <!-- SECTION 1: OVERVIEW -->
    <section id="overview" class="section-block">
      <h2 class="section-title">📋 1. Executive Summary & Business Value</h2>
      <p class="section-subtitle">Core problem statement, ROI, and technical differentiation.</p>
      <p>
        In modern continuous integration pipelines, <strong>flaky tests</strong> (tests that intermittently pass and fail on identical source code) generate noise, delay releases, and erode developer trust in automated test suites.
      </p>
      <div class="cards-grid">
        <div class="feature-card">
          <div class="feature-card-icon">⚡</div>
          <div class="feature-card-title">Transition-Based Scoring</div>
          <div class="feature-card-text">Strictly quantifies flakiness based on status changes (Pass ↔ Fail) across historical runs rather than raw failure counts.</div>
        </div>
        <div class="feature-card">
          <div class="feature-card-icon">🧠</div>
          <div class="feature-card-title">Vector Failure Clustering</div>
          <div class="feature-card-text">Indexes error messages into Qdrant to group identical failure signatures across different test files and shards.</div>
        </div>
        <div class="feature-card">
          <div class="feature-card-icon">🎯</div>
          <div class="feature-card-title">Actionable AI Fixes</div>
          <div class="feature-card-text">Delivers syntax-level code fixes for Playwright, Selenium, and Tosca powered by Groq Llama 3.1 8B.</div>
        </div>
      </div>
    </section>

    <!-- SECTION 2: SYSTEM ARCHITECTURE DIAGRAM -->
    <section id="architecture-diagram" class="section-block">
      <h2 class="section-title">🏗️ 2. End-to-End System Architecture</h2>
      <p class="section-subtitle">Visual architecture connecting CI runners, dual-storage, LLM inference, and client UI.</p>
      <div class="diagram-container">
        <div class="diagram-title"><span>📐</span> High-Definition Architectural Topology</div>
        <svg class="flow-svg" viewBox="0 0 920 380" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="blueGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#EFF6FF"/><stop offset="100%" stop-color="#DBEAFE"/></linearGradient>
            <linearGradient id="primaryGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#2563EB"/><stop offset="100%" stop-color="#1D4ED8"/></linearGradient>
            <linearGradient id="purpleGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#FAF5FF"/><stop offset="100%" stop-color="#F3E8FF"/></linearGradient>
          </defs>

          <!-- CI Runners Box -->
          <rect x="20" y="30" width="220" height="320" rx="10" fill="url(#blueGrad)" stroke="#BFDBFE" stroke-width="2"/>
          <text x="130" y="60" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="13" fill="#1E40AF">CI / CD TEST RUNNERS</text>
          
          <rect x="40" y="80" width="180" height="50" rx="6" fill="#FFFFFF" stroke="#93C5FD"/>
          <text x="130" y="105" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#1E293B">Playwright Test Runner</text>
          <text x="130" y="120" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#64748B">--reporter=junit</text>

          <rect x="40" y="145" width="180" height="50" rx="6" fill="#FFFFFF" stroke="#93C5FD"/>
          <text x="130" y="170" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#1E293B">Selenium (Pytest / JUnit)</text>
          <text x="130" y="185" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#64748B">pytest --junitxml</text>

          <rect x="40" y="210" width="180" height="50" rx="6" fill="#FFFFFF" stroke="#93C5FD"/>
          <text x="130" y="235" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#1E293B">Tricentis Tosca</text>
          <text x="130" y="250" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#64748B">Server Execution API</text>

          <rect x="40" y="275" width="180" height="50" rx="6" fill="#FFFFFF" stroke="#93C5FD"/>
          <text x="130" y="300" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#1E293B">Advance Framework</text>
          <text x="130" y="315" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#64748B">Katalon Sharded Tests</text>

          <!-- Arrow 1 -->
          <path d="M 240 190 L 300 190" stroke="#3B82F6" stroke-width="3" stroke-dasharray="4 4"/>
          <polygon points="305,190 295,185 295,195" fill="#3B82F6"/>

          <!-- Backend Box -->
          <rect x="310" y="30" width="270" height="320" rx="10" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="2"/>
          <rect x="310" y="30" width="270" height="36" rx="10" fill="url(#primaryGrad)"/>
          <text x="445" y="54" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#FFFFFF">FASTAPI BACKEND SERVICE</text>

          <rect x="330" y="80" width="230" height="52" rx="6" fill="#F8FAFC" stroke="#E2E8F0"/>
          <text x="445" y="102" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#0F172A">Tag Cleaner & Ingestion</text>
          <text x="445" y="118" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#059669">clean_test_name() regex</text>

          <rect x="330" y="145" width="230" height="52" rx="6" fill="#F8FAFC" stroke="#E2E8F0"/>
          <text x="445" y="167" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#0F172A">Flakiness Scorer & Variance</text>
          <text x="445" y="183" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#2563EB">Transition flip-rate logic</text>

          <rect x="330" y="210" width="230" height="52" rx="6" fill="#F8FAFC" stroke="#E2E8F0"/>
          <text x="445" y="232" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#0F172A">Heuristic Categorizer</text>
          <text x="445" y="248" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#D97706">Timing • Network • Overlay</text>

          <rect x="330" y="275" width="230" height="52" rx="6" fill="#F8FAFC" stroke="#E2E8F0"/>
          <text x="445" y="297" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="11" fill="#0F172A">Render 24/7 Keep-Awake</text>
          <text x="445" y="313" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#7C3AED">GET /health (10m cron)</text>

          <!-- DB Connections -->
          <path d="M 580 110 L 640 90" stroke="#059669" stroke-width="2"/>
          <polygon points="645,88 636,85 638,95" fill="#059669"/>
          <path d="M 580 200 L 640 210" stroke="#7C3AED" stroke-width="2"/>
          <polygon points="645,212 636,206 636,216" fill="#7C3AED"/>

          <!-- Right Side: DB & AI -->
          <rect x="650" y="40" width="240" height="95" rx="8" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="2"/>
          <text x="770" y="65" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#065F46">SQLite Database (/data)</text>
          <text x="770" y="85" text-anchor="middle" font-family="Plus Jakarta Sans" font-size="10" fill="#047857">Table: test_runs</text>
          <text x="770" y="103" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#059669">Persistent Disk Mount</text>

          <rect x="650" y="150" width="240" height="95" rx="8" fill="url(#purpleGrad)" stroke="#D8B4FE" stroke-width="2"/>
          <text x="770" y="175" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#6B21A8">Qdrant Vector Index</text>
          <text x="770" y="195" text-anchor="middle" font-family="Plus Jakarta Sans" font-size="10" fill="#7E22CE">Collection: test_failures</text>
          <text x="770" y="213" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#6B21A8">Top-5 Similarity Match</text>

          <rect x="650" y="260" width="240" height="90" rx="8" fill="#FFFBEB" stroke="#FDE68A" stroke-width="2"/>
          <text x="770" y="285" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#92400E">Groq Cloud AI Engine</text>
          <text x="770" y="305" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="#B45309">llama-3.1-8b-instant</text>
          <text x="770" y="323" text-anchor="middle" font-family="Plus Jakarta Sans" font-size="9" fill="#92400E">Tool-tailored code remediation</text>
        </svg>
      </div>
    </section>

    <!-- SECTION 3: CLASSIFICATION DECISION TREE -->
    <section id="decision-tree" class="section-block">
      <h2 class="section-title">🌳 3. Flakiness Classification Decision Tree</h2>
      <p class="section-subtitle">Visual state machine for assigning verdicts, colors, and root causes.</p>
      <div class="diagram-container">
        <div class="diagram-title"><span>🔄</span> Decision Tree & Step Variance Evaluation</div>
        <svg class="flow-svg" viewBox="0 0 900 320" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="20" y="120" width="130" height="50" rx="25" fill="#2563EB"/>
          <text x="85" y="150" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="11" fill="#FFFFFF">Test Run Log</text>

          <path d="M 150 145 L 200 145" stroke="#64748B" stroke-width="2"/>
          <polygon points="205,145 197,140 197,150" fill="#64748B"/>

          <polygon points="270,105 340,145 270,185 200,145" fill="#EFF6FF" stroke="#3B82F6" stroke-width="2"/>
          <text x="270" y="142" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="10" fill="#1E40AF">Failures</text>
          <text x="270" y="155" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="10" fill="#1E40AF">Found?</text>

          <path d="M 270 105 L 270 50 L 390 50" stroke="#10B981" stroke-width="2"/>
          <polygon points="395,50 387,45 387,55" fill="#10B981"/>
          <text x="300" y="42" font-family="JetBrains Mono" font-weight="700" font-size="9" fill="#059669">NO (0 Fails)</text>

          <rect x="400" y="25" width="220" height="50" rx="8" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="2"/>
          <text x="510" y="48" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#065F46">HEALTHY / STABLE</text>
          <text x="510" y="64" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="#047857">Badge: Green (0.0% Score)</text>

          <path d="M 340 145 L 410 145" stroke="#64748B" stroke-width="2"/>
          <polygon points="415,145 407,140 407,150" fill="#64748B"/>
          <text x="375" y="138" font-family="JetBrains Mono" font-weight="700" font-size="9" fill="#64748B">YES</text>

          <polygon points="480,105 550,145 480,185 410,145" fill="#FFFBEB" stroke="#F59E0B" stroke-width="2"/>
          <text x="480" y="142" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="10" fill="#92400E">Any Passes</text>
          <text x="480" y="155" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="700" font-size="10" fill="#92400E">in History?</text>

          <path d="M 480 185 L 480 260 L 590 260" stroke="#EF4444" stroke-width="2"/>
          <polygon points="595,260 587,255 587,265" fill="#EF4444"/>
          <text x="515" y="250" font-family="JetBrains Mono" font-weight="700" font-size="9" fill="#DC2626">NO (100% Fail)</text>

          <rect x="600" y="235" width="280" height="55" rx="8" fill="#FEF2F2" stroke="#FECACA" stroke-width="2"/>
          <text x="740" y="258" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#991B1B">LIKELY REAL BUG (REGRESSION)</text>
          <text x="740" y="274" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="#B91C1C">Badge: Red • Consistent Failure</text>

          <path d="M 550 145 L 620 145" stroke="#F59E0B" stroke-width="2"/>
          <polygon points="625,145 617,140 617,150" fill="#F59E0B"/>
          <text x="580" y="138" font-family="JetBrains Mono" font-weight="700" font-size="9" fill="#D97706">YES (Mixed)</text>

          <rect x="630" y="115" width="250" height="60" rx="8" fill="#FFFBEB" stroke="#FDE68A" stroke-width="2"/>
          <text x="755" y="138" text-anchor="middle" font-family="Plus Jakarta Sans" font-weight="800" font-size="12" fill="#92400E">LIKELY FLAKY TEST</text>
          <text x="755" y="155" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="#B45309">Badge: Amber • Transition Score</text>
        </svg>
      </div>
    </section>

    <!-- SECTION 4: SCORING & VARIANCE MATH -->
    <section id="scoring-math" class="section-block">
      <h2 class="section-title">📊 4. Flakiness Scoring & Step Variance Math</h2>
      <p class="section-subtitle">Mathematical formulation of transition flip-rates and failure concentration.</p>
      
      <h3>Transition Flip Formula</h3>
      <pre><code>def flakinessScore(runs):
    if len(runs) < 3:
        return 0.0
    transitions = 0
    for i in range(1, len(runs)):
        if runs[i].status != runs[i - 1].status:
            transitions += 1
    return transitions / (len(runs) - 1)</code></pre>

      <h3>Step Failure Variance Concentration</h3>
      <p>
        Evaluates step-level clustering: Concentration = (Failures at Top Step) / (Total Failures).
        If &ge; 75%, failures are concentrated (localized brittle selector). If &lt; 75%, failures are scattered (environment latency / network jitter).
      </p>
    </section>

    <!-- SECTION 5: FULL README.MD EMBEDDED -->
    <section id="full-readme" class="section-block">
      <h2 class="section-title">📄 5. Complete README.md Document</h2>
      <p class="section-subtitle">Full contents of Flaky Test Detector_README.md embedded verbatim.</p>
      <div class="code-header">Flaky Test Detector_README.md</div>
      <pre><code>{html.escape(readme_md)}</code></pre>
    </section>

    <!-- SECTION 6: FULL DEPLOYMENT.MD EMBEDDED -->
    <section id="full-deployment" class="section-block">
      <h2 class="section-title">☁️ 6. Complete DEPLOYMENT.md Document</h2>
      <p class="section-subtitle">Full contents of DEPLOYMENT.md embedded verbatim.</p>
      <div class="code-header">DEPLOYMENT.md</div>
      <pre><code>{html.escape(deployment_md)}</code></pre>
    </section>

    <!-- SECTION 7: CI/CD WORKFLOWS HUB -->
    <section id="ci-workflows" class="section-block">
      <h2 class="section-title">⚙️ 7. CI/CD Workflows Hub (All Pipelines)</h2>
      <p class="section-subtitle">Tabbed repository workflows for fast demo, full test execution, and keep-awake.</p>

      <div class="tabs-nav">
        <button class="tab-btn active" onclick="switchTab(event, 'tab-fast-demo')">⚡ LIVE DEMO (15s)</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-full-demo')">🧪 Full Pipeline</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-keep-awake')">⏰ Keep-Awake Cron</button>
        <button class="tab-btn" onclick="switchTab(event, 'tab-playwright-hook')">🎭 Advance Framework Hook</button>
      </div>

      <div id="tab-fast-demo" class="tab-pane active">
        <div class="code-header">.github/workflows/live-demo-fast.yml</div>
        <pre><code>name: LIVE DEMO — fast subset
on:
  workflow_dispatch:
    inputs:
      reason:
        description: 'Demo run description'
        required: false
        default: 'Live presentation demo'
jobs:
  fast-demo-run:
    name: Run Fast Demo Tests (@demo)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {{ node-version: '20' }}
      - uses: actions/setup-python@v5
        with: {{ python-version: '3.11' }}
      - run: npm ci
      - run: npx playwright install chromium --with-deps
      - name: Run Fast Demo Tests (@demo)
        run: |
          mkdir -p results
          npx playwright test --grep @demo --reporter=junit
        continue-on-error: true
        env:
          PLAYWRIGHT_JUNIT_OUTPUT_NAME: results/junit.xml
      - name: Send results to Flaky Test Detector
        if: always()
        env:
          API_KEY: ${{{{ secrets.DETECTOR_API_KEY }}}}
        run: |
          DETECTOR_URL="https://flaky-test-detector-kbpc.onrender.com"
          if [ -f results/junit.xml ]; then
            python tools/junit_xml_to_ingest.py results/junit.xml \
              --url "${{DETECTOR_URL}}/api/v1/test-runs/ingest" \
              --commit-sha "${{{{ github.sha }}}}" \
              --api-key "${{API_KEY}}"
          fi</code></pre>
      </div>

      <div id="tab-full-demo" class="tab-pane">
        <div class="code-header">.github/workflows/flaky-detector-demo.yml</div>
        <pre><code>name: Flaky Detector Demo Pipeline
on:
  push:
    branches: [main]
  workflow_dispatch: {{}}
jobs:
  build-test-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {{ node-version: '20' }}
      - uses: actions/setup-python@v5
        with: {{ python-version: '3.11' }}
      - run: npm ci
      - run: npx playwright install --with-deps
      - name: Run Playwright tests
        run: |
          mkdir -p results
          npx playwright test --reporter=junit
        continue-on-error: true
        env:
          PLAYWRIGHT_JUNIT_OUTPUT_NAME: results/junit.xml
      - name: Send results to Flaky Test Detector
        if: always()
        env:
          API_KEY: ${{{{ secrets.DETECTOR_API_KEY }}}}
        run: |
          DETECTOR_URL="https://flaky-test-detector-kbpc.onrender.com"
          if [ -f results/junit.xml ]; then
            python tools/junit_xml_to_ingest.py results/junit.xml \
              --url "${{DETECTOR_URL}}/api/v1/test-runs/ingest" \
              --commit-sha "${{{{ github.sha }}}}" \
              --api-key "${{API_KEY}}"
          fi</code></pre>
      </div>

      <div id="tab-keep-awake" class="tab-pane">
        <div class="code-header">.github/workflows/keep-awake.yml</div>
        <pre><code>name: Keep Render Backend Awake
on:
  schedule:
    - cron: '*/10 * * * *'
  workflow_dispatch: {{}}
jobs:
  ping-health:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Render Backend
        run: |
          URL="https://flaky-test-detector-kbpc.onrender.com/health"
          STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 20 "${{URL}}" || echo "FAILED")
          echo "Render Status: ${{STATUS}}"</code></pre>
      </div>

      <div id="tab-playwright-hook" class="tab-pane">
        <div class="code-header">Advance-Playwright-Framework Ingestion Hook (playwright.yml)</div>
        <pre><code>      - name: 🚀 Send results to Flaky Test Detector
        if: always()
        env:
          API_KEY: ${{{{ secrets.DETECTOR_API_KEY }}}}
        run: |
          DETECTOR_URL="https://flaky-test-detector-kbpc.onrender.com"
          curl -s -o junit_ingest.py https://raw.githubusercontent.com/JNamu12/Flaky-Test-Detector/main/tools/junit_xml_to_ingest.py
          if [ -f results/junit.xml ]; then
            python junit_ingest.py results/junit.xml \
              --url "${{DETECTOR_URL}}/api/v1/test-runs/ingest" \
              --commit-sha "${{{{ github.sha }}}}" \
              --api-key "${{API_KEY}}"
          fi</code></pre>
      </div>
    </section>

    <!-- SECTION 8: EVOLUTION TIMELINE -->
    <section id="evolution-timeline" class="section-block">
      <h2 class="section-title">⏳ 8. Complete Project Evolution Timeline</h2>
      <p class="section-subtitle">Chronological record of key architectural milestones and decisions.</p>

      <div class="timeline-item">
        <div class="timeline-date">Phase 1: Project Scaffolding</div>
        <div class="timeline-title">FastAPI Backend, SQLAlchemy Models & Groq Llama 3.1 Setup</div>
        <p>Created Pydantic schemas (<code>TestRun</code>, <code>TestRunBatch</code>, <code>FlakyTestSummary</code>), SQLite database layer, and initial Groq LLM root-cause analyzer.</p>
      </div>

      <div class="timeline-item">
        <div class="timeline-date">Phase 2: UI Dashboard & Heuristic Categorizer</div>
        <div class="timeline-title">Single-File Dashboard with Dark/Light Theme & History Strips</div>
        <p>Created zero-dependency <code>dashboard.html</code> with 14-run history rectangles, transition-based score badges, and pure JS error normalization.</p>
      </div>

      <div class="timeline-item">
        <div class="timeline-date">Phase 3: Render Free Tier Optimization</div>
        <div class="timeline-title">Memory Footprint Reduction (~35MB RAM) & Persistent Disk Mount</div>
        <p>Eliminated 502 Bad Gateway OOM errors by replacing local PyTorch with Groq Cloud API, mounting persistent storage at <code>/data</code>, and adding <code>.seeded</code> guard.</p>
      </div>

      <div class="timeline-item">
        <div class="timeline-date">Phase 4: Slide-Over Drawer & UX Polish</div>
        <div class="timeline-title">720px Slide-Over Drawer, Timezone Engine & Tag Stripping</div>
        <p>Replaced bottom detail panel with a modern slide-over drawer, added <code>parseUTCDate()</code> for local IST timezone rendering, and created <code>clean_test_name()</code> to strip <code>@demo</code> tags from XML.</p>
      </div>

      <div class="timeline-item">
        <div class="timeline-date">Phase 5: Live Demo & Reliability</div>
        <div class="timeline-title">15-Second Fast Live Demo Workflow & 24/7 Keep-Awake Cron</div>
        <p>Created dedicated <code>LIVE DEMO — fast subset</code> GitHub Actions workflow and automated 10-minute <code>keep-awake.yml</code> cron to prevent Render sleep.</p>
      </div>
    </section>

    <!-- SECTION 9: QA & TROUBLESHOOTING LOG -->
    <section id="troubleshooting-log" class="section-block">
      <h2 class="section-title">🛠️ 9. QA & Troubleshooting Log</h2>
      <p class="section-subtitle">Resolution of edge cases, bug reports, and optimizations encountered.</p>

      <div class="table-container">
        <table>
          <thead>
            <tr><th>Issue / Bug Encountered</th><th>Root Cause</th><th>Engineering Fix Applied</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Render 502 Bad Gateway / OOM</strong></td>
              <td>SentenceTransformers PyTorch package exceeded 512MB RAM free limit.</td>
              <td>Switched to Groq Cloud API and reduced Docker RAM footprint to ~35MB.</td>
            </tr>
            <tr>
              <td><strong>Real Data Lost on Restart</strong></td>
              <td>SQLite DB path was in ephemeral storage and seed script ran on boot.</td>
              <td>Mounted persistent volume at <code>/data</code> with <code>.seeded</code> guard file.</td>
            </tr>
            <tr>
              <td><strong>Timestamp Showed 02:13 Instead of 07:44</strong></td>
              <td>Browser parsed UTC string without 'Z' as naive local time.</td>
              <td>Implemented <code>parseUTCDate()</code> to enforce UTC parsing before browser local conversion.</td>
            </tr>
            <tr>
              <td><strong>Tag '@demo' in Test Names</strong></td>
              <td>Playwright tags in test title were ingested literally.</td>
              <td>Created regex cleaner <code>re.sub(r'(?:\s+@[\w-]+)+$', '', name)</code> in parser layer.</td>
            </tr>
            <tr>
              <td><strong>Scrolling Needed for Details</strong></td>
              <td>Detail panel opened at bottom of 100+ row table.</td>
              <td>Converted to 720px right-side slide-over drawer with backdrop blur.</td>
            </tr>
            <tr>
              <td><strong>Render Sleeping During Demos</strong></td>
              <td>Render Free Tier spins down after 15 minutes of inactivity.</td>
              <td>Added <code>keep-awake.yml</code> cron pinging <code>/health</code> every 10 minutes.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- SECTION 10: PROMPTS ARCHIVE (1-85) -->
    <section id="prompts-archive" class="section-block">
      <h2 class="section-title">📜 10. Comprehensive Prompts Archive (Prompts 1 – 85)</h2>
      <p class="section-subtitle">Every prompt and engineering request recorded across all development sessions.</p>

      <div id="prompts-list">
        {all_prompts_html}
      </div>
    </section>

    <footer>
      <p>🧪 <strong>Flaky Test Detector</strong> • Master Technical Knowledge Transfer Document</p>
      <p style="margin-top:0.35rem;font-size:0.78rem;color:var(--text-soft);">Complete Historical Archive & Architectural Blueprints • September 2026</p>
    </footer>

  </main>

  <script>
    function togglePrompt(headerEl) {{
      const parent = headerEl.parentElement;
      parent.classList.toggle('open');
    }}

    function switchTab(evt, tabId) {{
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
      evt.currentTarget.classList.add('active');
      const target = document.getElementById(tabId);
      if (target) target.classList.add('active');
    }}

    function filterSidebar(query) {{
      const q = query.toLowerCase();
      const items = document.querySelectorAll('#sidebar-menu .nav-item');
      items.forEach(item => {{
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      }});
      const prompts = document.querySelectorAll('#prompts-list .prompt-box');
      prompts.forEach(p => {{
        const text = p.textContent.toLowerCase();
        p.style.display = text.includes(q) ? 'block' : 'none';
      }});
    }}

    window.addEventListener('scroll', () => {{
      const sections = document.querySelectorAll('section');
      const scrollPos = window.scrollY + 120;
      sections.forEach(sec => {{
        if (scrollPos >= sec.offsetTop && scrollPos < sec.offsetTop + sec.offsetHeight) {{
          const id = sec.getAttribute('id');
          document.querySelectorAll('.sidebar-nav .nav-item').forEach(link => {{
            link.classList.toggle('active', link.getAttribute('href') === `#${{id}}`);
          }});
        }}
      }});
    }});
  </script>
</body>
</html>
"""

with open('KT_Documentation.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Generated KT_Documentation.html successfully! Size: {len(html_content)} bytes")
