from django.db import migrations, models, connection

def agregar_si_no_existe(apps, schema_editor):
    table = 'salon_empleado'
    with connection.cursor() as cursor:
        existing = [c.name for c in connection.introspection.get_table_description(cursor, table)]
    
    model = apps.get_model('salon', 'Empleado')
    
    if 'es_independiente' not in existing:
        schema_editor.add_field(model, model._meta.get_field('es_independiente'))

    if 'es_domiciliario' not in existing:
        schema_editor.add_field(model, model._meta.get_field('es_domiciliario'))

class Migration(migrations.Migration):
    dependencies = [
        ('salon', '0018_cita_direccion_domicilio_cita_es_domicilio_and_more'),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(agregar_si_no_existe),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='empleado',
                    name='es_independiente',
                    field=models.BooleanField(default=False, help_text='Marcar si el empleado alquila silla/es independiente'),
                ),
                migrations.AlterField(
                    model_name='empleado',
                    name='es_domiciliario',
                    field=models.BooleanField(default=False, help_text='Marcar si realiza servicios a domicilio'),
                ),
            ]
        )
    ]
