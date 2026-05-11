# Patch design modern + interfață integral în limba română

Acest patch actualizează interfața platformei într-un stil modern, coerent și unitar și traduce etichetele vizibile în limba română.

## Ce include

- redesign global pentru `base.html` și `static/css/app.css`;
- navbar modern și unitar;
- carduri, tabele, formulare și butoane stilizate unitar;
- etichete românești pentru formularul de evaluare produs;
- etichete românești pentru căutare oportunități, încărcare CSV și analiză investițională;
- filtru Django `ro_label` / `ro_value` pentru traducerea cheilor tehnice afișate în tabele;
- actualizarea paginilor principale: Acasă, Evaluare produs, Oportunități, Rezultat predicție, Investiții, Istoric, Tablou de bord BI, Încărcare CSV.

## Aplicare

1. Dezarhivează conținutul peste rădăcina proiectului Django:

   `C:\Users\Acer\PycharmProjects\django_business_ai_mvp`

2. Alege `Replace the files in the destination`.

3. Oprește serverul și pornește-l din nou:

   `python manage.py check`

   `python manage.py runserver`

Nu sunt necesare migrații pentru acest patch.

## Verificare rapidă texte engleză rămase

În PowerShell, din folderul proiectului:

```powershell
Select-String -Path .\templates\**\*.html,.\products\**\*.py,.\discovery\**\*.py,.\investment\**\*.py,.\datasets\**\*.py -Pattern "Name|Category|Current price|Review count|Sales volume|Stock level|Conversion rate|Submit|Search|Upload|Dashboard|Prediction|Recommended price|Source|Score|Feature|Contribution"
```

Dacă apar rezultate în comentarii sau în nume tehnice interne, nu este o problemă. Important este să nu fie afișate în interfața utilizatorului.
