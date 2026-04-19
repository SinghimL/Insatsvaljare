# Insatsväljare för bostadsrätt

A net-worth forecaster that compares down-payment strategies for a Swedish bostadsrätt purchase under the 2026 mortgage rules. The tool weighs the cost of borrowing against the opportunity cost of locking cash in insats, and visualises — over a configurable holding period — how choosing a different belåningsgrad reshapes your terminal net worth under varying ränta scenarios, portföljavkastning, and skattekonto types (ISK, KF, or other).

## Kör lokalt

```bash
uv sync
uv run streamlit run src/insatsvaljare/app.py
```

Appen öppnas på http://localhost:8501.

Tester:
```bash
uv run pytest
```

## Deployment (Streamlit Cloud, gratis)

1. **Skapa GitHub-repo**:
   ```bash
   gh repo create Insatsvaljare --public --source=. --remote=origin --push
   ```

2. **Deploya**:
   - Gå till https://share.streamlit.io/
   - Logga in med GitHub
   - "New app" → välj repo `Insatsvaljare`, branch `main`, path `src/insatsvaljare/app.py`
   - Python version: `3.14`
   - Deploy

3. **Dela**: Appen får en URL i form `https://insatsvaljare-<hash>.streamlit.app`.

Alla deps hanteras via `requirements.txt`. Snapshot-data (Stabelo-räntor) ligger i `ref/stabelo_snapshot.json` och uppdateras manuellt via appens "🔄 Uppdatera Stabelo-räntor"-knapp.

### Alternativ: Railway / Render / Fly.io

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "src/insatsvaljare/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
```

## Projektstruktur

```
src/insatsvaljare/
  app.py         — Streamlit UI
  model.py       — Månadsvis simulering över valbar horisont
  rates.py       — LTV-påslag + scenarioräntor
  stabelo.py     — Turbo-stream parser + API-hämtning
  tax.py         — Ränteavdrag + ISK schablonskatt
  scenarios.py   — 3 scenarier + valfri AR(1) Monte Carlo
  defaults.py    — Stockholm 2026 standardparametrar
ref/
  swedish-mortgage-policy-2026.md  — politik + källor
  stabelo_snapshot.json            — cached rates (commit)
tests/
  test_{tax,rates,model,stabelo}.py
```

## Modellens kärnmekanism

Givet en fast mängd startkapital (insats + investeringsbuffert), välj LTV:
- **Låg LTV** → mer kapital låst i bostaden, mindre i portfölj, lägre räntekostnad
- **Hög LTV** → mer kapital investerat, högre räntekostnad, möjligt "spread"-spel mot portföljavkastning

Simuleringen räknar månadsvis kassaflöde, årsvis skattereglering (ränteavdrag + ISK schablonskatt), och rapporterar **terminal nettoförmögenhet** samt **inkrementell IRR vs. 90 % LTV-baseline** för varje scenario.

Se `ref/swedish-mortgage-policy-2026.md` för fullständig referens till 2026 års regler och räntekällor.
