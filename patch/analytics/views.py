from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import AnalysisRun
from predictions.models import PredictionRun
from predictions.services import get_feature_importance, get_model_metrics, get_model_metadata

CHART_COLORS = [
    "#4f46e5", "#06b6d4", "#16a34a", "#f59e0b",
    "#ef4444", "#8b5cf6", "#14b8a6", "#64748b",
    "#f97316", "#ec4899",
]


def _pct(value: float, total: float) -> float:
    if not total:
        return 0.0
    return round((float(value) / float(total)) * 100, 2)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except Exception:
        return default


def _optional_investment_model():
    try:
        from investment.models import InvestmentAnalysis
        return InvestmentAnalysis
    except Exception:
        return None


def _build_label_distribution(runs):
    rows = list(runs.values("success_label").annotate(total=Count("id")).order_by("-total"))
    total = sum(r["total"] for r in rows) or 1
    for idx, row in enumerate(rows):
        row["percent"] = _pct(row["total"], total)
        row["color"] = CHART_COLORS[idx % len(CHART_COLORS)]
    return rows


def _pie_gradient(rows):
    if not rows:
        return "#e2e8f0 0 100%"
    cursor = 0.0
    parts = []
    for row in rows:
        start = cursor
        cursor += float(row.get("percent") or 0)
        parts.append(f"{row.get('color', '#4f46e5')} {start:.2f}% {cursor:.2f}%")
    if cursor < 100:
        parts.append(f"#e2e8f0 {cursor:.2f}% 100%")
    return ", ".join(parts)


def _build_category_distribution(runs):
    rows = list(
        runs.values("product__category")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    total = sum(r["total"] for r in rows) or 1
    for idx, row in enumerate(rows):
        row["category"] = row.get("product__category") or "Necunoscut"
        row["percent"] = _pct(row["total"], total)
        row["color"] = CHART_COLORS[idx % len(CHART_COLORS)]
    return rows


def _build_timeline(runs):
    buckets: dict[str, int] = defaultdict(int)
    for run in runs.order_by("created_at"):
        key = timezone.localtime(run.created_at).strftime("%d.%m") if run.created_at else "N/A"
        buckets[key] += 1
    rows = [{"date": k, "total": v} for k, v in buckets.items()]
    max_total = max((r["total"] for r in rows), default=1)
    for row in rows:
        row["percent"] = _pct(row["total"], max_total)
    return rows[-12:]


def _build_price_comparison(runs):
    rows = []
    for run in runs.order_by("-created_at")[:15]:
        current = _as_float(run.product.current_price if hasattr(run, "product") else 0)
        recommended = _as_float(run.recommended_price)
        if current <= 0:
            continue
        diff = recommended - current
        diff_pct = (diff / current) * 100
        rows.append({
            "product": run.product.name[:40],
            "current_price": round(current, 2),
            "recommended_price": round(recommended, 2),
            "difference": round(diff, 2),
            "diff_pct": round(diff_pct, 1),
        })
    return rows


def _investment_decision_distribution(analyses):
    rows = list(
        analyses.values("decision_label").annotate(total=Count("id")).order_by("-total")
    )
    labels = {
        "recommended": "Merită investiția",
        "medium_risk": "Merită cu risc mediu",
        "not_recommended": "Nu este recomandată",
    }
    total = sum(r["total"] for r in rows) or 1
    for idx, row in enumerate(rows):
        row["label"] = labels.get(row.get("decision_label"), row.get("decision_label"))
        row["percent"] = _pct(row["total"], total)
        row["color"] = CHART_COLORS[idx % len(CHART_COLORS)]
    return rows


def dashboard(request):
    analysis_runs = AnalysisRun.objects.all()
    total_runs = analysis_runs.count()
    completed_runs = analysis_runs.filter(status=AnalysisRun.STATUS_COMPLETED).count()
    total_predictions = sum(item.predictions_count for item in analysis_runs)
    total_products = sum(item.products_count for item in analysis_runs)

    # Statistici globale rapide
    all_runs = PredictionRun.objects.select_related("product").all()
    avg_prob = all_runs.aggregate(v=Avg("success_probability"))["v"] or 0
    high_potential = all_runs.filter(success_label__icontains="ridicat").count()

    context = {
        "analysis_runs": analysis_runs,
        "latest_run": analysis_runs.first(),
        "summary": {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_predictions": total_predictions,
            "total_products": total_products,
            "avg_success_probability": round(float(avg_prob), 3),
            "high_potential_count": high_potential,
        },
    }
    return render(request, "analytics/dashboard.html", context)


def analysis_run_detail(request, pk):
    analysis_run = get_object_or_404(AnalysisRun, pk=pk)
    runs = analysis_run.prediction_runs.select_related("product").all()
    total_predictions = runs.count()
    high_potential = runs.filter(success_label__icontains="ridicat").count()
    medium_potential = runs.filter(success_label__icontains="mediu").count()
    low_potential = runs.filter(success_label__icontains="redus").count()

    InvestmentAnalysis = _optional_investment_model()
    analyses = InvestmentAnalysis.objects.none() if InvestmentAnalysis else []
    if InvestmentAnalysis:
        analyses = InvestmentAnalysis.objects.select_related(
            "product", "prediction_run"
        ).filter(analysis_run=analysis_run)

    agg = runs.aggregate(
        avg_prob=Avg("success_probability"),
        avg_price=Avg("recommended_price"),
        max_prob=Max("success_probability"),
        min_prob=Min("success_probability"),
    )

    inv_agg = {}
    if InvestmentAnalysis and analyses.exists():
        inv_agg = analyses.aggregate(
            avg_roi=Avg("roi_percent"),
            total_profit=Sum("total_profit"),
            avg_margin=Avg("profit_margin_percent"),
        )

    summary = {
        "total_predictions": total_predictions,
        "high_potential": high_potential,
        "medium_potential": medium_potential,
        "low_potential": low_potential,
        "high_potential_percent": _pct(high_potential, total_predictions),
        "avg_success_probability": round(float(agg["avg_prob"] or 0), 3),
        "avg_recommended_price": round(float(agg["avg_price"] or 0), 2),
        "max_success_probability": round(float(agg["max_prob"] or 0), 3),
        "min_success_probability": round(float(agg["min_prob"] or 0), 3),
        "total_investment_analyses": analyses.count() if InvestmentAnalysis else 0,
        "avg_roi": round(float(inv_agg.get("avg_roi") or 0), 2),
        "total_profit": inv_agg.get("total_profit") or Decimal("0"),
        "avg_margin": round(float(inv_agg.get("avg_margin") or 0), 2),
    }

    by_label = _build_label_distribution(runs)
    by_category = _build_category_distribution(runs)
    by_decision = _investment_decision_distribution(analyses) if InvestmentAnalysis else []

    context = {
        "analysis_run": analysis_run,
        "summary": summary,
        "by_label": by_label,
        "label_pie_gradient": _pie_gradient(by_label),
        "by_category": by_category,
        "category_pie_gradient": _pie_gradient(by_category),
        "by_decision": by_decision,
        "decision_pie_gradient": _pie_gradient(by_decision),
        "timeline": _build_timeline(runs),
        "top_success": runs.order_by("-success_probability")[:10],
        "runs": runs,
        "investment_rows": (
            list(analyses.order_by("-total_profit")[:10]) if InvestmentAnalysis else []
        ),
        "price_comparison": _build_price_comparison(runs),
    }
    return render(request, "analytics/analysis_run_detail.html", context)


def model_performance(request):
    metrics = get_model_metrics()
    feature_importance = get_feature_importance()
    metadata = get_model_metadata()

    classifier_rows = metrics.get("classifier_metrics", []) if isinstance(metrics, dict) else []
    regressor_rows = metrics.get("regressor_metrics", []) if isinstance(metrics, dict) else []
    selected_classifier = metrics.get("selected_classifier") if isinstance(metrics, dict) else None
    selected_regressor = metrics.get("selected_regressor") if isinstance(metrics, dict) else None

    classifier_importance = feature_importance.get("classifier", []) if isinstance(feature_importance, dict) else []
    regressor_importance = feature_importance.get("regressor", []) if isinstance(feature_importance, dict) else []
    xai_method = feature_importance.get("method", "feature_importances_") if isinstance(feature_importance, dict) else ""

    max_clf_imp = max([float(r.get("importance") or 0) for r in classifier_importance], default=1)
    max_reg_imp = max([float(r.get("importance") or 0) for r in regressor_importance], default=1)

    for row in classifier_importance:
        row["percent"] = _pct(float(row.get("importance") or 0), max_clf_imp)
    for row in regressor_importance:
        row["percent"] = _pct(float(row.get("importance") or 0), max_reg_imp)

    # Cel mai bun model din fiecare categorie
    def best_classifier_highlight(rows):
        if not rows:
            return None
        return max(rows, key=lambda r: float(r.get("f1") or 0))

    def best_regressor_highlight(rows):
        if not rows:
            return None
        return max(rows, key=lambda r: float(r.get("r2") or 0))

    dataset_info = metrics.get("dataset", {}) if isinstance(metrics, dict) else {}
    cv_folds = metrics.get("cv_folds", 5) if isinstance(metrics, dict) else 5

    return render(request, "analytics/model_performance.html", {
        "metrics": metrics,
        "classifier_rows": classifier_rows,
        "regressor_rows": regressor_rows,
        "selected_classifier": selected_classifier,
        "selected_regressor": selected_regressor,
        "classifier_importance": classifier_importance[:13],
        "regressor_importance": regressor_importance[:13],
        "xai_method": xai_method,
        "best_classifier_row": best_classifier_highlight(classifier_rows),
        "best_regressor_row": best_regressor_highlight(regressor_rows),
        "dataset_info": dataset_info,
        "cv_folds": cv_folds,
        "metadata": metadata,
        "engineered_features": metadata.get("engineered_features", []),
    })
