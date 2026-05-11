# Modul eBay Discovery

Acest patch adaugă modulul `discovery`, folosit pentru căutarea oportunităților comerciale.

Flux:

1. Utilizatorul introduce keyword, buget maxim și Top N.
2. Aplicația caută produse prin eBay Browse API sau prin CSV fallback.
3. Produsele sunt ordonate după un scor comercial.
4. Utilizatorul apasă „Analizează investiția”.
5. Produsul este trimis către modulul ML existent pentru predicția succesului și estimarea prețului recomandat.

## Instalare patch

După copierea fișierelor în proiect:

```cmd
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Test rapid fără API

Intră la:

```text
http://127.0.0.1:8000/oportunitati/
```

Completează:

```text
Cuvânt cheie: smartwatch
Categorie: smartwatch
Buget maxim: 100
Rating minim: 4
Număr minim recenzii: 50
Număr rezultate: Top 5
Sursa datelor: CSV fallback
```

## Activare eBay API

1. Creează cont pe eBay Developer Program.
2. Creează un keyset Production sau Sandbox.
3. Copiază `.env.example` în `.env`.
4. Completează:

```text
EBAY_ENVIRONMENT=production
EBAY_MARKETPLACE_ID=EBAY_US
EBAY_CLIENT_ID=client_id_taul
EBAY_CLIENT_SECRET=client_secret_taul
```

Apoi repornește serverul.

Dacă API-ul nu este configurat sau dă eroare, aplicația revine automat la CSV fallback.
