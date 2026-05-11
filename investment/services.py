from decimal import Decimal, ROUND_HALF_UP
from .models import InvestmentAnalysis


TWO_PLACES = Decimal('0.01')


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_investment(analysis: InvestmentAnalysis) -> InvestmentAnalysis:
    selling_price = money(analysis.recommended_selling_price)
    acquisition = money(analysis.acquisition_cost)
    shipping = money(analysis.shipping_cost)
    marketing = money(analysis.marketing_cost)
    other = money(analysis.other_costs)
    units = max(int(analysis.estimated_units or 1), 1)

    commission_rate = Decimal(str(analysis.platform_commission_percent or 0)) / Decimal('100')
    commission_value = money(selling_price * commission_rate)
    total_unit_cost = money(acquisition + shipping + marketing + other + commission_value)
    profit_per_unit = money(selling_price - total_unit_cost)
    total_revenue = money(selling_price * units)
    total_profit = money(profit_per_unit * units)

    if selling_price > 0:
        profit_margin_percent = float((profit_per_unit / selling_price) * Decimal('100'))
    else:
        profit_margin_percent = 0.0

    if total_unit_cost > 0:
        roi_percent = float((profit_per_unit / total_unit_cost) * Decimal('100'))
    else:
        roi_percent = 0.0

    probability = 0.0
    if analysis.prediction_run:
        probability = float(analysis.prediction_run.success_probability or 0)

    if profit_per_unit <= 0:
        decision_label = InvestmentAnalysis.DECISION_NOT_RECOMMENDED
        reason = 'Profitul estimat per produs este negativ sau zero. Investiția nu este recomandată în forma actuală.'
    elif profit_margin_percent >= 20 and probability >= 0.70:
        decision_label = InvestmentAnalysis.DECISION_RECOMMENDED
        reason = 'Produsul are probabilitate ridicată de succes și marjă estimată bună. Investiția este recomandată.'
    elif profit_margin_percent >= 10 and probability >= 0.55:
        decision_label = InvestmentAnalysis.DECISION_MEDIUM_RISK
        reason = 'Produsul are potențial comercial, dar marja sau probabilitatea de succes indică un risc mediu.'
    else:
        decision_label = InvestmentAnalysis.DECISION_NOT_RECOMMENDED
        reason = 'Indicatorii calculați nu justifică investiția: probabilitatea de succes sau marja estimată sunt prea reduse.'

    analysis.commission_value = commission_value
    analysis.total_unit_cost = total_unit_cost
    analysis.profit_per_unit = profit_per_unit
    analysis.total_revenue = total_revenue
    analysis.total_profit = total_profit
    analysis.profit_margin_percent = round(profit_margin_percent, 2)
    analysis.roi_percent = round(roi_percent, 2)
    analysis.decision_label = decision_label
    analysis.decision_reason = reason
    return analysis
