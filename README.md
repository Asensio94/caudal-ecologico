# Caudal ecológico

Compara cada día el caudal medio de los ríos con el caudal mínimo ecológico que fija el plan
hidrológico para ese punto y ese mes. Caudales del SAIH de cada confederación; mínimos leídos
directamente del BOE. Web: https://asensio94.github.io/caudal-ecologico/

De momento cubre dos demarcaciones: el Júcar (42 de los 45 puntos de control del plan) y el Guadiana
(13 de 35: los aforos de río; los de salida de embalse no publican el caudal soltado).

## Cómo funciona

1. **Mínimos.** El Real Decreto 35/2023 aprobó los planes hidrológicos 2022–2027. Cada demarcación
   tiene su anexo con un mínimo por mes para cada masa de agua, en régimen ordinario y de sequía
   prolongada, y la estación que lo controla. `caudal/plan.py` descarga el bloque de la API de datos
   abiertos del BOE y lee las tablas. «Cese» se guarda como 0 (el río puede secarse ese mes); una
   casilla vacía queda sin mínimo.
   - Júcar: anexo XI, apéndice 5 (tablas 5.1 y 5.2, y la de seguimiento con su ROEA).
   - Guadiana: anexo VI, apéndice 6. Las tablas se localizan por el título de su apartado (6.1 puntos de
     control, 6.2 y 6.3 mínimos ordinarios, 6.7 sequía), no por su posición. Los tramos marcados (*)
     del Alto Guadiana solo serán exigibles cuando se recuperen sus acuíferos y se dejan fuera.
2. **Estaciones.** La estación «EA 89» del SAIH Júcar es la ROEA 08089 del plan; en el Guadiana el
   plan ya nombra la estación del SIRA («CR2 25» → CR2-25). Así cada punto de control se une con su
   serie de caudal sin tabla manual. Las coordenadas se guardan en longitud y latitud (el Júcar las da
   en UTM 30N y se convierten).
3. **Caudal diario.** Se descargan las lecturas cada cinco (Júcar) o diez minutos (Guadiana) de cada día (hora peninsular,
   días de 23 y 25 horas incluidos) y se hace la media. Con menos del 75 % de las lecturas, el día
   se queda sin dato.
4. **Comparación.** Un día queda «por debajo del mínimo» si su media está más de un 5 % por debajo
   del mínimo de ese mes. Los días seguidos por debajo forman un episodio; un día sin datos en medio
   no lo corta.
5. **Déficit.** (mínimo − caudal) × 86 400 s, en hm³: el agua que habría hecho falta.
6. **Publicación.** Una acción diaria vuelve a leer la última semana (el SAIH corrige sus datos
   provisionales), guarda las series y publica la página.

## Contraste / validación

- La media diaria de la estación EA 89 Huerto Mulet (variable 13070) del 7/10/2026 sale con 287 de
  288 lecturas. El SAIH asigna esa variable a la masa 18-33, la misma que el BOE asigna al ROEA 08089.
- Pendiente: comparar con el anuario de aforos (ROEA) validado cuando salga el del año 2025-26 y con
  los informes de seguimiento del plan que publica la confederación.

## Límites

- Los datos del SAIH son provisionales. Un día por debajo es un indicio, no una infracción: el plan
  mide el cumplimiento por meses y años, y la calificación corresponde a la confederación.
- Se aplica siempre el régimen ordinario; todavía no se cruzan las declaraciones de sequía prolongada.
- Las curvas de gasto son menos precisas con poco caudal, justo donde se mira. El margen del 5 % lo
  amortigua, no lo elimina.
- Tres puntos de control del Júcar (ROEA 08092, 08112 y 08119) no tienen aforo con datos públicos.
- En el Guadiana, 20 puntos se controlan a la salida de un embalse o azud y el visor SIRA no publica
  ese caudal; tampoco el aforo NR2-12, ligado a un tramo aún no exigible.

## Pendiente

- Cantábrico. El lector está probado (`sources/cantabrico.py`), pero el plan da los mínimos por tramo
  con coordenadas y por estaciones del año, sin nombrar aforo: hace falta un cruce espacial. El Tajo, con mínimos escalonados por
  fechas hasta 2027, necesita además permiso de la confederación para reutilizar su SAIH.
- Calificación mensual al estilo del Ministerio (leve, media, grave).
- Cruce con las declaraciones de sequía prolongada.

## Uso

```bash
pip install -r requirements.txt
python -m caudal.cli plan            # mínimos y estaciones desde el BOE, el SAIH y el SIRA
python -m caudal.cli fetch --days 30 # medias diarias de los últimos 30 días
python -m caudal.cli page            # docs/index.html
python -m pytest -q
```

## Datos que se guardan

| Fichero | Contenido |
|---|---|
| `data/stations.csv` | Puntos de control: estación, río, masa de agua, ROEA, longitud y latitud (ETRS89) |
| `data/requirements/<cuenca>.csv` | Mínimo mensual por estación y régimen, con su referencia legal y enlace al BOE |
| `data/flows/<estación>.csv` | Media diaria, lecturas recibidas y esperadas, fuente y hora de descarga |

## Fuentes y licencias

- Caudales: [SAIH Júcar](https://saih.chj.es/), Confederación Hidrográfica del Júcar;
  [SIRA](https://siraguadiana.com/), Confederación Hidrográfica del Guadiana (perfil público del visor,
  sin cuenta; su aviso legal permite reproducir citando la fuente).
- Mínimos: [Real Decreto 35/2023](https://www.boe.es/buscar/act.php?id=BOE-A-2023-3511), BOE,
  vía su API de datos abiertos.
- Código: MIT. Datos propios (medias diarias y comparaciones): CC BY 4.0.

Forma parte de un conjunto de proyectos hermanos:
[Observatorio de alegaciones](https://github.com/Asensio94/observatorio-alegaciones) ·
[Vigía de incendios](https://github.com/Asensio94/vigia-incendios) ·
[Centinela Natura](https://github.com/Asensio94/centinela-natura) ·
[Vigilancia de humedales](https://github.com/Asensio94/vigilancia-humedales) ·
[Sub Nocte](https://github.com/Asensio94/sub-nocte) ·
[Riesgo de tendidos para aves](https://github.com/Asensio94/riesgo-tendidos-aves) ·
[Grafo de promotores](https://github.com/Asensio94/grafo-promotores) ·
[Cartera de las cotizadas](https://github.com/Asensio94/cartera-cotizadas) ·
[Cuaderno de campo](https://github.com/Asensio94/cuaderno-campo)
