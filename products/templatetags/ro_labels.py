from django import template

register = template.Library()

FIELD_LABELS_RO = {
    'name': 'Nume produs',
    'category': 'Categorie',
    'brand': 'Brand',
    'current_price': 'Preț curent',
    'cost': 'Cost achiziție',
    'discount_percent': 'Discount (%)',
    'rating': 'Rating produs',
    'review_count': 'Număr recenzii',
    'reviews': 'Număr recenzii',
    'views': 'Vizualizări',
    'add_to_cart': 'Adăugări în coș',
    'sales_volume': 'Volum vânzări',
    'stock_level': 'Nivel stoc',
    'conversion_rate': 'Rată de conversie (%)',
    'margin_percent': 'Marjă comercială (%)',
    'season': 'Sezon',
    'created_at': 'Data înregistrării',
    'updated_at': 'Data actualizării',

    'success_probability': 'Probabilitate de succes',
    'success_label': 'Încadrare succes comercial',
    'recommended_price': 'Preț recomandat',
    'model_name_classifier': 'Model de clasificare',
    'model_name_regressor': 'Model de regresie',
    'model_utilizat': 'Model utilizat',
    'probabilitate_succes_ml': 'Probabilitate succes ML',
    'pret_recomandat_ml': 'Preț recomandat ML',
    'pret_platforma': 'Preț platformă',
    'moneda_platforma': 'Monedă platformă',

    'sursa_oportunitate': 'Sursă oportunitate',
    'scor_comercial_discovery': 'Scor comercial descoperire',
    'commercial_score': 'Scor comercial',
    'trend_score': 'Scor trend',
    'estimated_orders': 'Comenzi estimate',
    'comenzi_estimate': 'Comenzi estimate',
    'seller_feedback_score': 'Scor feedback vânzător',
    'seller_feedback_percent': 'Procent feedback vânzător',
    'rating_produs_corectat': 'Rating produs corectat',
    'numar_recenzii_corectat': 'Număr recenzii corectat',

    'acquisition_cost': 'Cost achiziție / furnizor',
    'shipping_cost': 'Cost transport / logistică',
    'marketing_cost': 'Cost marketing',
    'other_costs': 'Alte costuri',
    'platform_commission_percent': 'Comision platformă (%)',
    'recommended_selling_price': 'Preț recomandat de vânzare',
    'estimated_units': 'Unități estimate vândute',
    'commission_value': 'Valoare comision / unitate',
    'total_unit_cost': 'Cost total / unitate',
    'profit_per_unit': 'Profit estimat / unitate',
    'total_revenue': 'Venit total estimat',
    'total_profit': 'Profit total estimat',
    'profit_margin_percent': 'Marjă profit (%)',
    'roi_percent': 'Randament investiție / ROI (%)',
    'decision_label': 'Decizie investițională',
    'decision_reason': 'Motiv decizie',
}

VALUE_LABELS_RO = {
    'csv_fallback': 'CSV fallback',
    'csv': 'CSV fallback',
    'api': 'eBay API',
    'ebay_api': 'eBay API',
    'RandomForestClassifier + RandomForestRegressor': 'Random Forest clasificare + regresie',
    'baseline_classifier': 'Clasificator baseline',
    'baseline_regressor': 'Regresor baseline',
    'recommended': 'Merită investiția',
    'medium_risk': 'Merită cu risc mediu',
    'not_recommended': 'Nu este recomandată investiția',
}

@register.filter
def ro_label(value):
    if value is None:
        return ''
    key = str(value)
    return FIELD_LABELS_RO.get(key, key.replace('_', ' ').capitalize())

@register.filter
def ro_value(value):
    if value is None:
        return ''
    key = str(value)
    return VALUE_LABELS_RO.get(key, value)

@register.filter
def decision_badge_class(value):
    key = str(value or '').lower()
    if 'merită investiția' in key or key == 'recommended':
        return 'badge-success'
    if 'risc' in key or key == 'medium_risk':
        return 'badge-warning'
    if 'nu' in key or key == 'not_recommended':
        return 'badge-danger'
    return 'badge-info'

# Etichete suplimentare pentru patch-ul ML/XAI.
FIELD_LABELS_RO.update({
    'model_clasificare_selectat': 'Model de clasificare selectat',
    'model_regresie_selectat': 'Model de regresie selectat',
    'fallback_reason': 'Motiv fallback',
    'stock_risk': 'Risc stoc',
    'xai_tip_explicatie': 'Tip explicație XAI',
    'xai_rezumat': 'Rezumat XAI',
    'current_price': 'Preț curent',
})

VALUE_LABELS_RO.update({
    'baseline determinist': 'Baseline determinist',
    'explicație locală model-agnostică bazată pe importanța variabilelor': 'Explicație locală model-agnostică bazată pe importanța variabilelor',
})
