from django import forms
from .models import Tenant, Absence

class ConfigNegocioForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['name', 'subdomain', 'ciudad', 'direccion', 'telefono', 'instagram', 'facebook']

class AbsenceForm(forms.ModelForm):
    class Meta:
        model = Absence
        fields = ['fecha_inicio', 'fecha_fin', 'motivo']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
