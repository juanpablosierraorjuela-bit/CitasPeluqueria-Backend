# UBICACIÓN: salon/migrations/0009_ajustes_finales.py
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0008_peluqueria_codigo_pais_wa_and_more'),
    ]

    operations = [
        # 1. Agregar las claves de Bold que faltan
        migrations.AddField(
            model_name='peluqueria',
            name='bold_secret_key',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Bold Secret Key'),
        ),
        # 2. Agregar horarios (Aunque la base de datos crea tenerlos, esto asegura que el código lo sepa)
        migrations.AddField(
            model_name='peluqueria',
            name='hora_apertura',
            field=models.TimeField(default='06:00', help_text='Hora de apertura del local'),
        ),
        migrations.AddField(
            model_name='peluqueria',
            name='hora_cierre',
            field=models.TimeField(default='21:00', help_text='Hora de cierre del local'),
        ),
        # 3. Renombrar nicho a nichos (Corrección ortográfica)
        migrations.RenameField(
            model_name='solicitudsaas',
            old_name='nicho',
            new_name='nichos',
        ),
        # 4. Asegurar que Ausencia tenga 'motivo' en lugar de 'tipo'
        migrations.AddField(
            model_name='ausencia',
            name='motivo',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
