from django import forms
from .models import SearchQuery


class OpportunitySearchForm(forms.ModelForm):
    top_n = forms.ChoiceField(
        choices=[(3, 'Top 3'), (5, 'Top 5'), (10, 'Top 10')],
        initial=5,
        label='Număr rezultate',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = SearchQuery
        fields = ['keyword', 'category', 'max_price', 'min_rating', 'min_reviews', 'top_n', 'data_source']
        labels = {
            'keyword': 'Cuvânt cheie',
            'category': 'Categorie',
            'max_price': 'Buget maxim / preț maxim',
            'min_rating': 'Rating minim',
            'min_reviews': 'Număr minim recenzii',
            'data_source': 'Sursa datelor',
        }
        help_texts = {
            'keyword': 'Exemplu: smartwatch, căști bluetooth, proiector portabil',
            'data_source': 'Alege eBay API doar dacă ai configurat cheile în fișierul .env. Altfel folosește CSV fallback.',
        }
        widgets = {
            'keyword': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: smartwatch'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opțional: Electronice'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 500', 'step': '0.01', 'min': '0'}),
            'min_rating': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 4.5', 'step': '0.1', 'min': '0', 'max': '5'}),
            'min_reviews': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exemplu: 50', 'min': '0'}),
            'data_source': forms.Select(attrs={'class': 'form-control'}),
        }
