# research-cli

Automated USIL academic thesis generation from real research data. Fetches papers from 9 scholarly databases, builds a verified citation database, and generates a complete thesis with proper 3-chapter USIL structure and DOCX export.

---

## Setup Instructions (Windows)

### Step 1: Install Python

1. Go to https://www.python.org/downloads/
2. Download **Python 3.12** (or any 3.10+)
3. Run the installer — **check the box "Add Python to PATH"** at the bottom
4. Click "Install Now"

### Step 2: Download the project

1. Open **Command Prompt** (press `Win + R`, type `cmd`, press Enter)
2. Navigate to where you want the project (e.g. your Desktop):
   ```
   cd %USERPROFILE%\Desktop
   ```
3. Clone the repo:
   ```
   git clone https://github.com/PSzumi/baby.git
   cd baby
   ```

> If `git` is not installed: download it from https://git-scm.com/download/win and install it (all defaults are fine), then reopen Command Prompt.

### Step 3: Create virtual environment and install

```
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

After this you should see `(.venv)` at the start of your command line.

### Step 4: Get a Gemini API key (free)

1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account
3. Click **"Create API Key"**
4. Copy the key

### Step 5: Create the .env file

In the `baby` folder, create a file called `.env`. The easiest way:

```
notepad .env
```

Paste this content and fill in your key:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=paste-your-key-here
UNPAYWALL_EMAIL=your.email@gmail.com
CROSSREF_MAILTO=your.email@gmail.com
```

Save and close Notepad.

### Step 6: Run it

Make sure the virtual environment is activated (`(.venv)` shows in your prompt). If not:
```
.venv\Scripts\activate
```

Then run each command one at a time, waiting for each to finish:

```
research-cli init myproject --lang es --location "Lima, Perú" --university "USIL" --var1 "Estrés laboral" --var2 "Satisfacción laboral" --population "trabajadores de una empresa privada" --sample-size 120

research-cli fetch-data myproject --email your.email@gmail.com

research-cli review myproject --auto

research-cli scaffold myproject

research-cli draft myproject

research-cli export myproject
```

The final thesis will be at: `projects\myproject\outputs\v1\thesis.docx`

### Every time you open a new Command Prompt

You need to activate the virtual environment first:
```
cd %USERPROFILE%\Desktop\baby
.venv\Scripts\activate
```

---

## Setup Instructions (Linux / macOS)

```bash
git clone https://github.com/PSzumi/baby.git
cd baby
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env: set GEMINI_API_KEY and UNPAYWALL_EMAIL
```

---

## Customizing your thesis

Change the `init` command variables to match your thesis topic:

| Flag | What it does |
|------|-------------|
| `--var1` | Independent variable name |
| `--var2` | Dependent variable name |
| `--population` | Who you are studying |
| `--sample-size` | Number of participants |
| `--location` | Geographic focus (used in Planteamiento del Problema) |
| `--university` | University name |
| `--lang es` | Spanish (use `en` for English) |
| `--career` | Career / academic program |

---

## Available commands

| Command | What it does |
|---------|-------------|
| `init` | Create project, set topic and variables |
| `fetch-data` | Search 9 academic databases for sources |
| `review` | Curate sources (use `--auto` to include all) |
| `scaffold` | Plan sections and assign sources |
| `draft` | Generate full thesis text section by section |
| `export` | Convert to USIL-formatted .docx |
| `present` | Generate presentation guide and Q&A |
| `revise` | Apply feedback to revise sections |
| `status` | Show project state |

---

## USIL thesis structure (26 sections)

```
Dedicatoria / Agradecimiento / Resumen / Abstract
Introducción
Capítulo 1
  1.1. Problema de Investigación
    1.1.1. Planteamiento del Problema
    1.1.2. Formulación del Problema
    1.1.3. Justificación de la Investigación
  1.2. Marco Referencial
    1.2.1. Antecedentes (internacionales + nacionales)
    1.2.2. Marco Teórico (Variable 1 + Variable 2)
  1.3. Objetivos e Hipótesis
Capítulo 2
  2.1. Método
    2.1.1–2.1.6. Tipo, Diseño, Variables, Muestra, Instrumentos, Procedimiento
Capítulo 3
  3.1. Resultados, Discusión, Conclusiones, Recomendaciones
Referencias Bibliográficas
Anexos (Matriz de consistencia)
```

---

## Troubleshooting

**"python is not recognized"** — Python wasn't added to PATH. Reinstall and check the "Add to PATH" box.

**"git is not recognized"** — Install git from https://git-scm.com/download/win and reopen Command Prompt.

**"No module named research_cli"** — Make sure you ran `pip install -e .` with the virtual environment activated.

**API rate limits / 429 errors** — The tool pauses between API calls automatically. If you still get errors, wait a few minutes and run the command again (it resumes where it left off).

**DOCX looks wrong** — Open the .docx in Word, right-click the Table of Contents and click "Update Field" to populate it.
