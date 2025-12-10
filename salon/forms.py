# UBICACIÓN: salon/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Peluqueria, Servicio, Empleado, HorarioEmpleado

class ConfigNegocioForm(forms.ModelForm):
    class Meta:
        model = Peluqueria
        fields = [
            'nombre_visible', 'ciudad', 'direccion', 'telefono', 
            'codigo_pais_wa', 'telegram_token', 'telegram_chat_id',
            'bold_api_key', 'bold_integrity_key', 'porcentaje_abono'
        ]
        widgets = {
            'bold_api_key': forms.PasswordInput(render_value=True),
            'bold_integrity_key': forms.PasswordInput(render_value=True),
            'telegram_token': forms.PasswordInput(render_value=True),
        }

class ServicioForm(forms.ModelForm):
    duracion_minutos = forms.IntegerField(min_value=5, max_value=300, initial=30, label="Duración (min)")

    class Meta:
        model = Servicio
        fields = ['nombre', 'precio']

class NuevoEmpleadoForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    apellido = forms.CharField(max_length=100)
    email = forms.EmailField(label="Correo (Será su usuario)")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña Inicial")

class HorarioForm(forms.ModelForm):
    class Meta:
        model = HorarioEmpleado
        fields = ['hora_inicio', 'hora_fin', 'almuerzo_inicio', 'almuerzo_fin']
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            'almuerzo_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'almuerzo_fin': forms.TimeInput(attrs={'type': 'time'}),
        }
