"""Serviciu de predicție ML — Business AI Decision Support.

Ierarhie de fallback:
  1. Modele ML antrenate (joblib) + SHAP local explainer
  2. Modele ML antrenate + importanță globală (dacă SHAP eșuează)
  3. Baseline determinist (dacă ml_artifacts lipsesc)
"""

from __future__ import annotations

import json
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from django.conf import settings

warnings.filterwarnings("ignore")

MODEL_DIR = Path(settings.BASE_DIR) / "ml_artifacts"
CLASSIFIER_PATH = MODEL_DIR / "success_classifier.joblib"
REGRESSOR_PATH = MODEL_DIR / "price_regressor.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.joblib"
METRICS_PATH = MODEL_DIR / "model_metrics.json"
FEATURE_IMPORTANCE_PATH = MODEL_DIR / "feature_importance.json"

# ─── Caracteristici ───────────────────────────────────────────────────────────

NUMERIC_FEATURES_RAW = [
    "current_price", "cost", "discount_percent", "rating", "review_count",
    "views", "add_to_cart", "sales_volume", "stock_level",
    "conversion_rate", "margin_percent",
]
ENGINEERED_FEATURES = ["price_to_cost_ratio", "demand_index", "engagement_rate"]
NUMERIC_FEATURES = NUMERIC_FEATURES_RAW + ENGINEERED_FEATURES
CATEGORICAL_FEATURES = ["category", "season"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

FEATURE_LABELS = {
    "current_price": "Prețul curent",
    "cost": "Costul de achiziție",
    "discount_percent": "Discountul aplicat",
    "rating": "Ratingul produsului",
    "review_count": "Numărul de recenzii",
    "views": "Numărul de vizualizări",
    "add_to_cart": "Adăugările în coș",
    "sales_volume": "Volumul vânzărilor",
    "stock_level": "Nivelul stocului",
    "conversion_rate": "Rata de conversie",
    "margin_percent": "Marja comercială",
    "category": "Categoria produsului",
    "season": "Sezonalitatea",
    "price_to_cost_ratio": "Raportul preț/cost",
    "demand_index": "Indicele de cerere",
    "engagement_rate": "Rata de implicare",
}


# ─── Utilitare ────────────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ─── Feature engineering (trebuie să fie identic cu ml/train_models.py) ──────

def _add_engineered_features(features: dict[str, Any]) -> dict[str, Any]:
    price = _safe_float(features.get("current_price"), 1.0)
    cost = _safe_float(features.get("cost"), 1.0)
    views = _safe_float(features.get("views"), 0.0)
    add_to_cart = _safe_float(features.get("add_to_cart"), 0.0)
    sales_volume = _safe_float(features.get("sales_volume"), 0.0)

    features["price_to_cost_ratio"] = min(price / max(cost, 0.01), 10.0)
    features["demand_index"] = (
        min(views, 20000) / 20000 * 0.30
        + min(add_to_cart, 2000) / 2000 * 0.40
        + min(sales_volume, 5000) / 5000 * 0.30
    )
    features["engagement_rate"] = min(add_to_cart / max(views, 1) * 100, 50.0)
    return features


def build_feature_vector(product) -> dict[str, Any]:
    features = {
        "current_price": _safe_float(getattr(product, "current_price", 0)),
        "cost": _safe_float(getattr(product, "cost", 0)),
        "discount_percent": _safe_float(getattr(product, "discount_percent", 0)),
        "rating": _safe_float(getattr(product, "rating", 0)),
        "review_count": _safe_int(getattr(product, "review_count", 0)),
        "views": _safe_int(getattr(product, "views", 0)),
        "add_to_cart": _safe_int(getattr(product, "add_to_cart", 0)),
        "sales_volume": _safe_int(getattr(product, "sales_volume", 0)),
        "stock_level": _safe_int(getattr(product, "stock_level", 0)),
        "conversion_rate": _safe_float(getattr(product, "conversion_rate", 0)),
        "margin_percent": _safe_float(getattr(product, "margin_percent", 0)),
        "category": getattr(product, "category", None) or "Unknown",
        "season": getattr(product, "season", None) or "normal",
    }
    return _add_engineered_features(features)


def ml_artifacts_exist() -> bool:
    return CLASSIFIER_PATH.exists() and REGRESSOR_PATH.exists()


def get_model_metadata() -> dict[str, Any]:
    if METADATA_PATH.exists():
        try:
            loaded = joblib.load(METADATA_PATH)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return {
        "selected_classifier": "baseline_classifier",
        "selected_regressor": "baseline_regressor",
        "features": FEATURES,
    }


def get_model_metrics() -> dict[str, Any]:
    return _read_json(METRICS_PATH, {})


def get_feature_importance() -> dict[str, Any]:
    return _read_json(FEATURE_IMPORTANCE_PATH, {"classifier": [], "regressor": []})


# ─── XAI: SHAP local explanation ─────────────────────────────────────────────

def _shap_local_explanation(
    classifier: Any,
    X_row: pd.DataFrame,
    probability: float,
    features: dict[str, Any],
) -> dict[str, Any]:
    """Calculează contribuțiile SHAP locale pentru o singură predicție.

    Dacă SHAP nu este disponibil sau modelul nu suportă TreeExplainer,
    cade pe metoda bazată pe importanță globală.
    """
    try:
        import shap  # type: ignore

        model = classifier.named_steps["model"]
        preprocessor = classifier.named_steps["preprocessor"]
        X_transformed = preprocessor.transform(X_row)

        if not hasattr(model, "feature_importances_"):
            raise ValueError("Modelul nu suportă SHAP TreeExplainer.")

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_transformed)

        # Clasificare binară — clasa pozitivă
        if isinstance(shap_values, list):
            sv = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        else:
            sv = shap_values
        sv = sv[0]  # primul (și singurul) rând

        # Mapăm coloanele transformate înapoi la variabile originale
        try:
            col_names = list(preprocessor.get_feature_names_out())
        except Exception:
            col_names = [f"f{i}" for i in range(len(sv))]

        aggregated: dict[str, float] = {}
        for col, val in zip(col_names, sv):
            clean = col.split("__", 1)[1] if "__" in col else col
            original = clean
            for cat_feat in CATEGORICAL_FEATURES:
                if clean.startswith(cat_feat + "_"):
                    original = cat_feat
                    break
            aggregated[original] = aggregated.get(original, 0.0) + float(val)

        rows = [
            {
                "feature": feat,
                "label": FEATURE_LABELS.get(feat, feat),
                "value": round(_safe_float(features.get(feat), 0), 4),
                "impact": round(val, 5),
                "direction": "pozitiv" if val >= 0 else "negativ",
            }
            for feat, val in aggregated.items()
        ]
        rows.sort(key=lambda r: abs(r["impact"]), reverse=True)

        return _build_xai_output(rows, probability, method="SHAP TreeExplainer")

    except Exception:
        return _global_importance_xai(features, probability)


def _global_importance_xai(features: dict[str, Any], probability: float) -> dict[str, Any]:
    """Fallback XAI: folosește importanța globală și valorile locale."""
    importance_rows = get_feature_importance().get("classifier", [])
    importance = {r.get("feature"): float(r.get("importance") or 0) for r in importance_rows}

    if not importance:
        importance = {
            "demand_index": 0.20, "views": 0.14, "add_to_cart": 0.13,
            "sales_volume": 0.12, "rating": 0.11, "review_count": 0.10,
            "conversion_rate": 0.08, "margin_percent": 0.06,
            "engagement_rate": 0.05, "price_to_cost_ratio": 0.04,
            "stock_level": 0.03, "current_price": 0.02,
        }

    benchmarks = {
        "current_price": 165.0, "cost": 100.0, "discount_percent": 10.0,
        "rating": 4.0, "review_count": 150.0, "views": 2500.0,
        "add_to_cart": 180.0, "sales_volume": 80.0, "stock_level": 40.0,
        "conversion_rate": 3.5, "margin_percent": 38.0,
        "price_to_cost_ratio": 1.65, "demand_index": 0.35, "engagement_rate": 3.5,
    }

    rows = []
    for feat, baseline in benchmarks.items():
        value = _safe_float(features.get(feat), 0)
        weight = importance.get(feat, 0.01)
        if baseline == 0:
            relative = 0.0
        else:
            relative = (value - baseline) / abs(baseline)
        if feat in {"current_price", "cost"}:
            relative = -relative
        if feat == "stock_level" and value < 5:
            relative = -1.2
        contribution = max(-1.0, min(1.0, relative)) * weight
        rows.append({
            "feature": feat,
            "label": FEATURE_LABELS.get(feat, feat),
            "value": round(value, 4),
            "impact": round(contribution, 5),
            "direction": "pozitiv" if contribution >= 0 else "negativ",
        })

    rows.sort(key=lambda r: abs(r["impact"]), reverse=True)
    return _build_xai_output(rows, probability, method="importanță globală model-agnostică")


def _build_xai_output(rows: list[dict], probability: float, method: str) -> dict[str, Any]:
    positive = [r for r in rows if r["impact"] > 0][:5]
    negative = [r for r in rows if r["impact"] < 0][:5]

    if probability >= 0.70:
        verdict = "Modelul indică o oportunitate comercială favorabilă."
    elif probability >= 0.45:
        verdict = "Modelul indică un potențial comercial moderat, care necesită validare."
    else:
        verdict = "Modelul semnalează risc comercial ridicat; investiția trebuie analizată prudent."

    pos_text = ", ".join(r["label"] for r in positive) or "indicatorii comerciali disponibili"
    neg_text = ", ".join(r["label"] for r in negative) or "nu au fost identificați factori negativi majori"

    return {
        "xai_tip_explicatie": f"Explicație locală — {method}",
        "xai_rezumat": (
            f"{verdict} Factorii care susțin cel mai mult predicția sunt: {pos_text}. "
            f"Factorii limitativi principali sunt: {neg_text}."
        ),
        "xai_factori_pozitivi": positive,
        "xai_factori_negativi": negative,
        "xai_contributii_locale": rows[:12],
    }


# ─── Etichete ─────────────────────────────────────────────────────────────────

def _prob_success(classifier, row: pd.DataFrame, predicted_label: Any) -> float:
    if not hasattr(classifier, "predict_proba"):
        return 0.0
    proba = classifier.predict_proba(row)[0]
    classes = list(classifier.classes_)
    if 1 in classes:
        return float(proba[classes.index(1)])
    if predicted_label in classes:
        return float(proba[classes.index(predicted_label)])
    return float(max(proba))


def _label_for_probability(probability: float) -> str:
    if probability >= 0.70:
        return "Potențial ridicat de succes"
    if probability >= 0.45:
        return "Potențial mediu de succes"
    return "Potențial redus de succes"


# ─── Baseline (fără modele ML antrenate) ─────────────────────────────────────

def baseline_predict(product):
    f = build_feature_vector(product)
    demand = min(f["views"] / 3000, 1.0) * 0.20 + min(f["add_to_cart"] / 200, 1.0) * 0.18
    trust = min(f["rating"] / 5, 1.0) * 0.18 + min(f["review_count"] / 300, 1.0) * 0.12
    sales = min(f["sales_volume"] / 500, 1.0) * 0.15
    biz = min(f["conversion_rate"] / 10, 1.0) * 0.10 + min(f["margin_percent"] / 50, 1.0) * 0.07
    stock_risk = -0.08 if f["stock_level"] < 5 else 0.0
    probability = max(0.0, min(1.0, demand + trust + sales + biz + stock_risk))

    label = _label_for_probability(probability)
    price_adj = 1 + (probability - 0.5) * 0.15 - (f["discount_percent"] / 100) * 0.05
    recommended_price = max(1.0, _safe_float(f["current_price"], 10.0) * price_adj)

    explanation = {
        "model_utilizat": "baseline determinist",
        "probabilitate_succes_ml": round(probability, 4),
        "pret_recomandat_ml": round(recommended_price, 2),
        **{k: f[k] for k in ["views", "add_to_cart", "rating", "review_count",
                              "sales_volume", "conversion_rate", "margin_percent",
                              "stock_level", "demand_index", "engagement_rate",
                              "price_to_cost_ratio"]},
    }
    explanation.update(_global_importance_xai(f, probability))
    return probability, label, Decimal(str(round(recommended_price, 2))), explanation


# ─── Predicție ML principală ──────────────────────────────────────────────────

def ml_predict(product):
    if not ml_artifacts_exist():
        return baseline_predict(product)

    try:
        classifier = joblib.load(CLASSIFIER_PATH)
        regressor = joblib.load(REGRESSOR_PATH)
        metadata = get_model_metadata()

        features = build_feature_vector(product)
        row = pd.DataFrame([features], columns=FEATURES)

        predicted_class = classifier.predict(row)[0]
        probability = _prob_success(classifier, row, predicted_class)
        recommended_price = max(1.0, float(regressor.predict(row)[0]))
        label = _label_for_probability(probability)

        clf_name = metadata.get("selected_classifier", "ML Classifier")
        reg_name = metadata.get("selected_regressor", "ML Regressor")

        explanation = {
            "model_utilizat": f"{clf_name} + {reg_name}",
            "model_clasificare_selectat": clf_name,
            "model_regresie_selectat": reg_name,
            "probabilitate_succes_ml": round(probability, 4),
            "pret_recomandat_ml": round(recommended_price, 2),
            **{k: features[k] for k in ["rating", "review_count", "views", "add_to_cart",
                                         "sales_volume", "conversion_rate", "margin_percent",
                                         "stock_level", "demand_index", "engagement_rate",
                                         "price_to_cost_ratio"]},
        }
        # XAI local — încearcă SHAP, cade pe global importance
        explanation.update(_shap_local_explanation(classifier, row, probability, features))

        return probability, label, Decimal(str(round(recommended_price, 2))), explanation

    except Exception as exc:
        probability, label, price, explanation = baseline_predict(product)
        explanation["fallback_reason"] = str(exc)
        return probability, label, price, explanation


def predict_product(product):
    return ml_predict(product)
