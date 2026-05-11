# Patch CSV Import + Predicții automate

Acest patch transformă pagina „Încărcare CSV” într-un flux complet:

1. încarcă fișierul CSV;
2. creează produse în baza de date;
3. rulează automat modelul ML pentru fiecare produs;
4. salvează predicțiile în `PredictionRun`;
5. actualizează „Istoric predicții” și „Tablou de bord BI”.

## Aplicare

1. Oprește serverul:

```cmd
CTRL + C
```

2. Dezarhivează patch-ul peste proiect:

```text
C:\Users\Acer\PycharmProjects\django_business_ai_mvp
```

3. Alege `Replace the files in the destination`.

4. Rulează:

```cmd
python manage.py check
python manage.py runserver
```

Nu sunt necesare migrații.

## Coloane minime CSV

```text
name, category, current_price
```

## Coloane recomandate

```text
name, category, brand, current_price, cost, discount_percent, rating, review_count, views, add_to_cart, sales_volume, stock_level, conversion_rate, margin_percent, season
```

După upload verifică:

```text
/date/upload/
/predictii/istoric/
/analize/
```
