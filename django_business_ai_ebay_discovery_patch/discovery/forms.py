from django import forms
from .models import SearchQuery


class OpportunitySearchForm(forms.ModelForm):
    top_n = forms.ChoiceField(
        choices=[(3, 'Top 3'), (5, 'Top 5'), (10, 'Top 10')],
        initial=5,
        label='Număr rezultate'
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
            'keyword': 'Exemplu: smartwatch, bluetooth headphones, portable projector',
            'data_source': 'Alege eBay API dacă ai configurat cheile în .env. Altfel folosește CSV fallback.',
        }
