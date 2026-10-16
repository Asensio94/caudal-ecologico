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
from .plan_fr import BASIN, DATASET_URL, LB, LB_PDF, RECENT_DAYS, RM, RM_PDF
from .sources import hubeau, vigieau, wise

LANG = "fr"
HUBEAU_DOC = "https://hubeau.eaufrance.fr/page/api-hydrometrie"
HYDROPORTAIL = "https://www.hydro.eaufrance.fr/"
SDAGE_AG = "https://eau-grandsudouest.fr/politique-eau/bassin/schema-directeur-amenagement-gestion-eaux-sdage"
LB_QGIS = ("https://donnees-documents.eau-loire-bretagne.fr/home/donnees/"
           "sdage-2022-2027--projet-cartographique-qgis.html")
TRANSCRIPTIONS = "https://github.com/Asensio94/caudal-ecologico/tree/main/data/sdage"
BASIN_NAMES = {BASIN: "Adour-Garonne", LB: "Loire-Bretagne", RM: "Rhône-Méditerranée"}
SDAGE_DOC7 = "https://adour-garonne.eaufrance.fr/upload/DOC/SDAGE/SDAGE-2022-2027/"
VIGIEAU_DATA = "https://www.data.gouv.fr/fr/datasets/donnee-secheresse-vigieau/"
L214_18 = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047299352"
LICENCE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"


def _excluded(items: list[str], basin: str) -> str:
    if not items:
        return ""
    li = "\n".join(f"        <li>{escape(i)}</li>" for i in items)
    one = len(items) == 1
    return (f'\n      <details><summary>{BASIN_NAMES[basin]} : {len(items)} point{"" if one else "s"} du tableau '
            f'{"qui n’est pas comparé" if one else "qui ne sont pas comparés"}, et pourquoi</summary>\n'
            f'      <ul>\n{li}\n      </ul></details>')


def _count(basin: str, compared: dict[str, int], excluded: dict[str, list[str]]) -> str:
    k = compared.get(basin, 0)
    return f"{n(k, LANG)} des {n(k + len(excluded.get(basin, [])), LANG)} points"


def method_html(compared: dict[str, int], excluded: dict[str, list[str]], first_level: date | None) -> str:
    """`compared` and `excluded` are keyed by basin slug: points compared, and why the rest are not."""
    since = (f" Le niveau est relevé chaque matin depuis le {long_date(first_level, LANG)} ; VigiEau ne garde pas "
             "d’historique par point, donc il n’y a pas de niveau pour les jours antérieurs." if first_level else "")
    out = "".join(_excluded(excluded.get(b, []), b) for b in BASIN_NAMES)
    return f"""
  <section class="method" lang="fr">
    <h2>Comment c’est calculé</h2>
    <ol>
      <li><b>Le seuil vient du SDAGE.</b> Chaque bassin a son schéma directeur (SDAGE 2022-2027), qui fixe un réseau
      de points nodaux sur les principaux cours d’eau. À chacun il donne un débit objectif d’étiage (DOE), visé
      pendant l’étiage et à respecter 8 années sur 10, et un débit de crise (DCR), le débit en dessous duquel l’eau
      potable et la survie des espèces sont en jeu. C’est le DCR qui sert de seuil chaque jour, dans trois bassins :
      <ul>
        <li><b>Adour-Garonne</b> (disposition C3) : le DCR « doit impérativement être sauvegardé en valeur moyenne
        journalière ». Le programme télécharge le <a href="{DATASET_URL}">tableau C3 publié par l’agence de
        l’eau</a> (Licence Ouverte) et le lit tel quel, sans recopie à la main.</li>
        <li><b>Loire-Bretagne</b> (chapitre 7) : le <a href="{LB_PDF}">SDAGE</a> donne, pour chaque point nodal, le
        DOE, un débit seuil d’alerte (DSA) et le DCR ; la disposition 7E-1 fonde les restrictions sur le DSA et le
        DCR. Le tableau n’existe qu’en PDF : il est <a href="{TRANSCRIPTIONS}">recopié dans le dépôt</a>, chaque
        valeur vérifiée contre le texte du PDF, avec la page d’où elle vient.</li>
        <li><b>Rhône-Méditerranée</b> (disposition 7-07, tableau 7C) : même méthode, à partir du <a
        href="{RM_PDF}">SDAGE en PDF</a>. Ce SDAGE définit le DCR « en valeur journalière associée à une durée
        maximum de franchissement », mais le tableau ne donne pas cette durée : chaque jour sous le DCR est compté,
        alors qu’un épisode plus court que la durée admise ne contrevient peut-être pas au SDAGE. Les valeurs
        marquées d’un astérisque peuvent être révisées pendant le cycle ; la page le signale.</li>
      </ul></li>
      <li><b>Chaque seuil, avec sa station.</b> En Adour-Garonne, le tableau rattache chaque point à une station
      hydrométrique et, quand elle a été déplacée ou remplacée, à une seconde ; on lit la première des deux qui a
      publié un débit sur Hub’Eau au cours des {RECENT_DAYS} derniers jours. En Loire-Bretagne, la <a
      href="{LB_QGIS}">couche des points nodaux de l’agence</a> donne le code de la station, et en
      Rhône-Méditerranée le tableau donne seulement la rivière et le lieu. Dans ces deux bassins, la station retenue
      est celle de Hub’Eau qui porte le nom qu’écrit le SDAGE ; quand le code de l’agence désigne une autre station,
      c’est le nom du SDAGE qui l’emporte. Un point dont la station est douteuse (plusieurs stations du même nom,
      station « à réimplanter », station loin du lieu indiqué) n’est pas comparé : mieux vaut un point de moins
      qu’un seuil lu au mauvais endroit. Résultat : {_count(BASIN, compared, excluded)} en Adour-Garonne,
      {_count(LB, compared, excluded)} en Loire-Bretagne et {_count(RM, compared, excluded)} en
      Rhône-Méditerranée.{out}</li>
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
      <li><b>Le DOE et le DSA, à côté.</b> Le DOE est affiché pour situer le débit, mais il n’est pas comparé jour par
      jour : le SDAGE l’évalue sur la saison et sur plusieurs années (8 sur 10). Un jour sous le DOE n’est donc pas un
      manquement. En Loire-Bretagne, le DSA est affiché aussi : c’est le débit à partir duquel le préfet prend les
      premières restrictions. Quand le tableau donne deux valeurs (« 17/13 »), elles sont recopiées telles quelles.</li>
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
      <li><b>Les points sans DCR chiffré ou sans station sûre.</b> En Rhône-Méditerranée surtout, beaucoup de points du
      tableau 7C ont un DCR « à définir » ; d’autres n’ont pas de station qui publie sur Hub’Eau ou en ont plusieurs
      du même nom. La liste de chaque bassin, avec la raison, est dans l’étape 2 ci-dessus.</li>
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
      <li>Sur les axes réalimentés (Garonne, Neste, Lot, Loire, Allier, Durance, Verdon…), le débit dépend des lâchers des retenues de soutien
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
  <a href="{DATASET_URL}">tableau C3 du SDAGE Adour-Garonne 2022-2027</a>, agence de l’eau Adour-Garonne (méthode
  détaillée dans le <a href="{SDAGE_DOC7}">document d’accompagnement nº 7</a>) ; <a href="{LB_PDF}">SDAGE
  Loire-Bretagne 2022-2027</a>, chapitre 7, et <a href="{LB_QGIS}">couche des points nodaux</a>, agence de l’eau
  Loire-Bretagne ; <a href="{RM_PDF}">SDAGE Rhône-Méditerranée 2022-2027</a>, tableau 7C, agence de l’eau
  Rhône Méditerranée Corse ; tableaux en PDF <a href="{TRANSCRIPTIONS}">recopiés dans le dépôt</a>. Restrictions : <a
  href="{vigieau.SITE}">VigiEau</a> et <a href="{VIGIEAU_DATA}">données sécheresse VigiEau</a>, ministère de la
  Transition écologique. Pressions : <a href="{wise.VIEWER}">WISE, Agence européenne pour l’environnement</a>. Toutes
  ces données sont réutilisables sous la <a href="{LICENCE}">Licence Ouverte</a> ou en citant la source.</p>"""
