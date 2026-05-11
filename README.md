# Business AI Decision Support - Django MVP

Aplicație Django pentru disertație: evaluarea potențialului de succes al produselor și estimarea unui preț competitiv.

## Rulare locală în PyCharm / terminal

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Deschide: http://127.0.0.1:8000/

## Module

- `products`: introducere date produs.
- `predictions`: predicție succes + preț recomandat + explicații baseline.
- `datasets`: upload și validare CSV.
- `analytics`: dashboard BI peste istoricul predicțiilor.

## Următorul pas tehnic

Înlocuirea funcției `baseline_predict` cu modele scikit-learn antrenate:
- clasificator pentru `success_label` / `success_probability`;
- regressor pentru `recommended_price`;
- SHAP pentru explicații locale și globale.
