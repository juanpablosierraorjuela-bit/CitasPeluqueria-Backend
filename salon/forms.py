# UBICACIÓN: salon/forms.py
from django import forms
from .models import Peluqueria, Servicio, Ausencia

class ConfigNegocioForm(forms.ModelForm):
    class Meta:
        model = Peluqueria
        fields = [
            'nombre_visible', 'ciudad', 'direccion', 'telefono', 
            'codigo_pais_wa', 'telegram_token', 'telegram_chat_id',
            'bold_api_key', 'bold_integrity_key', 'bold_secret_key',
            'nequi_celular', 'nequi_qr_imagen', 'porcentaje_abono'
        ]
        widgets = {
            'bold_api_key': forms.PasswordInput(render_value=True),
            'bold_integrity_key': forms.PasswordInput(render_value=True),
            'bold_secret_key': forms.PasswordInput(render_value=True),
            'telegram_token': forms.PasswordInput(render_value=True),
        }

class ServicioForm(forms.ModelForm):
    duracion_minutos = forms.IntegerField(min_value=5, max_value=300, initial=30, label="Duración (min)")
    class Meta:
        model = Servicio
        fields = ['nombre', 'precio']

class AusenciaForm(forms.ModelForm):
    fecha_inicio = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label="Inicio de ausencia"
    )
    fecha_fin = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label="Fin de ausencia"
    )
    class Meta:
        model = Ausencia
        fields = ['fecha_inicio', 'fecha_fin', 'motivo']

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
