from django.db import migrations, models, connection

def agregar_credenciales(apps, schema_editor):
    table = 'salon_empleado'
    with connection.cursor() as cursor:
        existing = [c.name for c in connection.introspection.get_table_description(cursor, table)]
    
    model = apps.get_model('salon', 'Empleado')
    campos = ['bold_api_key', 'bold_secret_key', 'telegram_token', 'telegram_chat_id']
    
    for campo in campos:
        if campo not in existing:
            schema_editor.add_field(model, model._meta.get_field(campo))

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
