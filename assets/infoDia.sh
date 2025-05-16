#!/bin/bash

# Verifica que se haya pasado una fecha como argumento
if [ $# -ne 1 ]; then
    echo "Uso: $0 YYYY-MM-DD"
    exit 1
fi

# Captura la fecha del argumento
FECHA=$1

# Verifica que la fecha sea válida
if ! date -d "$FECHA" >/dev/null 2>&1; then
    echo "Formato de fecha inválido. Use YYYY-MM-DD"
    exit 1
fi

# Genera los nombres de archivo basados en la fecha proporcionada
PRIMARIO="primario_${FECHA}.pdf"
SECUNDARIO="secundario_${FECHA}.pdf"
SALIDA_TEMPORAL="primario2x2.pdf"

# Obtiene el día de la semana
DIA_SEMANA=$(date -d "$FECHA" +%A)

# Formatea el nombre del archivo final
DIA=$(date -d "$FECHA" +%d)
MES=$(date -d "$FECHA" +%m)
SALIDA_FINAL="$HOME/Descargas/viandas/${DIA_SEMANA}${DIA}-${MES}.pdf"

# Ejecuta los comandos con los nombres generados
pdfjam --nup 2x2 "$PRIMARIO" --outfile "$SALIDA_TEMPORAL"
pdfunite "$SALIDA_TEMPORAL" "$SECUNDARIO" "$SALIDA_FINAL"

echo "Proceso completado. Archivo generado: $SALIDA_FINAL"
