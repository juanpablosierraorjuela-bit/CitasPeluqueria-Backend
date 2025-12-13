#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Instalar librerías
pip install -r requirements.txt

# 2. Recolectar estáticos
python manage.py collectstatic --no-input

# 3. Aplicar migraciones
python manage.py migrate
