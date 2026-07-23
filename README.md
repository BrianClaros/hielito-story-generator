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

## Generar una campaña con varias propuestas

El generador de campañas crea entre 2 y 6 propuestas completas, alterna
direcciones creativas y genera una hoja comparativa:

```bash
python hielito_campaign_generator.py \
  --objective "Promocionar la bolsa de 15 kg para eventos del fin de semana" \
  --variants 3 \
  --cost-profile draft \
  --concepts producto evento comercio \
  --weather hot \
  --temp 31
```

Cada campaña se guarda dentro de `output/campaigns/` con las imágenes,
metadatos, prompts y una `comparativa.jpg`. Generar varias propuestas utiliza
una llamada de texto compartida y una llamada de imagen por propuesta.

## Controlar costos

La generación de imágenes representa la mayor parte del gasto. Usá estos
perfiles:

- `draft`: calidad baja para explorar conceptos.
- `balanced`: calidad media para revisar propuestas individuales.
- `final`: calidad alta solamente para la pieza elegida.

Las campañas reutilizan un único copy entre propuestas. `--unique-copy` genera
un copy diferente por variante, pero aumenta el consumo. `--local-copy` evita
por completo la llamada de texto y usa las frases locales existentes.

El generador imprime el plan de consumo antes de comenzar. Las campañas
`final` de más de dos propuestas requieren `--allow-expensive`.

Flujo recomendado:

```bash
# Explorar dos opciones económicas
python hielito_campaign_generator.py \
  --objective "Promocionar bolsa de 15 kg" \
  --variants 2 \
  --cost-profile draft \
  --local-copy \
  --concepts producto comercio

# Generar una pieza final después de elegir concepto y referencia
python hielito_story_generator_V2.py \
  --require-openai \
  --full-openai-story \
  --auto-reference \
  --creative-concept producto \
  --cost-profile final \
  --objective "Promocionar bolsa de 15 kg"
```

## Publicación automática diaria en Instagram

`hielito_daily_story.py` genera la historia del día (según `obtener_prompt_del_dia`,
que asigna un objetivo comercial y un concepto creativo por día de la semana) y la
publica como Historia de Instagram usando la Content Publishing API de Meta
(Graph API), sin abrir ni automatizar ningún navegador.

Requisitos previos:

- Cuenta de Instagram profesional (Business o Creator) vinculada a una Página de
  Facebook.
- Una app en Meta for Developers con el permiso `instagram_content_publish`.
- Un access token válido para esa app y el ID de la cuenta profesional de
  Instagram (`instagram_business_account`), configurados en `.env`:

```bash
IG_ACCESS_TOKEN=tu-access-token
IG_BUSINESS_ACCOUNT_ID=tu-instagram-business-account-id
```

La Graph API exige que la imagen esté en una URL pública (no admite subir el
archivo directamente). Por eso el script levanta un servidor HTTP local,
lo expone unos segundos con un túnel de [ngrok](https://ngrok.com/) en una ruta
con token aleatorio, y lo cierra apenas Meta terminó de descargar la imagen.
Si tenés una cuenta de ngrok, configurá `NGROK_AUTHTOKEN` en `.env` para evitar
los límites de la cuenta anónima.

```bash
python hielito_daily_story.py --cost-profile balanced
```

- `--local-copy` evita la llamada de texto a OpenAI y usa las frases locales.
- `--dry-run` genera la imagen en `output/` pero no la publica.

Para automatizar la publicación diaria, programá este comando con `cron` (o el
programador de tareas que uses) a la hora que prefieras.

## Pruebas

```bash
python -m unittest -v
```
