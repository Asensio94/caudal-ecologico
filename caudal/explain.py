"""The page's explanation: how each number is made, basin by basin, and everything left out.

The page has to stand on its own: whoever reads a "por debajo" must be able to see where
the minimum comes from, why that gauge measures it and what the method cannot see,
without opening the repository. Counts come from the data, so the text cannot go stale.
"""
from __future__ import annotations

from html import escape

from .config import TOLERANCE
from .plan import CATCHMENT_TOLERANCE, SNAP_METRES
from .sources import chj_piezometry, wise

BOE = "https://www.boe.es/buscar/act.php?id=BOE-A-2023-3511"
CEDEX = "https://ceh.cedex.es/anuarioaforos/"
EEA_WFD = "https://water.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD"
MITECO_GW = "https://www.miteco.gob.es/es/cartografia-y-sig/ide/descargas/agua/estado-masas-agua-phc-2022-2027.html"


def _excluded(items: list[str], what: str) -> str:
    if not items:
        return ""
    li = "\n".join(f"        <li>{escape(i)}</li>" for i in items)
    one = len(items) == 1
    what = what.replace("puntos", "punto").replace("aforos", "aforo") if one else what
    return (f'\n      <details><summary>{len(items)} {what} que no se {"compara" if one else "comparan"}, y por qué</summary>\n'
            f'      <ul>\n{li}\n      </ul></details>')


def _of(k: int, total: int) -> str:
    return f"{k} de {total}"


def method_html(compared: dict[str, int], excluded: dict[str, list[str]], links: dict[str, str],
                ctx: dict[str, int]) -> str:
    """`compared` and `excluded` by basin key; `links` the SAIH address of each basin; `ctx` the
    context counts (stations with pressures, with a poor aquifer…) computed by the page."""
    n, x = compared, {k: len(v) for k, v in excluded.items()}
    c = ctx
    return f"""
  <section class="method">
    <h2>Cómo se calcula</h2>
    <ol>
      <li><b>El mínimo sale del BOE.</b> El <a href="{BOE}">Real Decreto 35/2023</a> aprobó los planes
      hidrológicos 2022–2027 de las demarcaciones intercomunitarias. Cada una tiene su anexo con los caudales
      mínimos, en régimen ordinario y en sequía prolongada. El programa descarga esas tablas de la API de datos
      abiertos del BOE y las lee tal cual, sin copiarlas a mano; cada mínimo de la tabla enlaza a su apartado.
      «Cese» (meses en que un río temporal puede secarse) cuenta como mínimo cero; una casilla vacía, como mes
      sin mínimo.</li>
      <li><b>Cada mínimo, con su estación.</b> Un mínimo se fija en un punto concreto del río. Solo se compara
      con una estación que mida en ese punto; cómo se decide depende del plan de cada cuenca (abajo).</li>
      <li><b>El caudal sale del SAIH.</b> El Sistema Automático de Información Hidrológica de cada confederación
      publica el caudal cada pocos minutos o cada hora. Se toman las lecturas de cada día en hora peninsular
      (los días del cambio de hora tienen 23 y 25 horas) y se hace la media. Si llegan menos del 75 % de las
      lecturas esperadas, el día se queda sin dato en vez de dar una media sesgada.</li>
      <li><b>Se comparan.</b> Un día queda «por debajo del mínimo» si su caudal medio es más de un
      {TOLERANCE * 100:.0f} % inferior al mínimo de ese mes. Ese margen absorbe el error de medida, que es mayor
      cuanto menos agua lleva el río. Varios días seguidos por debajo forman un episodio; un día sin datos en
      medio no lo corta.</li>
      <li><b>Se suma lo que faltó.</b> El déficit es la diferencia entre el mínimo y el caudal, multiplicada por
      los 86.400 segundos del día: el volumen de agua que habría hecho falta, en hectómetros cúbicos.</li>
      <li><b>Se actualiza cada mañana.</b> Una tarea automática vuelve a leer la última semana, porque el SAIH
      corrige sus datos provisionales durante unos días, guarda las series y publica esta página.</li>
    </ol>
    <table class="params">
      <tr><th>Parámetro</th><th class="num">Valor</th></tr>
      <tr><td>Lecturas mínimas para dar un día por bueno</td><td class="num">75 %</td></tr>
      <tr><td>Margen por error de medida</td><td class="num">{TOLERANCE * 100:.0f} %</td></tr>
      <tr><td>Días sin datos dentro de un episodio que no lo cortan</td><td class="num">1</td></tr>
      <tr><td>Días que se vuelven a leer cada mañana</td><td class="num">7</td></tr>
      <tr><td>Cantábrico: distancia máxima de la estación al cauce de la masa</td><td class="num">{SNAP_METRES} m</td></tr>
      <tr><td>Cantábrico: diferencia máxima de cuenca con el punto del plan</td><td class="num">{CATCHMENT_TOLERANCE * 100:.0f} %</td></tr>
    </table>

    <h2>Cuenca por cuenca</h2>
    <h3>Júcar</h3>
    <p>Anexo XI, apéndice 5: un mínimo por mes para cada masa de agua (tabla 5.1, ordinario; 5.2, sequía). El
    plan dice qué aforo controla cada masa por su código ROEA (Red Oficial de Estaciones de Aforo), y el SAIH Júcar los numera igual (su «EA 89» es
    el ROEA 08089), así que la unión es directa. Lecturas cada cinco minutos. Se comparan {n.get("jucar", 0)}
    de los {n.get("jucar", 0) + x.get("jucar", 0)} puntos de control.</p>{_excluded(excluded.get("jucar", []), "puntos del plan")}

    <h3>Guadiana</h3>
    <p>Anexo VI, apéndice 6: la tabla 6.1 nombra la estación de cada masa; 6.2 y 6.3 dan los mínimos ordinarios
    mes a mes y 6.7 los de sequía. Las tablas se buscan por el título de su apartado, no por su posición. Los
    caudales salen del visor SIRA con su perfil público, sin cuenta, cada diez minutos. Solo publica el caudal de
    los aforos de río; en los puntos situados a la salida de un embalse o azud no da el caudal soltado al río, y
    esos no se pueden comparar. Dos tramos del Alto Guadiana (marcados con asterisco) solo tendrán mínimo
    exigible cuando se recuperen sus acuíferos. En un caso el BOE pone junto a la estación el código de una masa
    y el nombre de otra; se usa la del nombre, y la fila lo indica. Se comparan {n.get("guadiana", 0)} de los
    {n.get("guadiana", 0) + x.get("guadiana", 0)} puntos de control.</p>{_excluded(excluded.get("guadiana", []), "puntos del plan")}

    <h3>Cantábrico</h3>
    <p>Anexos I (Cantábrico Oriental) y II (Occidental), apéndice 4.1: tres mínimos por masa, uno para aguas
    altas (enero a abril), otro para aguas medias (mayo, junio, noviembre y diciembre) y otro para aguas bajas
    (julio a octubre). Se fijan en el extremo de aguas abajo de cada masa, del que el plan da las coordenadas y
    la superficie de cuenca. El Oriental parte algunas masas en tramos con su propio punto. El régimen de sequía
    se llama «sequía prolongada» en el Oriental y «emergencia por sequía declarada» en el Occidental.</p>
    <p>Este plan no nombra estaciones. Una estación del SAIH cuenta para una masa si está a menos de
    {SNAP_METRES} m del cauce de la masa (según la capa de masas de agua de la propia confederación, cuyo visor
    asocia así estaciones y caudales ecológicos) y si su superficie de cuenca, según el
    <a href="{CEDEX}">anuario de aforos del CEDEX</a>, difiere menos de un {CATCHMENT_TOLERANCE * 100:.0f} % de la
    del punto del plan. La cuenca decide a qué río mide una estación junto a una confluencia, y deja fuera las
    que están en mitad de una masa larga: drenan bastante menos agua que el punto donde rige el mínimo, y
    compararlas exageraría los incumplimientos. Cada fila dice a qué distancia del cauce está la estación y
    cuánta cuenca drena. Quedan fuera también las masas con un tramo declarado reserva natural fluvial, que
    tiene mínimos propios en otro apéndice. En las masas que el BOE marca con dos asteriscos el mínimo de
    sequía no rige para los usos en espacios de la Red Natura 2000; aquí no cambia nada, porque siempre se
    aplica el ordinario. Lecturas cada cinco minutos; algunas estaciones tienen huecos reales en el SAIH, que
    aparecen como días sin dato. Se comparan {n.get("cantabrico", 0)} de los
    {n.get("cantabrico", 0) + x.get("cantabrico", 0)} aforos del SAIH con caudal.</p>{_excluded(excluded.get("cantabrico", []), "aforos")}

    <h3>Guadalquivir</h3>
    <p>Anexo VII, apéndice 6: las tablas 6.1.3 (ordinario) y 6.2.2 (sequía) fijan, en litros por segundo, el
    mínimo de 17 puntos con nombre del Guadalquivir y sus afluentes principales, en cinco periodos: octubre y
    noviembre, diciembre a abril, mayo, junio, y julio a septiembre. El plan nombra los puntos pero no da
    códigos, así que aquí hay una pequeña tabla hecha a mano, y cada fila explica su elección. Para las
    estaciones de aforo, el anuario del CEDEX da la señal del SAIH de cada código ROEA. Para presas y azudes,
    se usa la señal que la propia confederación muestra en su mapa de caudales (caudal circulante o soltado al
    río). Si el BOE dejara de listar alguno de esos puntos, el programa se detiene en vez de seguir con datos
    viejos. Lecturas cada hora, de la gráfica histórica del visor.</p>
    <p>Tres rarezas del BOE, que se respetan tal cual o se dejan en blanco, sin adivinar: en Arroyo María la
    tabla dice «1,22» l/s en mayo y junio, frente a 370–610 el resto del año, y esos dos meses quedan sin mínimo;
    en el Corbones, el mínimo de sequía de diciembre a abril (352 l/s) es mayor que el ordinario (300 l/s); y
    algunos puntos cambian de grafía entre la tabla ordinaria y la de sequía, por lo que se emparejan por río y
    lugar. El aforo del Guadiamar en Aznalcázar marca cero desde julio: no es una avería (registró las crecidas
    del invierno) y aguas arriba, en El Guijo, el río lleva entre 1 y 5 l/s.</p>
    <p>Por ahora no se comparan los mínimos por masa de agua (tabla 6.1.1, 402 masas sin estación asignada) ni los
    de salida de embalse (6.1.4). Se comparan {n.get("guadalquivir", 0)} de los
    {n.get("guadalquivir", 0) + x.get("guadalquivir", 0)} puntos de la red de seguimiento.</p>{_excluded(excluded.get("guadalquivir", []), "puntos del plan")}

    <h2>Por qué puede faltar agua</h2>
    <p>Cada fila añade lo que el propio plan hidrológico dice del entorno del punto. No explica un día concreto,
    pero ayuda a distinguir un río que se queda corto por lo que se le quita de uno que simplemente viene seco.</p>
    <ul>
      <li><b>Presiones sobre el caudal.</b> Los planes enumeran, masa a masa, las «presiones significativas»:
      extracciones (para regadío, abastecimiento, industria, hidroeléctrica…), presas y azudes, y alteraciones
      del régimen del río. Aquí se muestran solo las que restan o regulan caudal, no las de contaminación. La masa
      se busca en el mismo código que el plan asigna al punto; en el Guadalquivir, que no da códigos, es la masa
      del mismo río más cercana a la estación (a menos de {wise.SEARCH_METRES} m). Se ha encontrado la masa de
      {_of(c.get("rivers", 0), c.get("stations", 0))} puntos, y {c.get("pressured", 0)} tienen alguna presión de
      ese tipo.</li>
      <li><b>Estado del acuífero.</b> Debajo de casi todos los ríos hay una masa de agua subterránea. Los planes
      dicen si está en buen o mal estado cuantitativo: en mal estado se bombea más de lo que se recarga o el
      bombeo ya afecta a ríos y humedales. Cuando un acuífero baja, el río deja de recibir agua de él en verano, o
      empieza a perderla. Se toma la masa que hay justo debajo de la estación. {c.get("poor", 0)} puntos están
      sobre un acuífero en mal estado.</li>
      <li><b>Nivel del acuífero (solo Júcar).</b> La Confederación Hidrográfica del Júcar publica todas las
      medidas validadas de sus piezómetros, los pozos donde mide la altura del agua subterránea. Para cada
      piezómetro se toma la mediana de cada año y se calcula la pendiente de Theil–Sen (la mediana de las
      pendientes entre cada par de años), a la que un año raro no arrastra. Cuentan los piezómetros con al menos
      {chj_piezometry.MIN_YEARS} años medidos en los últimos {chj_piezometry.FIRST_YEAR_BACK} y alguno en los
      últimos {chj_piezometry.RECENT_YEARS}. El dato del acuífero es la mediana de sus piezómetros. Si baja año
      tras año, también en los húmedos, se saca más agua de la que entra; si solo baja en años secos, es sequía.
      {c.get("trend", 0)} puntos tienen este dato.</li>
    </ul>
    <p>De los {c.get("below", 0)} puntos con algún día por debajo del mínimo en estos 30 días,
    {c.get("below_pressured", 0)} tienen presiones sobre el caudal señaladas por el plan, {c.get("below_poor", 0)}
    están sobre un acuífero en mal estado y {c.get("below_either", 0)} tienen al menos una de las dos cosas.</p>
    <p>Es lo que el plan declara, no una comprobación sobre el terreno. Puede quedarse corto (el Gigüela en
    Villafranca lleva semanas seco y el plan no señala presiones en esa masa, aunque el acuífero de debajo sí
    está en mal estado) y no dice qué presa o qué pozo concreto, ni cuánta agua se lleva. El acuífero que
    alimenta un río puede estar aguas arriba y no justo debajo de la estación. Los datos vienen de la evaluación
    que España envió a la Unión Europea en 2022, hecha con datos de 2018 y 2019.</p>

    <h3>Límites</h3>
    <ul>
      <li>Los datos del SAIH son provisionales: la confederación los revisa y publica los definitivos en el anuario
      de aforos meses después. Un día por debajo aquí es un indicio, no una infracción; calificarlo corresponde a
      la confederación.</li>
      <li>Se aplica siempre el régimen ordinario. En sequía prolongada declarada el plan permite un mínimo menor
      fuera de los espacios protegidos; aún no se cruza con las declaraciones de sequía.</li>
      <li>El plan mide el cumplimiento en conjunto por meses y años, no día a día; esta página enseña el detalle
      diario.</li>
      <li>Las curvas que convierten nivel en caudal son menos precisas con poca agua, justo donde se mira. El
      margen del {TOLERANCE * 100:.0f} % lo amortigua, no lo elimina.</li>
    </ul>

    <h3 id="que-falta">Qué falta</h3>
    <ul>
      <li>Ebro: su SAIH exige registrarse para usar la API. Segura: su visor pide aceptar unas condiciones.
      Tajo, Duero y Miño-Sil: hace falta permiso de la confederación para reutilizar sus datos; en el Tajo,
      además, los mínimos suben por etapas hasta 2027.</li>
      <li>Los mínimos por masa del Guadalquivir y los de salida de embalse.</li>
      <li>Una calificación mensual como la del Ministerio, y el cruce con las declaraciones de sequía.</li>
      <li>Contrastar las medias con el anuario de aforos validado cuando se publique el del año 2025-26.</li>
      <li>El nivel de los acuíferos fuera del Júcar. El Ministerio publica la red piezométrica de todas las
      cuencas, pero su descarga pide superar una prueba antirrobots y su servidor de mapas falla. Cada
      confederación publica la suya por separado y en formatos distintos.</li>
      <li>Qué presa o qué toma concreta hay aguas arriba de cada punto (inventario de presas y Registro de
      Aguas).</li>
    </ul>
  </section>"""


def sources_html(links: dict[str, str]) -> str:
    return f"""<p>Caudales: <a href="{links["jucar"]}">SAIH Júcar</a>, Confederación Hidrográfica del Júcar;
  <a href="{links["guadiana"]}">SIRA</a>, Confederación Hidrográfica del Guadiana (perfil público del visor);
  <a href="{links["cantabrico"]}">SAIH Cantábrico</a>, Confederación Hidrográfica del Cantábrico;
  <a href="{links["guadalquivir"]}">SAIH Guadalquivir</a>, Confederación Hidrográfica del Guadalquivir. Sus avisos
  legales permiten reproducir los datos citando la fuente. Estaciones y masas del Cantábrico: servicios de mapas de
  la Confederación Hidrográfica del Cantábrico. Superficie de cuenca y códigos SAIH de los aforos:
  <a href="{CEDEX}">anuario de aforos del CEDEX</a> (edición 2021–2022; guardamos una copia en el
  repositorio porque su servidor no responde a las ejecuciones automáticas). Mínimos: <a href="{BOE}">Real Decreto 35/2023</a>, BOE.
  Presiones y estado de los acuíferos: planes hidrológicos 2022–2027 tal como España los envió a la Unión Europea,
  en los <a href="{EEA_WFD}">servicios WISE de la Agencia Europea de Medio Ambiente</a> (los mismos que publica el
  <a href="{MITECO_GW}">Ministerio</a>); reutilización libre citando la fuente. Niveles de los acuíferos del Júcar:
  <a href="{chj_piezometry.PAGE}">red piezométrica de la Confederación Hidrográfica del Júcar</a>.</p>"""
