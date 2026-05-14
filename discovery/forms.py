from django import forms
from .models import SearchQuery


class OpportunitySearchForm(forms.ModelForm):
    top_n = forms.ChoiceField(
        choices=[(1, 'Top 1'), (3, 'Top 3'), (5, 'Top 5'), (10, 'Top 10')],
        initial=5,
        label='Câte oportunități?',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = SearchQuery
        fields = [
            'top_n', 'keyword', 'category',
            'max_price', 'min_rating', 'min_reviews', 'data_source',
        ]
        labels = {
            'keyword':     'Cuvânt cheie / produs',
            'category':    'Categorie',
            'max_price':   'Buget maxim per produs (USD)',
            'min_rating':  'Rating minim acceptat',
            'min_reviews': 'Număr minim de recenzii',
            'data_source': 'Sursa datelor',
        }
        help_texts = {
            'keyword':     'Opțional. Lasă gol → algoritmul descoperă automat.',
            'category':    'Opțional. Exemplu: Electronics, Beauty, Sports, Home.',
            'max_price':   'Opțional. Filtrează produsele mai scumpe decât bugetul.',
            'min_rating':  'Recomandat: 4.0 — calitate confirmată de piață.',
            'min_reviews': 'Recomandat: 500 — cerere dovedită, nu produse noi fără istoric.',
            'data_source': (
                'Amazon API — date live (necesită RAPIDAPI_KEY în .env). '
                'CSV fallback — date demo locale.'
            ),
        }
        widgets = {
            'keyword': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exemplu: wireless earbuds  (sau lasă gol)',
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exemplu: Electronics',
            }),
            'max_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exemplu: 100',
                'step': '0.01', 'min': '0',
            }),
            'min_rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exemplu: 4.0',
                'step': '0.1', 'min': '0', 'max': '5',
            }),
            'min_reviews': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exemplu: 500',
                'min': '0',
            }),
            'data_source': forms.Select(
                attrs={'class': 'form-control'},
                choices=[
                    ('api', 'Amazon API (date reale)'),
                    ('aliexpress', 'AliExpress API (date reale)'),
                    ('ebay', 'eBay Browse API (date reale)'),
                    ('csv', 'CSV fallback (demo)'),
                ]
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # keyword și category sunt opționale — nu sunt required
        self.fields['keyword'].required = False
        self.fields['category'].required = False
        self.fields['max_price'].required = False
        self.fields['min_rating'].required = False
        self.fields['min_reviews'].required = False
