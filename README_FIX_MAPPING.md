# Patch corectare mapping rating / recenzii

Acest patch corectează transferul datelor din modulul `discovery` către modulul ML.

Problema observată:
- `rating` putea apărea ca `99.2`, adică procentul de feedback al sellerului;
- `reviews` putea apărea ca `4`, adică ratingul produsului.

Corect după patch:
- `rating` = rating produs între 0 și 5;
- `review_count` = numărul de recenzii;
- `seller_feedback_percent` = procent feedback seller, păstrat separat;
- `seller_feedback_score` = scor feedback seller, păstrat separat.

După copierea patch-ului:
1. Oprește serverul cu CTRL+C.
2. Copiază fișierele peste proiect.
3. Pornește serverul:

```cmd
python manage.py runserver
```

Nu sunt necesare migrații.

Pentru test:
1. Intră la `/oportunitati/`.
2. Caută `smartwatch` cu CSV fallback.
3. Apasă „Analizează investiția”.
4. În rezultat trebuie să apară valori de tip:
   - rating: 4.7
   - reviews: 340
   - seller_feedback_percent: 99.2
