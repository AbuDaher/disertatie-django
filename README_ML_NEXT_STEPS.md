# Pasul 2 - Modele Machine Learning

Acest patch adaugă:

- `sample_data/products_training.csv` - dataset sintetic pentru antrenare;
- `ml/train_models.py` - script de antrenare clasificare + regresie;
- `ml_artifacts/` - folder în care vor fi salvate modelele `.joblib`;
- `predictions/services.py` actualizat pentru a folosi modelul ML dacă există, altfel baseline;
- `products/views.py` actualizat pentru a salva în istoric numele modelului folosit.

## Comenzi

Rulează din rădăcina proiectului, cu `.venv` activ:

```cmd
python ml/train_models.py
python manage.py runserver
```

După rulare, ar trebui să apară fișierele:

```text
ml_artifacts/success_classifier.joblib
ml_artifacts/price_regressor.joblib
ml_artifacts/model_metadata.joblib
```

Apoi adaugă un produs nou din interfață. Predicția ar trebui să folosească modelele Random Forest, nu baseline-ul.
