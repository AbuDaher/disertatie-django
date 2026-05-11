from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from analytics.models import AnalysisRun
from .forms import DatasetUploadForm
from .models import DatasetUpload
from products.models import Product
from predictions.models import PredictionRun
from predictions.services import predict_product

try:
    from predictions.services import get_model_metadata, ml_artifacts_exist
except Exception:
    def get_model_metadata():
        return {"selected_classifier": "ML classifier", "selected_regressor": "ML regressor"}

    def ml_artifacts_exist():
        return True


REQUIRED_FIELDS = ["name", "category", "current_price"]

COLUMN_ALIASES = {
    "name": ["name", "nume", "nume produs", "produs", "product", "product name"],
    "category": ["category", "categorie", "categoria", "product_category"],
    "brand": ["brand", "marca"],
    "current_price": ["current_price", "current price", "pret curent", "preț curent", "price", "pret", "preț"],
    "cost": ["cost", "cost achizitie", "cost achiziție", "supplier_cost", "cost furnizor"],
    "discount_percent": ["discount_percent", "discount percent", "discount", "reducere", "discount (%)"],
    "rating": ["rating", "rating produs", "evaluare", "product_rating"],
    "review_count": ["review_count", "review count", "reviews", "numar recenzii", "număr recenzii", "recenzii"],
    "views": ["views", "vizualizari", "vizualizări"],
    "add_to_cart": ["add_to_cart", "add to cart", "adaugari in cos", "adăugări în coș", "cos", "coș"],
    "sales_volume": ["sales_volume", "sales volume", "volum vanzari", "volum vânzări", "vanzari", "vânzări", "estimated_orders", "comenzi estimate"],
    "stock_level": ["stock_level", "stock level", "stoc", "nivel stoc"],
    "conversion_rate": ["conversion_rate", "conversion rate", "rata conversie", "rată conversie", "conversie"],
    "margin_percent": ["margin_percent", "margin percent", "marja", "marjă", "marja comerciala", "marjă comercială"],
    "season": ["season", "sezon", "sezonalitate"],
}

NUMERIC_DEFAULTS = {
    "discount_percent": 0,
    "rating": 0,
    "review_count": 0,
    "views": 0,
    "add_to_cart": 0,
    "sales_volume": 0,
    "stock_level": 0,
    "conversion_rate": 0,
    "margin_percent": 0,
}

INTEGER_FIELDS = {"review_count", "views", "add_to_cart", "sales_volume", "stock_level"}


def _normalize_column_name(value: str) -> str:
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _build_column_map(df: pd.DataFrame) -> dict[str, str]:
    normalized = {_normalize_column_name(column): column for column in df.columns}
    result: dict[str, str] = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _normalize_column_name(alias)
            if key in normalized:
                result[target] = normalized[key]
                break
    return result


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if str(value).strip() == "":
        return True
    return False


def _clean_text(value: Any, default: str = "") -> str:
    if _is_empty(value):
        return default
    return str(value).strip()


def _clean_float(value: Any, default: float = 0.0) -> float:
    if _is_empty(value):
        return default
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(_clean_float(value, default)))
    except Exception:
        return default


def _clean_decimal(value: Any, default: str = "0") -> Decimal:
    if _is_empty(value):
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _row_value(row: pd.Series, column_map: dict[str, str], field: str, default: Any = None) -> Any:
    source_column = column_map.get(field)
    if not source_column:
        return default
    return row.get(source_column, default)


def _product_payload_from_row(row: pd.Series, column_map: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": _clean_text(_row_value(row, column_map, "name"), "Produs fără nume"),
        "category": _clean_text(_row_value(row, column_map, "category"), "Necategorizat"),
        "brand": _clean_text(_row_value(row, column_map, "brand"), ""),
        "current_price": _clean_decimal(_row_value(row, column_map, "current_price"), "0"),
        "cost": _clean_decimal(_row_value(row, column_map, "cost"), "0"),
        "season": _clean_text(_row_value(row, column_map, "season"), "tot anul"),
    }

    for field, default in NUMERIC_DEFAULTS.items():
        value = _row_value(row, column_map, field, default)
        if field in INTEGER_FIELDS:
            payload[field] = max(0, _clean_int(value, int(default)))
        else:
            payload[field] = _clean_float(value, float(default))

    return payload


def _validate_columns(column_map: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if field not in column_map]


def _generate_prediction_for_product(product: Product, analysis_run: AnalysisRun) -> PredictionRun:
    probability, label, price, explanation = predict_product(product)
    metadata = get_model_metadata()
    return PredictionRun.objects.create(
        product=product,
        analysis_run=analysis_run,
        success_probability=probability,
        success_label=label,
        recommended_price=price,
        model_name_classifier=metadata.get("selected_classifier", "ML classifier") if ml_artifacts_exist() else "baseline_classifier",
        model_name_regressor=metadata.get("selected_regressor", "ML regressor") if ml_artifacts_exist() else "baseline_regressor",
        explanation=explanation,
    )


def import_csv_and_generate_predictions(upload: DatasetUpload) -> dict[str, Any]:
    """Importă produsele din CSV și generează predicții într-o verificare distinctă."""
    df = pd.read_csv(upload.file.path)
    df = df.dropna(how="all")
    column_map = _build_column_map(df)
    missing = _validate_columns(column_map)
    if missing:
        readable = ", ".join(missing)
        raise ValueError(f"Lipsesc coloane obligatorii pentru import: {readable}.")

    title = f"Upload CSV - {upload.original_name}"[:255]
    analysis_run = AnalysisRun.objects.create(
        title=title,
        source_type=AnalysisRun.SOURCE_CSV_UPLOAD,
        source_file_name=upload.original_name,
        status=AnalysisRun.STATUS_CREATED,
        notes=upload.notes or "Verificare creată automat din încărcare CSV.",
    )

    created_products = 0
    created_predictions = 0
    skipped_rows = 0
    errors: list[str] = []

    with transaction.atomic():
        for index, row in df.iterrows():
            try:
                payload = _product_payload_from_row(row, column_map)
                if not payload["name"] or payload["current_price"] <= 0:
                    skipped_rows += 1
                    continue
                product = Product.objects.create(**payload)
                created_products += 1
                _generate_prediction_for_product(product, analysis_run)
                created_predictions += 1
            except Exception as exc:
                skipped_rows += 1
                errors.append(f"Rândul {index + 2}: {exc}")

    analysis_run.products_count = created_products
    analysis_run.predictions_count = created_predictions
    analysis_run.status = AnalysisRun.STATUS_COMPLETED if created_predictions else AnalysisRun.STATUS_ERROR
    analysis_run.notes = (
        f"Import finalizat. Produse create: {created_products}. "
        f"Predicții generate: {created_predictions}. Rânduri ignorate: {skipped_rows}."
    )
    if errors:
        analysis_run.notes += "\nErori parțiale:\n" + "\n".join(errors[:10])
    analysis_run.save()

    return {
        "analysis_run": analysis_run,
        "rows": len(df),
        "created_products": created_products,
        "created_predictions": created_predictions,
        "skipped_rows": skipped_rows,
        "errors": errors[:10],
    }


def dataset_upload(request):
    if request.method == "POST":
        form = DatasetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.original_name = request.FILES["file"].name
            obj.status = "uploaded"
            obj.save()

            try:
                result = import_csv_and_generate_predictions(obj)
                obj.rows_count = result["rows"]
                obj.status = "imported"
                obj.notes = (
                    f"Import finalizat. Produse create: {result['created_products']}. "
                    f"Predicții generate: {result['created_predictions']}. "
                    f"Rânduri ignorate: {result['skipped_rows']}.")
                if result["errors"]:
                    obj.notes += "\nErori parțiale:\n" + "\n".join(result["errors"])
                obj.save()
                messages.success(
                    request,
                    f"CSV importat ca verificare separată: {result['created_products']} produse și "
                    f"{result['created_predictions']} predicții generate.",
                )
                return redirect("analysis_run_detail", pk=result["analysis_run"].pk)
            except Exception as exc:
                obj.status = "error"
                obj.notes = f"Eroare import CSV: {exc}"
                obj.save()
                messages.error(request, f"CSV-ul a fost încărcat, dar importul a eșuat: {exc}")

            return redirect("dataset_upload")
    else:
        form = DatasetUploadForm()

    uploads = DatasetUpload.objects.all()
    return render(request, "datasets/upload.html", {"form": form, "uploads": uploads})
