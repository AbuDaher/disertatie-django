from django import forms
from .models import DatasetUpload


class DatasetUploadForm(forms.ModelForm):
    class Meta:
        model = DatasetUpload
        fields = ["file", "notes"]
        labels = {
            "file": "Fișier CSV",
            "notes": "Observații",
        }
        help_texts = {
            "file": "Încarcă un fișier CSV cu produse. Aplicația va crea produsele și va genera automat predicții ML.",
            "notes": "Opțional: descriere scurtă a setului de date.",
        }
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Exemplu: set de test pentru Dashboard BI"}),
        }
