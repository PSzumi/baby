# Setup Instructions for Angie

## Step 1: Delete old project (if exists)

```
rmdir /s /q projects\myproject
```

## Step 2: Create .env file

In the `baby` folder, run `notepad .env` and paste:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=<ask-pedro-for-key>
GROQ_API_KEY=<ask-pedro-for-key>
UNPAYWALL_EMAIL=angiesilvabrasil@gmail.com
CROSSREF_MAILTO=angiesilvabrasil@gmail.com
SEMANTIC_SCHOLAR_API_KEY=
CORE_API_KEY=
SCOPUS_API_KEY=<ask-pedro-for-key>
```

> **Ask Pedro for the actual API keys** — they can't be posted on GitHub.

Save and close Notepad.

## Step 3: Run the pipeline

```
research-cli init myproject --lang es --location "Lima, Perú" --university "USIL" --var1 "Estrés laboral" --var2 "Satisfacción laboral" --population "trabajadores de una empresa privada" --sample-size 120

research-cli fetch-data myproject --email angiesilvabrasil@gmail.com

research-cli review myproject --auto

research-cli scaffold myproject

research-cli draft myproject

research-cli export myproject
```

The final thesis will be at: `projects\myproject\outputs\v1\thesis.docx`

## Notes

- Default LLM is Gemini. To use Groq instead, change `LLM_PROVIDER=gemini` to `LLM_PROVIDER=groq` in `.env`
- Semantic Scholar and CORE keys are optional — they get skipped without a key
- If you get rate limit errors, wait a few minutes and re-run the same command (it resumes)
