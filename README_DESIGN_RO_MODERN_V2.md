# Patch design modern + interfață integral în română

Acest patch înlocuiește vechiul aspect al platformei cu un design modern de tip SaaS și standardizează limba interfeței în română.

## Conținut

- `templates/base.html` — layout global modern, navbar și footer în română.
- `static/css/app.css` — design system complet: carduri, formulare, tabele, KPI-uri, butoane, badge-uri.
- `products/forms.py` — etichete și explicații în română pentru formularul de evaluare produs.
- `discovery/forms.py` — etichete în română pentru căutarea oportunităților comerciale.
- `investment/forms.py` — etichete în română pentru analiza investițională.
- `datasets/forms.py` — etichete în română pentru încărcarea CSV.
- `products/templatetags/ro_labels.py` — filtru pentru traducerea automată a cheilor tehnice afișate în tabele.
- template-uri modernizate pentru: Acasă, Evaluare produs, Oportunități, Predicții, Investiții, Dashboard BI și Încărcare CSV.

## Aplicare

1. Oprește serverul:

```cmd
CTRL + C
```

2. Dezarhivează conținutul arhivei peste proiectul tău:

```text
C:\Users\Acer\PycharmProjects\django_business_ai_mvp
```

3. Alege `Replace the files in the destination`.

4. Rulează verificarea:

```cmd
python manage.py check
```

5. Pornește serverul:

```cmd
python manage.py runserver
```

6. În browser folosește refresh complet:

```text
CTRL + F5
```

## Observație

Nu sunt necesare migrații. Patch-ul modifică doar interfața, formularele și template-urile.

## Verificare rapidă pentru cuvinte rămase în engleză

În PowerShell, din rădăcina proiectului, poți rula:

```powershell
Select-String -Path .\templates\**\*.html,.\products\*.py,.\discovery\*.py,.\investment\*.py,.\datasets\*.py -Pattern "Name|Category|Current price|Review count|Sales volume|Stock level|Conversion rate|Submit|Search|Upload|Dashboard|Prediction|Source|Details|Back|Save|Cost|Season"
```

Dacă apar rezultate, verifică dacă sunt nume tehnice interne sau texte vizibile utilizatorului. Numele tehnice interne pot rămâne în engleză; textele vizibile trebuie traduse.
