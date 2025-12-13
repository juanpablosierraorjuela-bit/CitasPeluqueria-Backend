import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("salon", "0020_fix_missing_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="empleado",
            name="es_independiente",
            field=models.BooleanField(
                default=False,
                help_text="Si está marcado, usa sus propias credenciales de pago y Telegram.",
            ),
        ),
        migrations.AlterField(
            model_name="empleado",
            name="valor_pago",
            field=models.IntegerField(default=50),
        ),
        migrations.AlterField(
            model_name="producto",
            name="costo_compra",
            field=models.IntegerField(
                default=0, help_text="Costo unitario de adquisición"
            ),
        ),
        migrations.AlterField(
            model_name="producto",
            name="es_insumo_interno",
            field=models.BooleanField(
                default=False, help_text="Marcar si es uso interno (no venta)"
            ),
        ),
        migrations.AlterField(
            model_name="producto",
            name="precio_venta",
            field=models.IntegerField(
                default=0, help_text="Precio de venta al público"
            ),
        ),
        migrations.AlterField(
            model_name="servicio",
            name="cantidad_descuento",
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="servicio",
            name="producto_asociado",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="salon.producto",
            ),
        ),
    ]
