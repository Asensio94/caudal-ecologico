"""The French page's explanation: where each threshold and flow comes from, what stays out, limits.

Like explain.py for Spain: whoever reads "sous le DCR" must see where the threshold comes
from, which gauge measures it and what the method cannot see, without opening the repository.
Counts come from the data, so the text cannot go stale.
"""
from __future__ import annotations

from datetime import date
from html import escape

from .config import TOLERANCE
from .i18n import long_date, n, p
from .plan_fr import DATASET_URL, RECENT_DAYS
from .sources import hubeau, vigieau, wise

LANG = "fr"
HUBEAU_DOC = "https://hubeau.eaufrance.fr/page/api-hydrometrie"
HYDROPORTAIL = "https://www.hydro.eaufrance.fr/"
SDAGE_AG = "https://eau-grandsudouest.fr/politique-eau/bassin/schema-directeur-amenagement-gestion-eaux-sdage"
SDAGE_DOC7 = "https://adour-garonne.eaufrance.fr/upload/DOC/SDAGE/SDAGE-2022-2027/"
VIGIEAU_DATA = "https://www.data.gouv.fr/fr/datasets/donnee-secheresse-vigieau/"
L214_18 = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047299352"
LICENCE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"


def _excluded(items: list[str]) -> str:
    if not items:
        return ""
    li = "\n".join(f"        <li>{escape(i)}</li>" for i in items)
    one = len(items) == 1
    return (f'\n      <details><summary>{len(items)} point{"" if one else "s"} du tableau '
            f'{"qui n’est pas comparé" if one else "qui ne sont pas comparés"}, et pourquoi</summary>\n'
            f'      <ul>\n{li}\n      </ul></details>')


def method_html(compared: int, excluded: list[str], first_level: date | None) -> str:
    total = compared + len(excluded)
    since = (f" Le niveau est relevé chaque matin depuis le {long_date(first_level, LANG)} ; VigiEau ne garde pas "
             "d’historique par point, donc il n’y a pas de niveau pour les jours antérieurs." if first_level else "")
    return f"""
  <section class="method" lang="fr">
    <h2>Comment c’est calculé</h2>
    <ol>
      <li><b>Le seuil vient du SDAGE.</b> Le <a href="{SDAGE_AG}">SDAGE Adour-Garonne 2022-2027</a> fixe, dans sa
      disposition C3, un réseau de points nodaux sur les principaux cours d’eau du bassin. À chacun il donne deux
      débits : le débit objectif d’étiage (DOE), visé en moyenne journalière pendant l’étiage et à respecter
      8 années sur 10, et le débit de crise (DCR), qui « doit impérativement être sauvegardé en valeur moyenne
      journalière ». Le programme télécharge le <a href="{DATASET_URL}">tableau C3 publié par l’agence de l’eau</a>
      (Licence Ouverte) et le lit tel quel, sans recopie à la main. C’est le DCR qui sert de seuil chaque jour.</li>
      <li><b>Chaque seuil, avec sa station.</b> Le tableau rattache chaque point nodal à une station hydrométrique
      (« Code Station Hydro1 ») et, quand celle-ci a été déplacée ou remplacée, à une seconde (« Hydro2 »). On lit la
      première des deux qui a publié un débit sur Hub’Eau au cours des {RECENT_DAYS} derniers jours. Résultat :
      {n(compared, LANG)} des {n(total, LANG)} points du tableau sont comparés.{_excluded(excluded)}</li>
      <li><b>Le débit vient de Hub’Eau.</b> L’<a href="{HUBEAU_DOC}">API hydrométrie de Hub’Eau</a> diffuse le débit
      moyen journalier (QmnJ) que calculent les producteurs (DREAL, services de prévision des crues) à partir de leurs
      propres mesures ; il est pris tel quel. Chaque valeur porte un statut : brute, corrigée, pré-validée ou validée.
      Seule la dernière est définitive ; les autres sont présentées comme provisoires. Comme les valeurs sont encore
      corrigées pendant des semaines, les {hubeau.REFRESH_DAYS} derniers jours sont relus chaque matin.</li>
      <li><b>On compare.</b> Un jour est « sous le DCR » si son débit moyen est inférieur de plus de
      {p(TOLERANCE, LANG)} au DCR. Cette marge absorbe l’erreur de mesure, plus grande quand la rivière est basse.
      Plusieurs jours de suite sous le DCR forment un épisode ; un jour sans donnée au milieu ne l’interrompt pas.
      Tant que la donnée n’est pas validée, la page dit « sous le DCR selon des données provisoires », jamais
      « manquement ».</li>
      <li><b>Le DOE, à côté.</b> Le DOE est affiché pour situer le débit, mais il n’est pas comparé jour par jour :
      le SDAGE l’évalue sur la saison et sur plusieurs années (8 sur 10). Un jour sous le DOE n’est donc pas un
      manquement. Pour trois points, le tableau donne deux valeurs (« 17/13 ») ; elles sont recopiées telles quelles.</li>
      <li><b>Les restrictions, en contexte.</b> Quand les rivières baissent, les préfets placent les zones d’alerte
      en vigilance, alerte, alerte renforcée ou crise par arrêté. Pour chaque station, on demande à
      <a href="{vigieau.SITE}">VigiEau</a> la zone d’eaux superficielles où elle se trouve et le niveau de l’arrêté en
      vigueur. Ces restrictions ne modifient pas le DCR : elles montrent ce que l’État a décidé pendant que la rivière
      était basse.{since}</li>
    </ol>
    <table class="params">
      <tr><th>Paramètre</th><th class="num">Valeur</th></tr>
      <tr><td>Marge pour l’erreur de mesure</td><td class="num">{p(TOLERANCE, LANG)}</td></tr>
      <tr><td>Jours sans donnée dans un épisode qui ne l’interrompent pas</td><td class="num">1</td></tr>
      <tr><td>Jours relus chaque matin sur Hub’Eau</td><td class="num">{hubeau.REFRESH_DAYS}</td></tr>
      <tr><td>Ancienneté maximale d’une donnée pour retenir une station</td><td class="num">{RECENT_DAYS} jours</td></tr>
    </table>

    <h2>Ce qui reste en dehors, et pourquoi</h2>
    <ul>
      <li><b>Le débit réservé des ouvrages.</b> L’<a href="{L214_18}">article L214-18 du code de l’environnement</a>
      impose à chaque barrage ou seuil de laisser passer un débit minimal (en général au moins un dixième du module).
      Mais la valeur fixée pour chaque ouvrage figure dans son arrêté d’autorisation, et aucun registre ouvert ne la
      donne : le référentiel des obstacles à l’écoulement (ROE) recense les ouvrages, pas leur débit réservé. Le
      programme ne l’estime pas à partir du module : un seuil inventé ne vaudrait rien.</li>
      <li><b>Loire-Bretagne et Rhône-Méditerranée.</b> Leurs SDAGE fixent aussi des DOE et des DCR, mais dans des
      tableaux en PDF qui nomment les points sans le code de la station. Les rattacher demande un travail point par
      point ; c’est la prochaine étape.</li>
      <li><b>Seine-Normandie et Rhin-Meuse.</b> Les points nodaux sont publiés en données ouvertes, mais sans les
      valeurs de débit : il n’y a rien à comparer.</li>
      <li><b>Artois-Picardie, Corse et outre-mer.</b> Pas encore examinés.</li>
      <li><b>Les débits objectifs des SAGE.</b> Dans les petits bassins sans DOE, les SAGE peuvent fixer leurs propres
      débits objectifs ; ils ne sont pas réunis dans un fichier ouvert.</li>
    </ul>

    <h2>Limites</h2>
    <ul>
      <li>La plupart des débits du jour sont provisoires et peuvent changer, parfois beaucoup, à la validation.</li>
      <li>Aux bas débits, les courbes de tarage sont les moins sûres : un écart de quelques pour cent n’est pas
      significatif, d’où la marge de {p(TOLERANCE, LANG)}.</li>
      <li>Sur les axes réalimentés (Garonne, Neste, Lot…), le débit dépend des lâchers des retenues de soutien
      d’étiage : un débit au-dessus du DCR peut être en partie artificiel, et un débit en dessous peut tenir à la
      gestion de ces lâchers plus qu’à la seule sécheresse.</li>
      <li>La zone VigiEau est celle qui contient le point de la station. Près d’une limite entre zones, la rivière peut
      relever de la zone voisine.</li>
      <li>Les pressions affichées sous certains points viennent de l’état des lieux que la France a transmis à
      l’Union européenne (<a href="{wise.VIEWER}">WISE</a>) ; elles décrivent la masse d’eau, pas la cause d’un jour
      donné.</li>
    </ul>
  </section>"""


def sources_html() -> str:
    return f"""<p lang="fr">Débits : <a href="{HUBEAU_DOC}">Hub’Eau, API hydrométrie</a> (données de l’<a
  href="{HYDROPORTAIL}">HydroPortail</a>, producteurs : DREAL et services de prévision des crues). Seuils DOE et DCR :
  <a href="{DATASET_URL}">tableau C3 du SDAGE Adour-Garonne 2022-2027</a>, agence de l’eau Adour-Garonne ; méthode
  détaillée dans le <a href="{SDAGE_DOC7}">document d’accompagnement nº 7</a>. Restrictions : <a
  href="{vigieau.SITE}">VigiEau</a> et <a href="{VIGIEAU_DATA}">données sécheresse VigiEau</a>, ministère de la
  Transition écologique. Pressions : <a href="{wise.VIEWER}">WISE, Agence européenne pour l’environnement</a>. Toutes
  ces données sont réutilisables sous la <a href="{LICENCE}">Licence Ouverte</a> ou en citant la source.</p>"""
