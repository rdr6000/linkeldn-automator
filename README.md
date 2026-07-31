# 🚀 LinkedIn Automation System (MCP-First + FastAPI Web UI)

A modern, cross-platform (macOS, Windows, Linux), AI-powered LinkedIn automation engine built with an **MCP-First architecture** (Model Context Protocol). 

It features an **Apple/Linear-inspired dark Web UI dashboard**, real-time progress bars, parallel batch AI acceleration, comprehensive MCP search controls, human anti-bot protection algorithms, persistent configuration, and granular approval workflows.

---

## 🌟 Key Features

- **⚡ Fast Parallel Batch AI Acceleration**:
  - Runs AI generation concurrently in parallel batches (5 at a time) via `asyncio.gather()`, cutting multi-comment generation latency from 30s to ~2s.

- **📡 Realtime SSE (Server-Sent Events) Zero-Latency Log Streaming**:
  - Pushes live log console output and progress percentages instantly using SSE streaming (`/api/jobs/{id}/stream-logs`) on `http://localhost:8000/jobs/{id}`.

- **📊 Analytics & Engagement Conversion Dashboard**:
  - Interactive dashboard (`http://localhost:8000/analytics`) showing total action execution counts, success rates, comments vs connection metrics, 7-day daily activity bar chart, and target engagement history.

- **👤 Multi-Account Profile Management**:
  - Easily switch or create isolated profile session profiles (`default`, `work_profile`, `client_account`) directly from Settings (`http://localhost:8000/settings`).

- **🔍 Comprehensive MCP Search & Querying Settings**:
  - **Feed Controls**: Enable/disable feed collection, set feed limit, and toggle ordering (`Most Recent` vs `Top Recommended`).
  - **Post Search Filters**: Keywords, recency filters (`Past 24h`, `Past Week`, `Past Month`), sort order (`Relevance` vs `Date Posted`), and content type filters (`Videos`, `Photos`, `Documents`).
  - **People Search Filters**: Keywords, connection degree targeting (`1st`, `2nd`, `3rd`, `All`), Job Title filter (e.g. `CEO`, `Founder`), and Location filter (e.g. `United States`, `London`).

- **✉️ Separated Custom Note Settings & Per-Card Checkboxes**:
  - **Generate Custom Notes**: Toggle AI note generation during job runs to save AI token costs and latency.
  - **Send Custom Notes**: Toggle default send state for connection notes.
  - **Per-Card Checkbox**: Inline checkbox on each approval card in the UI (`[x] Include custom note with invite`) to easily send or skip custom notes per person.

- **🛡️ Custom Note Quota Auto-Recovery & Playwright Fallback**:
  - If a free LinkedIn account hits monthly custom note limits (`custom_note_limit_reached`), the system automatically recovers by sending the connection request **without a note**, ensuring connections still go through!

- **👤 Smart Author Name & Post Context Extraction**:
  - Intelligently extracts author names from MCP responses or parses profile names directly from URL slugs (e.g. `https://linkedin.com/posts/komal-bajaj-...` $\rightarrow$ `Komal Bajaj`).
  - Renders full target post content context directly in the Approvals Queue and Job Detail views.

- **🤖 Dual AI Provider Support (Gemini & OpenAI)**:
  - Toggle between **Google Gemini** (e.g., `gemini-2.5-flash`, `gemini-1.5-flash`) and **OpenAI** (e.g., `gpt-4o-mini`, `gpt-4o`, `o3-mini`).
  - Includes 10 curated models sorted from lowest to highest input price with live pricing badges.

- **🛡️ Human Anti-Bot & Anti-Ban Protection**:
  - **Realistic Typing Simulation**: Keystroke timing variances (45ms–125ms), punctuation pauses, shift key overhead, and mid-sentence hesitations.
  - **Organic Page Dynamics**: Pre-action reading delays (4–7s), human scroll trajectories, mouse hover delays, and post-submission lingering.

- **🗑️ Danger Zone Data Reset**:
  - One-click button in Settings to safely clear all jobs, pending approvals, and execution history logs.

---

## 🛠️ Prerequisites

- **Python 3.10+** installed.
- **Node.js 18+** installed (required for running `uvx mcp-server-linkedin`).
- An active LinkedIn Account logged in via `npx -y mcp-server-linkedin`.
- Either a **Google Gemini API Key** OR an **OpenAI API Key**.

---

## 📥 Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/linkedin-auto.git
   cd linkedin-auto
   ```

2. **Create and Activate a Virtual Environment**:
   - **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows**:
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Chromium Browser**:
   ```bash
   playwright install chromium
   ```

---

## 🔐 Authentication Setup (LinkedIn MCP)

This system uses the Model Context Protocol (MCP) server for LinkedIn.

1. **Run MCP Authentication Once**:
   ```bash
   npx -y mcp-server-linkedin
   ```
   *Follow the on-screen browser prompt to log into your LinkedIn account. The session will automatically save to `~/.linkedin-mcp/profile`.*

2. **Set API Key Environment Variables**:
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   MCP_URL=http://localhost:8001/mcp
   HEADLESS=true
   MODE=approval
   ```

3. **Default Configuration Persistence (`config.default.yaml`)**:
   - The repository includes a default template file [`config.default.yaml`](file:///C:/Personal/Krinal/linkledn/config.default.yaml) tracked by Git.
   - On first launch, if `config.yaml` does not exist, the system automatically initializes `config.yaml` from `config.default.yaml`.
   - `config.yaml` is listed in `.gitignore` so your personal local settings and search configurations remain private and uncommitted.

---

## 🚀 Running the System

Start both the **LinkedIn MCP Server** (port 8001) and the **FastAPI Web UI Dashboard** (port 8000) with a single command:

```bash
python main.py --all
```

### Access Points
- **Web UI Dashboard**: `http://localhost:8000`
- **Approvals Queue**: `http://localhost:8000/approvals`
- **Jobs Log History**: `http://localhost:8000/jobs`
- **Settings & AI Configuration**: `http://localhost:8000/settings`
- **MCP Server Endpoint**: `http://localhost:8001/mcp`

---

## 📖 Operational Workflow

### 1. Approval Mode (Default)
1. Navigate to **Dashboard** (`http://localhost:8000`) and click **⚡ Run Automation Job**.
2. Select which actions to run (Comments, Likes, Connections, Follows).
3. System fetches feed posts and candidate profiles via MCP, filters out duplicates, and generates anti-slop responses in fast parallel batches.
4. Go to **Approvals** (`http://localhost:8000/approvals`) to review generated comments alongside full target post content.
5. Toggle individual custom notes via the per-card checkbox (`[x] Include custom note with invite`), click **🔄 Regenerate with AI**, or click **Approve & Execute Now**.

### 2. Autonomous Mode
Set **Automation Mode** to `Autonomous` in Settings or `.env`. The system will automatically collect, generate, and execute all actions directly without manual intervention.

---

## 🧪 Running Tests

Verify system integrity with the full unit and integration test suite:

```bash
pytest -v
```

---

## 📁 Project Structure

```
├── app/
│   ├── ai_client.py         # Unified AI client router (Gemini & OpenAI)
│   ├── config.py            # Pydantic settings & config.yaml persistence
│   ├── database.py          # SQLite database connection & lightweight migrations
│   ├── gemini_client.py     # Google Gemini API integration & prompt templates
│   ├── openai_client.py     # OpenAI API integration & prompt templates
│   ├── models.py            # SQLAlchemy ORM models & Pydantic schemas
│   ├── linkedin/
│   │   ├── comment_like.py  # Playwright human-simulated comment/like automation
│   │   ├── connect.py       # Playwright fallback connection automation
│   │   └── ad_filter.py     # Sponsored post and advertisement detection
│   ├── mcp/
│   │   ├── client.py        # Client for mcp-server-linkedin (JSON-RPC stdio/HTTP)
│   │   └── tools.py         # Typed MCP helper methods for feed & profile search
│   ├── routers/             # FastAPI HTTP routes (dashboard, jobs, approvals, settings)
│   ├── services/            # Core business logic (collector, executor, generator, job_runner)
│   ├── static/              # Apple/Linear Minimalist CSS stylesheet
│   └── templates/           # Jinja2 HTML templates
├── data/                    # Local SQLite history database directory
├── main.py                  # CLI entry point to launch MCP server + FastAPI Web UI
├── start.py                 # Cross-platform runner script
└── tests/                   # Pytest automated test suite
```

---

## 📜 License
MIT License. Created for safe, human-centric LinkedIn networking automation.
