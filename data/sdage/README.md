# Tablas de los SDAGE transcritas

Loire-Bretagne y Rhône-Méditerranée solo publican sus caudales de los puntos nodales (DOE, DSA, DCR)
dentro del PDF del SDAGE 2022–2027. En lugar de leer el PDF cada mes, `plan-fr` lee estas dos
transcripciones revisadas; si el SDAGE cambia, se rehacen y la revisión queda en el historial de git.

| Fichero | Fuente | Páginas del PDF |
| --- | --- | --- |
| `loire-bretagne.csv` | [SDAGE Loire-Bretagne 2022–2027, tomo 1](https://sdage-sage.eau-loire-bretagne.fr/files/live/mounts/midas/Donnees-et-documents/Sdage/AELB-SDAGE_Tome1_maj_car), capítulo 7, tabla de objetivos de cantidad en los puntos nodales (aprobado el 18 de marzo de 2022) | 112–119 |
| `rhone-mediterranee.csv` | [SDAGE Rhône-Méditerranée 2022–2027, volumen principal](https://rhone-mediterranee.eaufrance.fr/sites/sierm/files/content/2022-03/20220318-SDAGE-2022-2027_vol.principal_ADOPTE-1.pdf), disposición 7-07, tabla 7C (aprobado el 21 de marzo de 2022) | 328–332 |

## Cómo se hicieron

1. **Extracción.** Las tablas se leyeron del PDF con pdfplumber, por la posición de cada palabra en la
   página. El script de extracción no está en el repositorio: no se vuelve a ejecutar, y lo que cuenta
   es el resultado revisado.
2. **Revisión a mano.** Se corrigieron los valores que el PDF parte con un espacio (Lre7: DOE «5 .7» →
   5,7; Alg: DSA «1 .0» → 1,0) y se limpiaron los nombres de río y lugar. En Rhône-Méditerranée, la
   marca «(*)» (valor que puede revisarse durante el ciclo) pasa a la columna `revisable`.
3. **Comprobación.** Cada DCR se volvió a buscar en el texto del PDF, en la fila de su punto. Las únicas
   diferencias venían de que el PDF escribe algunos códigos con una I en lugar de una l (BI1, VI1, CI);
   ningún valor difiere.
4. **Estación.** `code` es la estación de Hub’Eau que se compara; vacía, el punto queda fuera y `reason`
   dice por qué (en francés, como lo muestra la web).
   - Loire-Bretagne: `agency_code` es el código que da la [capa de puntos nodales de la
     agencia](https://donnees-documents.eau-loire-bretagne.fr/home/donnees/sdage-2022-2027--projet-cartographique-qgis.html).
     Si Hub’Eau tiene una estación con el nombre que escribe el SDAGE y es otra, manda el nombre.
     Cuatro puntos con solo el código de la agencia (Bl2, Ell, Lre2, Agr) se comprobaron por el nombre
     de la estación en Hub’Eau.
   - Rhône-Méditerranée: la tabla da río, lugar, departamento y masa de agua (`water_body_code`), sin
     código de estación. Se elige la estación de Hub’Eau del departamento que lleva ese nombre; donde
     el lugar lleva un calificativo («aval», un barrio), ese calificativo decide (puntos 22 y 93).
5. **Fuera, por dudosos.** Mejor un punto de menos que un umbral leído en el sitio equivocado:
   - varias estaciones con el mismo nombre y el SDAGE no dice cuál (Alg; RM 20 y 83);
   - estación «à réimplanter», «à aménager» o «à déterminer» según el SDAGE (RM 58, 89, 116 y 123);
   - estación lejos del lugar del SDAGE: Lay (N3511610, en La Bretonnière-la-Claye) y Lez (RM 85,
     Y3210021, 3 km aguas abajo del puente Garigliano);
   - punto seguido por un piezómetro y no por una estación de caudal (RM 39).
   Los puntos sin DCR cifrado («à définir») quedan fuera solos, al leer el fichero.

No se guardan nombres de personas: los comentarios libres de Hub’Eau no se usan.
