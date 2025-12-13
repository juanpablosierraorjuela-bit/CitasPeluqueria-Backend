from django import forms
from .models import Tenant, Absence, Professional

class ConfigNegocioForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'name', 'subdomain', 'ciudad', 'direccion', 'telefono',
            'instagram', 'facebook', 'tiktok',
            'nequi_number', 'bold_api_key'
        ]
        labels = {
            'name': 'Nombre del Negocio',
            'subdomain': 'Identificador URL (sin espacios)',
            'nequi_number': 'Número Nequi',
            'bold_api_key': 'Bold API Key (Opcional)'
        }

class AbsenceForm(forms.ModelForm):
    class Meta:
        model = Absence
        fields = ['fecha_inicio', 'fecha_fin', 'motivo']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Almuerzo, Cita médica'}),
        }