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

# Formulario para que el dueño agregue manualmente (opcional)
class NuevoEmpleadoForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    apellido = forms.CharField(max_length=100)
    email = forms.EmailField(label="Correo (Será su usuario)")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña Inicial")

# Formulario para el auto-registro público
class RegistroPublicoEmpleadoForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    apellido = forms.CharField(max_length=100)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden")
        return cleaned_data
