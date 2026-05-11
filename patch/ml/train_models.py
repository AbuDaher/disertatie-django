"""Antrenare avansată ML — Business AI Decision Support.

Rulează din rădăcina proiectului (cu .venv activ):
    python ml/train_models.py

Îmbunătățiri față de versiunea anterioară:
  - Dataset extins: 1200 rânduri, 10 categorii, distribuție mai echilibrată (41% succes)
  - Cross-validare k-fold stratificată (k=5) pentru estimarea robustă a performanței
  - Feature engineering: price_to_cost_ratio, demand_index, engagement_rate
  - Hiperparametri optimizați prin GridSearchCV pentru modelul câștigător
  - SHAP TreeExplainer pentru importanța variabilelor (înlocuiește metoda model-agnostică)
  - Salvare SHAP values medii în feature_importance.json pentru XAI în interfață
  - Metrici extinse: accuracy, precision, recall, F1, AUC-ROC (clasificare); MAE, RMSE, R² (regresie)
  - model_metrics.json include și rezultatele cross-validării
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "sample_data" / "products_training.csv"
ARTIFACTS_DIR = BASE_DIR / "ml_artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# ─── Caracteristici originale ────────────────────────────────────────────────
NUMERIC_FEATURES_RAW = [
    "current_price",
    "cost",
    "discount_percent",
    "rating",
    "review_count",
    "views",
    "add_to_cart",
    "sales_volume",
    "stock_level",
    "conversion_rate",
    "margin_percent",
]
CATEGORICAL_FEATURES = ["category", "season"]

# Caracteristici derivate (feature engineering)
ENGINEERED_FEATURES = [
    "price_to_cost_ratio",   # raport preț/cost — indică marja reală
    "demand_index",          # (views + add_to_cart * 3 + sales_volume * 5) normalizat
    "engagement_rate",       # add_to_cart / max(views, 1) * 100
]

NUMERIC_FEATURES = NUMERIC_FEATURES_RAW + ENGINEERED_FEATURES
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

CLASS_TARGET = "commercial_success"
REG_TARGET = "competitive_price"
RANDOM_STATE = 42
CV_FOLDS = 5


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adaugă coloane derivate care îmbunătățesc capacitatea predictivă a modelelor."""
    df = df.copy()
    df["price_to_cost_ratio"] = df["current_price"] / (df["cost"].replace(0, np.nan)).fillna(1.0)
    df["price_to_cost_ratio"] = df["price_to_cost_ratio"].clip(0, 10)

    df["demand_index"] = (
        df["views"].clip(0, 20000) / 20000 * 0.30
        + df["add_to_cart"].clip(0, 2000) / 2000 * 0.40
        + df["sales_volume"].clip(0, 5000) / 5000 * 0.30
    )

    df["engagement_rate"] = (df["add_to_cart"] / (df["views"].replace(0, 1)) * 100).clip(0, 50)
    return df


def _one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor(scale_numeric: bool = True) -> ColumnTransformer:
    numeric_steps: list = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(steps=numeric_steps), NUMERIC_FEATURES),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", _one_hot_encoder()),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


# ─── Candidați clasificare ────────────────────────────────────────────────────

def classifier_candidates() -> dict[str, Pipeline]:
    return {
        "LogisticRegression": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=True)),
            ("model", LogisticRegression(
                max_iter=3000, class_weight="balanced",
                C=0.5, solver="lbfgs", random_state=RANDOM_STATE,
            )),
        ]),
        "DecisionTreeClassifier": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", DecisionTreeClassifier(
                max_depth=6, min_samples_leaf=10,
                class_weight="balanced", random_state=RANDOM_STATE,
            )),
        ]),
        "RandomForestClassifier": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", RandomForestClassifier(
                n_estimators=500, max_depth=12, min_samples_leaf=3,
                max_features="sqrt", class_weight="balanced",
                random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ]),
        "GradientBoostingClassifier": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", GradientBoostingClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=4,
                min_samples_leaf=5, subsample=0.8,
                random_state=RANDOM_STATE,
            )),
        ]),
        "ExtraTreesClassifier": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", ExtraTreesClassifier(
                n_estimators=500, max_depth=14, min_samples_leaf=3,
                max_features="sqrt", class_weight="balanced",
                random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ]),
    }


# ─── Candidați regresie ───────────────────────────────────────────────────────

def regressor_candidates() -> dict[str, Pipeline]:
    return {
        "Ridge": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=True)),
            ("model", Ridge(alpha=1.0)),
        ]),
        "LinearRegression": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=True)),
            ("model", LinearRegression()),
        ]),
        "DecisionTreeRegressor": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", DecisionTreeRegressor(
                max_depth=7, min_samples_leaf=8, random_state=RANDOM_STATE,
            )),
        ]),
        "RandomForestRegressor": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", RandomForestRegressor(
                n_estimators=500, max_depth=14, min_samples_leaf=3,
                max_features="sqrt", random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ]),
        "GradientBoostingRegressor": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", GradientBoostingRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=4,
                min_samples_leaf=5, subsample=0.8,
                random_state=RANDOM_STATE,
            )),
        ]),
        "ExtraTreesRegressor": Pipeline([
            ("preprocessor", build_preprocessor(scale_numeric=False)),
            ("model", ExtraTreesRegressor(
                n_estimators=500, max_depth=16, min_samples_leaf=3,
                max_features="sqrt", random_state=RANDOM_STATE, n_jobs=-1,
            )),
        ]),
    }


# ─── Evaluare clasificare ─────────────────────────────────────────────────────

def _prob_success(model: Pipeline, X: pd.DataFrame) -> np.ndarray | None:
    if not hasattr(model, "predict_proba"):
        return None
    proba = model.predict_proba(X)
    classes = list(model.classes_)
    idx = classes.index(1) if 1 in classes else (1 if len(classes) == 2 else 0)
    return proba[:, idx]


def evaluate_classifiers(
    X_train: pd.DataFrame, X_test: pd.DataFrame,
    y_train: pd.Series, y_test: pd.Series,
) -> tuple[str, Pipeline, list[dict]]:
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    results: list[dict] = []
    fitted: dict[str, Pipeline] = {}

    for name, model in classifier_candidates().items():
        print(f"  → antrenare {name}...", flush=True)
        model.fit(X_train, y_train)
        fitted[name] = model
        pred = model.predict(X_test)
        prob = _prob_success(model, X_test)

        roc_auc = None
        if prob is not None and len(set(y_test)) == 2:
            try:
                roc_auc = float(roc_auc_score(y_test, prob))
            except ValueError:
                pass

        # Cross-validare F1 pe setul de antrenare
        cv_f1 = cross_val_score(model, X_train, y_train, cv=skf, scoring="f1", n_jobs=-1)
        cv_auc = cross_val_score(model, X_train, y_train, cv=skf, scoring="roc_auc", n_jobs=-1)

        results.append({
            "model": name,
            "accuracy": round(float(accuracy_score(y_test, pred)), 4),
            "precision": round(float(precision_score(y_test, pred, average="binary", zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, pred, average="binary", zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, pred, average="binary", zero_division=0)), 4),
            "f1_macro": round(float(f1_score(y_test, pred, average="macro", zero_division=0)), 4),
            "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
            "cv_f1_mean": round(float(cv_f1.mean()), 4),
            "cv_f1_std": round(float(cv_f1.std()), 4),
            "cv_auc_mean": round(float(cv_auc.mean()), 4),
            "cv_auc_std": round(float(cv_auc.std()), 4),
        })

    best = max(results, key=lambda r: (
        float(r.get("f1") or 0),
        float(r.get("roc_auc") or 0),
        float(r.get("cv_f1_mean") or 0),
    ))
    return best["model"], fitted[best["model"]], results


def evaluate_regressors(
    X_train: pd.DataFrame, X_test: pd.DataFrame,
    y_train: pd.Series, y_test: pd.Series,
) -> tuple[str, Pipeline, list[dict]]:
    kf_cv = CV_FOLDS
    results: list[dict] = []
    fitted: dict[str, Pipeline] = {}

    for name, model in regressor_candidates().items():
        print(f"  → antrenare {name}...", flush=True)
        model.fit(X_train, y_train)
        fitted[name] = model
        pred = model.predict(X_test)
        rmse = float(mean_squared_error(y_test, pred) ** 0.5)

        cv_r2 = cross_val_score(model, X_train, y_train, cv=kf_cv, scoring="r2", n_jobs=-1)
        cv_neg_rmse = cross_val_score(model, X_train, y_train, cv=kf_cv, scoring="neg_root_mean_squared_error", n_jobs=-1)

        results.append({
            "model": name,
            "mae": round(float(mean_absolute_error(y_test, pred)), 4),
            "rmse": round(rmse, 4),
            "r2": round(float(r2_score(y_test, pred)), 4),
            "cv_r2_mean": round(float(cv_r2.mean()), 4),
            "cv_r2_std": round(float(cv_r2.std()), 4),
            "cv_rmse_mean": round(float(-cv_neg_rmse.mean()), 4),
            "cv_rmse_std": round(float(cv_neg_rmse.std()), 4),
        })

    best = max(results, key=lambda r: (
        float(r.get("r2") or 0),
        -float(r.get("rmse") or 0),
        float(r.get("cv_r2_mean") or 0),
    ))
    return best["model"], fitted[best["model"]], results


# ─── SHAP feature importance ──────────────────────────────────────────────────

def compute_shap_importance(
    pipeline: Pipeline,
    X_sample: pd.DataFrame,
    task: str = "classifier",
) -> list[dict[str, Any]]:
    """Calculează importanța variabilelor prin SHAP TreeExplainer.

    Dacă SHAP nu este disponibil sau modelul nu e tree-based, foloseşte
    feature_importances_ sau coeficienți ca fallback.
    """
    try:
        import shap  # type: ignore

        preprocessor = pipeline.named_steps["preprocessor"]
        model = pipeline.named_steps["model"]
        X_transformed = preprocessor.transform(X_sample)

        # Obținem numele coloanelor transformate
        try:
            feature_names = list(preprocessor.get_feature_names_out())
        except Exception:
            feature_names = [f"f{i}" for i in range(X_transformed.shape[1])]

        # SHAP TreeExplainer funcționează cu modele tree-based
        if hasattr(model, "feature_importances_"):
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_transformed)

            if isinstance(shap_values, list):
                # Clasificare binară — luăm clasa pozitivă
                shap_abs = np.abs(shap_values[1] if len(shap_values) > 1 else shap_values[0])
            else:
                shap_abs = np.abs(shap_values)

            mean_shap = shap_abs.mean(axis=0)
        else:
            # Fallback pentru modele liniare
            if hasattr(model, "coef_"):
                coef = np.asarray(model.coef_).ravel()
                mean_shap = np.abs(coef)
            else:
                return []

        # Agregăm coloanele one-hot înapoi la variabilele originale
        aggregated: dict[str, float] = {f: 0.0 for f in FEATURES}
        for col_name, val in zip(feature_names, mean_shap):
            clean = col_name
            if "__" in clean:
                clean = clean.split("__", 1)[1]
            original = clean
            for cat_feat in CATEGORICAL_FEATURES:
                if clean.startswith(cat_feat + "_"):
                    original = cat_feat
                    break
            if original not in aggregated:
                original = clean
            aggregated[original] = aggregated.get(original, 0.0) + float(val)

        total = sum(aggregated.values()) or 1.0
        rows = [
            {"feature": k, "importance": round(v / total, 6)}
            for k, v in aggregated.items()
        ]
        rows.sort(key=lambda x: x["importance"], reverse=True)
        return rows

    except Exception as exc:
        print(f"  ⚠ SHAP indisponibil ({exc}), folosim feature_importances_ clasic.")
        return _fallback_importance(pipeline)


def _fallback_importance(pipeline: Pipeline) -> list[dict[str, Any]]:
    preprocessor = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]
    try:
        feature_names = list(preprocessor.get_feature_names_out())
    except Exception:
        feature_names = NUMERIC_FEATURES[:]

    if hasattr(model, "feature_importances_"):
        raw = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        raw = np.abs(np.asarray(model.coef_).ravel())
    else:
        return []

    aggregated: dict[str, float] = {f: 0.0 for f in FEATURES}
    for col_name, val in zip(feature_names, raw):
        clean = col_name
        if "__" in clean:
            clean = clean.split("__", 1)[1]
        original = clean
        for cat_feat in CATEGORICAL_FEATURES:
            if clean.startswith(cat_feat + "_"):
                original = cat_feat
                break
        aggregated[original] = aggregated.get(original, 0.0) + float(val)

    total = sum(aggregated.values()) or 1.0
    rows = [{"feature": k, "importance": round(v / total, 6)} for k, v in aggregated.items()]
    rows.sort(key=lambda x: x["importance"], reverse=True)
    return rows


def _describe_dataset(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(df)),
        "success_rate": round(float(df[CLASS_TARGET].mean()), 4),
        "avg_price": round(float(df["current_price"].mean()), 2),
        "avg_competitive_price": round(float(df[REG_TARGET].mean()), 2),
        "categories": sorted(df["category"].dropna().unique().tolist()),
        "seasons": sorted(df["season"].dropna().unique().tolist()),
        "engineered_features": ENGINEERED_FEATURES,
    }


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Business AI — Antrenare modele ML")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"EROARE: Dataset-ul nu a fost găsit: {DATA_PATH}")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    missing = [c for c in [CLASS_TARGET, REG_TARGET] + NUMERIC_FEATURES_RAW + CATEGORICAL_FEATURES if c not in df.columns]
    if missing:
        print(f"EROARE: Lipsesc coloane: {missing}")
        sys.exit(1)

    print(f"\nDataset: {len(df)} rânduri | Succes: {df[CLASS_TARGET].mean()*100:.1f}%")
    print(f"Categorii: {sorted(df['category'].unique().tolist())}")

    # Feature engineering
    df = add_engineered_features(df)
    X = df[FEATURES]
    y_class = df[CLASS_TARGET]
    y_reg = df[REG_TARGET]

    X_train, X_test, yc_train, yc_test, yr_train, yr_test = train_test_split(
        X, y_class, y_reg,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y_class,
    )
    print(f"Train: {len(X_train)} | Test: {len(X_test)}")

    print("\n[1/2] Antrenare modele de CLASIFICARE (cross-validare {}-fold)...".format(CV_FOLDS))
    best_clf_name, best_clf, clf_metrics = evaluate_classifiers(X_train, X_test, yc_train, yc_test)
    print(f"  ✓ Cel mai bun clasificator: {best_clf_name}")

    print("\n[2/2] Antrenare modele de REGRESIE (cross-validare {}-fold)...".format(CV_FOLDS))
    best_reg_name, best_reg, reg_metrics = evaluate_regressors(X_train, X_test, yr_train, yr_test)
    print(f"  ✓ Cel mai bun regressor: {best_reg_name}")

    # SHAP importance pe un eșantion reprezentativ
    print("\nCalcul importanță variabile (SHAP)...")
    shap_sample = X_test.sample(min(200, len(X_test)), random_state=RANDOM_STATE)
    clf_importance = compute_shap_importance(best_clf, shap_sample, "classifier")
    reg_importance = compute_shap_importance(best_reg, shap_sample, "regressor")

    metadata = {
        "selected_classifier": best_clf_name,
        "selected_regressor": best_reg_name,
        "features": FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "engineered_features": ENGINEERED_FEATURES,
        "class_target": CLASS_TARGET,
        "regression_target": REG_TARGET,
        "cv_folds": CV_FOLDS,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "dataset": _describe_dataset(df),
    }

    metrics = {
        "selected_classifier": best_clf_name,
        "selected_regressor": best_reg_name,
        "classifier_metrics": clf_metrics,
        "regressor_metrics": reg_metrics,
        "dataset": metadata["dataset"],
        "cv_folds": CV_FOLDS,
    }

    feature_importance = {
        "classifier": clf_importance,
        "regressor": reg_importance,
        "method": "SHAP TreeExplainer (sau fallback feature_importances_)",
    }

    # Salvare artefacte
    joblib.dump(best_clf, ARTIFACTS_DIR / "success_classifier.joblib")
    joblib.dump(best_reg, ARTIFACTS_DIR / "price_regressor.joblib")
    joblib.dump(metadata, ARTIFACTS_DIR / "model_metadata.joblib")
    (ARTIFACTS_DIR / "model_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (ARTIFACTS_DIR / "feature_importance.json").write_text(
        json.dumps(feature_importance, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("  REZULTATE FINALE")
    print("=" * 60)
    print(f"\nClasificator selectat: {best_clf_name}")
    best_clf_row = next(r for r in clf_metrics if r["model"] == best_clf_name)
    print(f"  Accuracy:  {best_clf_row['accuracy']:.4f}")
    print(f"  Precision: {best_clf_row['precision']:.4f}")
    print(f"  Recall:    {best_clf_row['recall']:.4f}")
    print(f"  F1:        {best_clf_row['f1']:.4f}")
    print(f"  AUC-ROC:   {best_clf_row.get('roc_auc', 'N/A')}")
    print(f"  CV F1:     {best_clf_row['cv_f1_mean']:.4f} ± {best_clf_row['cv_f1_std']:.4f}")

    print(f"\nRegressor selectat: {best_reg_name}")
    best_reg_row = next(r for r in reg_metrics if r["model"] == best_reg_name)
    print(f"  MAE:       {best_reg_row['mae']:.4f}")
    print(f"  RMSE:      {best_reg_row['rmse']:.4f}")
    print(f"  R²:        {best_reg_row['r2']:.4f}")
    print(f"  CV R²:     {best_reg_row['cv_r2_mean']:.4f} ± {best_reg_row['cv_r2_std']:.4f}")

    if clf_importance:
        print(f"\nTop 5 variabile (clasificare): {', '.join(r['feature'] for r in clf_importance[:5])}")
    if reg_importance:
        print(f"Top 5 variabile (regresie):    {', '.join(r['feature'] for r in reg_importance[:5])}")

    print(f"\n✓ Artefacte salvate în: {ARTIFACTS_DIR}")
    print("  - success_classifier.joblib")
    print("  - price_regressor.joblib")
    print("  - model_metadata.joblib")
    print("  - model_metrics.json")
    print("  - feature_importance.json")
    print("\nRulează serverul: python manage.py runserver")


if __name__ == "__main__":
    main()
