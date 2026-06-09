# Generador de historias de Hielito

Genera historias de Instagram de 1080x1920 usando las plantillas locales. Puede
crear el contenido con OpenAI y valida las afirmaciones comerciales contra
`business_facts.json`.

## Instalación

```bash
python -m pip install -r requirements.txt
```

## Generación local

```bash
python hielito_story_generator_V2.py --weather hot --temp 32 --stock medium
```

## Generación con OpenAI

Configurá la clave en un archivo `.env` local:

```bash
OPENAI_API_KEY=tu-clave
```

También podés exportarla directamente en la terminal:

```bash
export OPENAI_API_KEY="tu-clave"
```

Luego generá la historia:

```bash
python hielito_story_generator_V2.py \
  --use-openai \
  --weather hot \
  --temp 32 \
  --stock medium \
  --objective "Promocionar bolsas para eventos del fin de semana"
```

`--use-openai` utiliza el contenido local como respaldo si la API falla.
`--require-openai` finaliza con error cuando OpenAI no puede generar una historia
válida.

Los PNG y sus metadatos se guardan en `output/`. El JSON de metadata indica si
el contenido fue generado por `openai` o por el respaldo `local`.

## Fotografía publicitaria generada por OpenAI

OpenAI puede generar la escena visual usando los datos confirmados del negocio.
El sistema agrega después el texto exacto para evitar precios o teléfonos
deformados dentro de la imagen.

La fotografía generada no incluye texto ni logos. Los precios, condiciones de
entrega, WhatsApp y marca se agregan desde `business_facts.json` y la
configuración local.

```bash
python hielito_story_generator_V2.py \
  --require-openai \
  --require-openai-image \
  --creative-concept asado \
  --weather hot \
  --temp 32 \
  --stock medium \
  --objective "Promocionar bolsas de 15 kg para eventos"
```

Conceptos disponibles: `asado`, `evento`, `producto` y `comercio`.

Para acercar la dirección visual a una campaña existente, exportá una imagen de
referencia y usala así:

```bash
python hielito_story_generator_V2.py \
  --require-openai \
  --require-openai-image \
  --reference-image referencias/pomelli-asado.png \
  --creative-concept asado \
  --objective "Promocionar bolsas de 15 kg para el fin de semana"
```

También podés permitir que el sistema seleccione automáticamente una referencia
compatible:

```bash
python hielito_story_generator_V2.py \
  --require-openai \
  --require-openai-image \
  --auto-reference \
  --creative-concept producto \
  --objective "Promocionar bolsas de 15 kg"
```

La clasificación está en `referencias/reference_library.json`. Las referencias
solo guían el estilo visual; sus textos y afirmaciones nunca se consideran datos
comerciales vigentes.

## Historia completa generada por OpenAI

Este modo no agrega textos ni tarjetas gráficas con Pillow. OpenAI recibe una
referencia visual, el logo actual y los datos confirmados, y genera la pieza
completa:

```bash
python hielito_story_generator_V2.py \
  --require-openai \
  --full-openai-story \
  --auto-reference \
  --creative-concept producto \
  --objective "Promocionar la bolsa de 15 kg a $6500"
```

Las historias completas deben revisarse visualmente antes de publicarse porque
un modelo de imágenes todavía puede deformar letras o números. La metadata marca
estas piezas con `requires_visual_review: true` y guarda el prompt utilizado.

## Pruebas

```bash
python -m unittest -v
```
