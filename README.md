# Caudal ecológico

Compara cada día el caudal medio de los ríos con el caudal mínimo ecológico que fija el plan
hidrológico para ese punto y ese mes. Caudales del SAIH de cada confederación; mínimos leídos
directamente del BOE. Web: https://asensio94.github.io/caudal-ecologico/

De momento cubre cuatro: el Júcar (42 de los 45 puntos de control del plan), el Guadiana
(13 de 35: los aforos de río; los de salida de embalse no publican el caudal soltado) y el Cantábrico
Oriental y Occidental (33 de los 108 aforos de río del SAIH, los que miden justo donde el plan fija
el mínimo) y el Guadalquivir (16 de los 17 puntos de su red de seguimiento).

Una segunda página, [«¿Llegará a 2027?»](https://asensio94.github.io/caudal-ecologico/2027.html),
reúne para las 6 274 masas de agua superficiales y subterráneas de España su estado ecológico y químico
(cuantitativo y químico en las subterráneas), el plazo para alcanzar el buen estado y las excepciones
de la Directiva Marco del Agua que se le aplican. 2027 es el último plazo: después solo cabe una
prórroga por condiciones naturales o rebajar el objetivo.

## Cómo funciona

La web explica todo esto por sí sola: el método cuenca a cuenca, por qué cada estación mide su
mínimo (una nota en cada fila), qué se deja fuera y por qué, los límites y las fuentes.

1. **Mínimos.** El Real Decreto 35/2023 aprobó los planes hidrológicos 2022–2027. Cada demarcación
   tiene su anexo con un mínimo por mes para cada masa de agua, en régimen ordinario y de sequía
   prolongada, y la estación que lo controla. `caudal/plan.py` descarga el bloque de la API de datos
   abiertos del BOE y lee las tablas. «Cese» se guarda como 0 (el río puede secarse ese mes); una
   casilla vacía queda sin mínimo.
   - Júcar: anexo XI, apéndice 5 (tablas 5.1 y 5.2, y la de seguimiento con su ROEA).
   - Guadiana: anexo VI, apéndice 6. Las tablas se localizan por el título de su apartado (6.1 puntos de
     control, 6.2 y 6.3 mínimos ordinarios, 6.7 sequía), no por su posición. Los tramos marcados (*)
     del Alto Guadiana solo serán exigibles cuando se recuperen sus acuíferos y se dejan fuera.
   - Cantábrico: anexos I (Oriental) y II (Occidental), apéndice 4.1. Tres valores por masa (aguas
     altas de enero a abril; medias en mayo, junio, noviembre y diciembre; bajas de julio a octubre),
     fijados en el extremo de aguas abajo de la masa, del que se da la superficie de cuenca. El
     Oriental parte algunas masas en tramos, cada uno con su punto; el régimen de sequía es
     «sequía prolongada» en el Oriental y «emergencia por sequía declarada» en el Occidental.
   - Guadalquivir: anexo VII, apéndice 6. Las tablas 6.1.3 (ordinario) y 6.2.2 (sequía prolongada)
     fijan en l/s el mínimo de 17 puntos con nombre, en cinco periodos (octubre–noviembre,
     diciembre–abril, mayo, junio y julio–septiembre). Las filas de sequía se emparejan con las
     ordinarias por río y lugar, ya que algún nombre cambia de grafía entre tablas («Posito», «Presa
     Pedro Marin»). Una cifra con coma decimal en una tabla en l/s queda sin valor (ver Límites).
2. **Estaciones.** La estación «EA 89» del SAIH Júcar es la ROEA 08089 del plan; en el Guadiana el
   plan ya nombra la estación del SIRA («CR2 25» → CR2-25). Así cada punto de control se une con su
   serie de caudal sin tabla manual. Las coordenadas se guardan en longitud y latitud (el Júcar las da
   en UTM 30N y se convierten).
   El plan del Cantábrico no nombra estaciones, así que se cruzan por geometría y cuenca, sin tabla
   manual: una estación del SAIH (catálogo de la red en el servidor cartográfico de la CHC) cuenta para
   una masa si está a menos de 50 m de su cauce (capa de masas de agua de la propia CHC; su visor
   asocia caudales ecológicos a estaciones de la misma forma) y si su superficie de cuenca, según el
   anuario de aforos del CEDEX, difiere menos de un 10 % de la del punto del plan. Con eso se distingue,
   en una confluencia, a qué río mide la estación, y se descartan las que están en mitad de una masa
   larga, que drenan bastante menos cuenca que el punto donde rige el mínimo.
   El Guadalquivir nombra sus puntos pero no da códigos, así que aquí sí hay una tabla breve en
   `caudal/sources/guadalquivir.py`, con la justificación de cada fila. Las estaciones de aforo se
   unen por el código SAIH que el anuario del CEDEX da a cada ROEA. Las presas y azudes usan la
   señal que la propia CHG muestra en su mapa de caudales: caudal circulante o desembalsado al río.
   Écija se lee en El Villar (ROEA 5165), como hace ese mapa, porque el aforo de Écija está fuera de
   servicio y El Villar, justo aguas arriba, drena la misma cuenca. Si el BOE dejara de listar un
   punto de la tabla, `plan` falla en vez de seguir con datos viejos.
3. **Caudal diario.** Se descargan las lecturas cada cinco (Júcar, Cantábrico) o diez minutos (Guadiana), o cada
   hora (Guadalquivir), de cada día (hora peninsular,
   días de 23 y 25 horas incluidos) y se hace la media. Con menos del 75 % de las lecturas, el día
   se queda sin dato.
4. **Comparación.** Un día queda «por debajo del mínimo» si su media está más de un 5 % por debajo
   del mínimo de ese mes. Los días seguidos por debajo forman un episodio; un día sin datos en medio
   no lo corta.
5. **Déficit.** (mínimo − caudal) × 86 400 s, en hm³: el agua que habría hecho falta.
6. **Publicación.** Una acción diaria vuelve a leer la última semana (el SAIH corrige sus datos
   provisionales), guarda las series y publica la página.

### ¿Llegará a 2027?

1. **Estado y excepciones.** `caudal/wfd.py` consulta Discodata, el punto SQL de solo lectura de la
   Agencia Europea de Medio Ambiente, sobre la base WISE WFD (versión fijada `v2r1`, tercer ciclo,
   `cYear = 2022`): estado de cada masa, tramo de plazo («2021 o antes», «2027 o antes», «después de
   2027») y excepciones con su motivo. El nombre en español y un punto representativo de cada masa
   salen de los servicios de mapas WFD2022 de la AEMA, leídos como atributos: no se descargan
   geometrías.
2. **Plazos del BOE.** `caudal/objectives.py` lee el apéndice de objetivos medioambientales del
   Real Decreto 35/2023 para el Júcar, el Guadiana y los dos planes del Cantábrico: año exacto y
   artículo aplicado. Los códigos del plan se traducen al código europeo (`18-33` → `ES080MSPF18-33`);
   coinciden los 1 363.
3. **Clasificación.** `caudal/outlook.py` da a cada masa una situación: en buen estado, prórroga hasta
   2027, más allá de 2027 por condiciones naturales, más allá de 2027 sin alegar condiciones naturales
   (solo o además viabilidad técnica o coste, o sin motivo), objetivos menos rigurosos o sin evaluar.
   Donde hay año del BOE, manda sobre el tramo de la AEMA.
4. **Publicación.** `docs/2027.html` con el resumen por demarcación y un buscador sobre
   `docs/masas-2027.json` (datos abiertos). `python -m caudal.cli wfd` se ejecuta el día 1 de cada mes,
   con la relectura del plan.

### Señales para Estado de las IBA

`docs/signals.json` sigue el contrato de `estado-iba/CONTRATO.md`:

- `river_flow`: una por estación con algún día por debajo del mínimo en 30 días (con el margen del 5 %).

El estado de las masas de agua frente a 2027 no se envía: el contrato del hub no tiene ese tipo y
su validador lo contaría como error. Sigue en `docs/2027.html` y `docs/masas-2027.json`. El código
(`signals.water_status`) está listo para cuando el hub lo acepte: una señal por masa que no está en
buen estado o tiene una excepción, con `deadline` a `null`.

## Por qué puede faltar agua

`python -m caudal.cli context` (una vez al mes, con `plan`) guarda en `data/context.csv` lo que los
propios planes dicen del entorno de cada punto, y la web lo muestra en cada fila:

- **Presiones sobre el caudal** de la masa de río: extracciones, presas y azudes, regulación del régimen
  (códigos P3, P4-2 y P4-3 de la Directiva Marco). Se leen de los planes 2022–2027 tal como España los envió a
  la Unión Europea, en los servicios WISE de la Agencia Europea de Medio Ambiente: el Ministerio publica las
  mismas capas, pero su servidor de mapas falla y sus descargas piden superar una prueba antirrobots. La masa
  se busca por el código que el plan da al punto; en el Guadalquivir, la del mismo río más cercana (300 m).
- **Estado cuantitativo del acuífero** que hay justo debajo de la estación (bueno o malo, y si está en riesgo).
- **Tendencia del nivel del acuífero, solo en el Júcar**: la CHJ publica todas las medidas validadas de su red
  piezométrica. Por piezómetro, mediana anual del nivel estático y pendiente de Theil–Sen; cuentan los que
  tienen 10 años medidos en los últimos 25 y alguno en los últimos 3. Por acuífero, la mediana.

Es lo que el plan declara, no una comprobación: no dice qué presa o qué pozo, y puede quedarse corto (el
Gigüela IV figura sin presiones, con el acuífero de debajo en mal estado).

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
- En el Cantábrico, 75 aforos con caudal no se comparan: 20 no figuran en el anuario del CEDEX (sin
  superficie de cuenca), uno no está sobre una masa con mínimo y la mayoría están aguas arriba del
  punto del plan. Compararlos exigiría interpolar el mínimo por cuenca, cosa que el plan del Occidental
  permite pero no detalla. Tampoco se comparan las masas con un tramo declarado reserva natural
  fluvial (marcadas * en el BOE), que tiene mínimos propios. `python -m caudal.cli plan` lista cada
  aforo descartado y el motivo.
- «¿Llegará a 2027?» enseña el estado con que se aprobó el plan (datos de 2019–2021 en la mayoría de
  cuencas), no el de hoy. Las fichas de masas del Ministerio (MITECO) están tras una protección
  anti-robots y no se leen; en las cuencas sin año del BOE solo hay los tramos de la AEMA.
- «Más allá de 2027 sin alegar condiciones naturales» describe lo comunicado a Europa, no una
  infracción: la memoria del plan puede justificar más de lo que recoge la base europea.
- En las masas marcadas ** del Cantábrico Occidental el mínimo de sequía no rige para los
  aprovechamientos en ZEC o ZEPA; da igual mientras se aplique siempre el régimen ordinario.
- En el Guadalquivir solo se comparan los puntos de la red de seguimiento (6.1.3). Los mínimos por
  masa del apéndice 6.1.1 (402 masas, sin estación asignada) y los de salida de embalse (6.1.4)
  quedan para más adelante. La presa de Cordobilla (Genil) no se compara: el SAIH publica lo que
  alivian sus compuertas y lo que se bombea, no lo que circula río abajo.
- En Arroyo María el BOE dice «1,22» en mayo y junio dentro de una tabla en l/s, frente a 370–610 l/s
  el resto del año. Parece una errata (¿1.220 l/s? ¿1,22 m³/s?) y esos dos meses quedan sin mínimo en
  lugar de adivinar el valor.
- En el Corbones (Carmona), el mínimo de sequía de diciembre a abril es mayor que el ordinario
  (352 l/s frente a 300). Se guarda tal cual lo publica el BOE.
- El aforo del Guadiamar en Aznalcázar marca 0 desde julio. No es una avería: registró las crecidas
  del invierno, y El Guijo, aguas arriba, lleva entre 1 y 5 l/s. El río está casi seco frente a un
  mínimo de 400–650 l/s fijado por estudios específicos de ese tramo, aguas arriba de Doñana.

## Pendiente

- Tajo: mínimos escalonados por fechas hasta 2027, y hace falta permiso de la confederación para
  reutilizar su SAIH. Ebro y Segura, pendientes de la clave de la API y de aceptar las condiciones
  de su visor, respectivamente.
- Calificación mensual al estilo del Ministerio (leve, media, grave).
- Cruce con las declaraciones de sequía prolongada.
- Año exacto del BOE para las demás cuencas intercomunitarias: Miño-Sil, Duero, Tajo, Guadalquivir,
  Segura, Ebro, Ceuta y Melilla (cada plan tiene su propia tabla). Las cuencas internas no están en
  el real decreto y seguirán con los tramos de la AEMA.
- Niveles piezométricos fuera del Júcar (cada confederación los publica por su cuenta) y qué presa o toma
  concreta hay aguas arriba de cada punto.

## Uso

```bash
pip install -r requirements.txt
python -m caudal.cli plan            # mínimos y estaciones desde el BOE, los SAIH, el SIRA y el CEDEX
python -m caudal.cli context         # presiones, acuíferos y niveles piezométricos (AEMA y CHJ)
python -m caudal.cli fetch --days 30 # medias diarias de los últimos 30 días
python -m caudal.cli wfd             # estado, plazos y excepciones de todas las masas (AEMA y BOE)
python -m caudal.cli page            # docs/index.html, docs/2027.html, masas-2027.json y signals.json
python -m pytest -q
```

## Datos que se guardan

| Fichero | Contenido |
|---|---|
| `data/stations.csv` | Puntos de control: estación, río, masa de agua, ROEA, longitud y latitud (ETRS89) |
| `data/requirements/<cuenca>.csv` | Mínimo mensual por estación y régimen, con su referencia legal y enlace al BOE |
| `data/context.csv` | Presiones sobre el caudal de la masa de río y estado del acuífero bajo cada estación (planes 2022–2027 vía la AEMA); tendencia piezométrica en el Júcar |
| `data/cedex/cantabrico-estaf.csv` | Copia del anuario de aforos 2021–2022 del CEDEX (Cantábrico): el servidor del CEDEX corta las conexiones de GitHub, y la edición no cambia |
| `data/excluded.csv` | Puntos del plan y aforos que no se comparan, con el motivo; la web los lista |
| `data/flows/<estación>.csv` | Media diaria, lecturas recibidas y esperadas, fuente y hora de descarga |
| `data/wfd/water_bodies.csv` | Cada masa de agua: código europeo, demarcación, categoría, estado, tramo de plazo, fecha de entrega y punto representativo |
| `data/wfd/exemptions.csv` | Excepciones por masa y aspecto: artículo, motivo y presiones |
| `data/wfd/objectives.csv` | Año y artículos del BOE por masa, con su referencia legal y enlace |

## Fuentes y licencias

- Caudales: [SAIH Júcar](https://saih.chj.es/), Confederación Hidrográfica del Júcar;
  [SIRA](https://siraguadiana.com/), Confederación Hidrográfica del Guadiana (perfil público del visor,
  sin cuenta; su aviso legal permite reproducir citando la fuente);
  [SAIH Cantábrico](https://visor.saichcantabrico.es/), Confederación Hidrográfica del Cantábrico
  (descarga histórica del visor; su aviso legal permite reutilizar citando la fuente);
  [SAIH Guadalquivir](https://www.chguadalquivir.es/saih/), Confederación Hidrográfica del
  Guadalquivir (gráfica histórica del visor, sesión anónima; su aviso legal permite reproducir
  citando el origen).
- Estaciones y masas del Cantábrico: servicios de mapas de la CHC (`nodoide.chcantabrico.es`, red SAIH
  y masas de agua del plan); superficie de cuenca, y código SAIH de cada
  aforo del Guadalquivir: [Anuario de aforos](https://ceh.cedex.es/anuarioaforos/) del CEDEX.
- Presiones y estado de los acuíferos: [servicios WISE de la Agencia Europea de Medio
  Ambiente](https://water.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD) (planes 2022–2027 enviados por
  España). Niveles piezométricos del Júcar: [red piezométrica de la
  CHJ](https://www.chj.es/es-es/medioambiente/redescontrol/Paginas/Piezometria.aspx).
- Mínimos: [Real Decreto 35/2023](https://www.boe.es/buscar/act.php?id=BOE-A-2023-3511), BOE,
  vía su API de datos abiertos.
- Estado, excepciones y nombres de las masas: [WISE WFD](https://discodata.eea.europa.eu/), Agencia
  Europea de Medio Ambiente, CC BY 4.0 (Discodata y servicios de mapas WFD2022).
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
