# Archivo de Segmentos Creados

## Descripción

Cuando se crean segmentos en Mautic usando la función "CREAR SEGMENTOS", el sistema genera automáticamente un archivo `segmentos_creados.json` que contiene información detallada de cada segmento creado.

## Ubicación del archivo

```
segmentos_creados.json
```

Este archivo se crea en el mismo directorio donde se ejecuta la aplicación.

## Estructura del JSON

Cada segmento contiene la siguiente información:

```json
{
  "name": "Nombre del segmento (sin PRUEBA-)",
  "establishment": "Nombre del establecimiento",
  "type": "personal o corporate",
  "field": "Alias del campo en Mautic",
  "filters": {
    "campo_personalizado": "Nombre completo del campo con _txt",
    "operador_campo": "Operador usado (!=)",
    "valor_campo": "Valor del filtro (0)",
    "tipo_socio": "Personal o Corporativo",
    "fecha_ejecucion": "Fecha en formato YYYY-MM-DD"
  },
  "email_origen": "Nombre del boletín original (con PRUEBA-)",
  "fecha_creacion": "Fecha de creación del segmento"
}
```

## Ejemplo completo

Ver el archivo `segmentos_creados_ejemplo.json` para un ejemplo completo.

## Casos de uso

Este archivo es útil para:

1. **Auditoría**: Saber qué segmentos se crearon y cuándo
2. **Troubleshooting**: Verificar los filtros aplicados a cada segmento
3. **Replicación**: Recrear segmentos si es necesario
4. **Reportes**: Generar informes de segmentos creados
5. **Backup**: Mantener un registro de la configuración

## Notas importantes

- El archivo se **sobreescribe** cada vez que se ejecuta "CREAR SEGMENTOS"
- Si necesitas mantener un historial, renombra el archivo antes de crear nuevos segmentos
- El archivo está incluido en `.gitignore` para no subirlo al repositorio

## Formato de fecha

Las fechas están en formato ISO 8601: `YYYY-MM-DD`

Ejemplo: `2026-01-12` para el 12 de enero de 2026
