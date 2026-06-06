# Screenshots

These images are embedded in the main project README. Capture them from the
running Streamlit dashboard and save them here with the **exact filenames** below.

| Filename | What to capture |
|---|---|
| `dashboard-overview.png` | Top of the dashboard after running the pipeline — the row of metric cards (rules, tables, **Rule Conflicts**, **Incomplete Tables**, etc.). |
| `audit-tab.png` | The **🛡️ Audit** tab — conflict expanders + completeness table. |
| `rules-tab.png` | The **Rules** tab — the extracted business-rules table. |
| `ai-docs.png` | The **AI Docs** tab — an LLM-generated plain-English rule (needs Ollama running). |

## How to capture (Windows)

```powershell
cd C:\Users\shivraj\Projects
venv\Scripts\activate
streamlit run src/dashboard/app.py
```

1. Browser opens at `http://localhost:8501`. Upload a `.cbl` file (e.g. one from
   `data/cobol_corpus/aws_card_demo`) or a sample from `data/conflict_samples/`.
2. For each shot above, press **Win + Shift + S** (Snipping Tool), drag over the
   area, then paste into Paint and **Save As PNG** with the exact filename here.
3. Re-run the README embed check: the images appear automatically once committed.

> Tip: a clean, full-width browser window (hide bookmarks bar) looks most professional.
