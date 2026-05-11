from django import forms
from .models import InvestmentAnalysis


class InvestmentAnalysisForm(forms.ModelForm):
    class Meta:
        model = InvestmentAnalysis
        fields = [
            'acquisition_cost',
            'shipping_cost',
            'marketing_cost',
            'other_costs',
            'platform_commission_percent',
            'recommended_selling_price',
            'estimated_units',
        ]
        labels = {
            'acquisition_cost': 'Cost achiziție / furnizor per produs',
            'shipping_cost': 'Cost transport / logistică per produs',
            'marketing_cost': 'Cost marketing per produs',
            'other_costs': 'Alte costuri per produs',
            'platform_commission_percent': 'Comision platformă (%)',
            'recommended_selling_price': 'Preț recomandat de vânzare',
            'estimated_units': 'Unități estimate vândute',
        }
        widgets = {
            'acquisition_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Exemplu: 35.00'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Exemplu: 5.00'}),
            'marketing_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Exemplu: 3.00'}),
            'other_costs': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Exemplu: 0.00'}),
            'platform_commission_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'placeholder': 'Exemplu: 8'}),
            'recommended_selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Exemplu: 71.37'}),
            'estimated_units': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Exemplu: 100'}),
        }
