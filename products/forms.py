from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'brand', 'current_price', 'cost', 'discount_percent',
            'rating', 'review_count', 'views', 'add_to_cart', 'sales_volume',
            'stock_level', 'conversion_rate', 'margin_percent', 'season'
        ]
        labels = {
            'name': 'Nume produs',
            'category': 'Categorie',
            'brand': 'Brand',
            'current_price': 'Preț curent',
            'cost': 'Cost achiziție',
            'discount_percent': 'Discount (%)',
            'rating': 'Rating produs',
            'review_count': 'Număr recenzii',
            'views': 'Vizualizări',
            'add_to_cart': 'Adăugări în coș',
            'sales_volume': 'Volum vânzări',
            'stock_level': 'Nivel stoc',
            'conversion_rate': 'Rată de conversie (%)',
            'margin_percent': 'Marjă comercială (%)',
            'season': 'Sezon',
        }
        help_texts = {
            'name': 'Exemplu: Smartwatch FitPro S9',
            'category': 'Exemplu: Electronice, Wearables, Accesorii mobile',
            'brand': 'Exemplu: NovaTech',
            'current_price': 'Prețul actual de vânzare al produsului.',
            'cost': 'Costul estimat de achiziție sau producție.',
            'discount_percent': 'Reducerea aplicată, exprimată procentual.',
            'rating': 'Rating mediu al produsului, de exemplu 4.7.',
            'review_count': 'Numărul total de recenzii.',
            'views': 'Numărul de vizualizări ale produsului.',
            'add_to_cart': 'Numărul de adăugări în coș.',
            'sales_volume': 'Numărul de unități vândute sau estimarea comenzilor.',
            'stock_level': 'Numărul de unități disponibile în stoc.',
            'conversion_rate': 'Procentul vizitatorilor care finalizează cumpărarea.',
            'margin_percent': 'Marja comercială estimată.',
            'season': 'Exemplu: tot anul, vară, iarnă, sărbători.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Introdu numele produsului'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Introdu categoria'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Introdu brandul'}),
            'current_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 299.99', 'step': '0.01', 'min': '0'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 150.00', 'step': '0.01', 'min': '0'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 10', 'step': '0.01', 'min': '0'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 4.7', 'step': '0.1', 'min': '0', 'max': '5'}),
            'review_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 340', 'min': '0'}),
            'views': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 5200', 'min': '0'}),
            'add_to_cart': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 610', 'min': '0'}),
            'sales_volume': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 1450', 'min': '0'}),
            'stock_level': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 50', 'min': '0'}),
            'conversion_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 4.8', 'step': '0.01', 'min': '0'}),
            'margin_percent': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 25', 'step': '0.01'}),
            'season': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: tot anul'}),
        }
