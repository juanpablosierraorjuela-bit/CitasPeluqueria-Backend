from django.db import migrations, models, connection

def agregar_credenciales(apps, schema_editor):
    table = 'salon_empleado'
    with connection.cursor() as cursor:
        existing = [c.name for c in connection.introspection.get_table_description(cursor, table)]
    
    model = apps.get_model('salon', 'Empleado')
    
    # Definimos los campos manualmente porque no existen en el modelo histórico aún
    campos_defs = {
        'bold_api_key': models.CharField(blank=True, max_length=255, null=True, verbose_name='Mi API Key Bold'),
        'bold_secret_key': models.CharField(blank=True, max_length=255, null=True, verbose_name='Mi Secret Key Bold'),
        'telegram_token': models.CharField(blank=True, max_length=200, null=True, verbose_name='Mi Token Bot'),
        'telegram_chat_id': models.CharField(blank=True, max_length=100, null=True, verbose_name='Mi Chat ID'),
    }
    
    for nombre, field in campos_defs.items():
        if nombre not in existing:
            # Configuramos el campo manualmente para poder añadirlo
            field.name = nombre
            field.column = nombre
            field.concrete = True
            schema_editor.add_field(model, field)

class Migration(migrations.Migration):
    dependencies = [
        ('salon', '0019_auto_fix_fields'),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(agregar_credenciales),
            ],
            state_operations=[
                migrations.AddField(model_name='empleado', name='bold_api_key', field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Mi API Key Bold')),
                migrations.AddField(model_name='empleado', name='bold_secret_key', field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Mi Secret Key Bold')),
                migrations.AddField(model_name='empleado', name='telegram_token', field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Mi Token Bot')),
                migrations.AddField(model_name='empleado', name='telegram_chat_id', field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Mi Chat ID')),
            ]
        )
    ]
