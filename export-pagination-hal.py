#!/usr/bin/env python
# coding: utf-8

# In[4]:


#!/usr/bin/env python3
"""
Export paginé de l'API HAL (INSMI) vers un fichier CSV unique.
L'API est limitée à 10 000 résultats par requête ; ce script itère
automatiquement jusqu'à avoir récupéré tous les dépôts.
"""

import csv
import io
import sys
import time
import requests

# Certains champs HAL (abstracts, mots-clés…) dépassent la limite par défaut
# de 131 072 caractères. On la pousse au maximum supporté par le système.
csv.field_size_limit(10_000_000)  # 10 Mo par champ, compatible Windows/Linux

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL = "https://api.archives-ouvertes.fr/search/INSMI/"
PAGE_SIZE = 10000          # maximum autorisé par l'API
OUTPUT_FILE = "hal_insmi_export.csv"
RETRY_MAX = 3               # nombre de tentatives en cas d'erreur réseau
RETRY_DELAY = 5             # secondes entre deux tentatives

FIELDS = ",".join([
    "uri_s", "halId_s", "docid", "docType_s", "docSubType_s",
    "submitType_s", "version_i", "licence_s", "fileMain_s", "fileAnnexes_s",
    "doiId_s", "pubmedId_s", "pubmedcentralId_s", "wosId_s", "arxivId_s",
    "biorxivId_s", "chemrxivId_s", "fr_domainAllCodeLabel_fs",
    "domainAllCode_s", "primaryDomain_s", "level0_domain_s",
    "level1_domain_s", "level2_domain_s", "level3_domain_s",
    "authFullName_s", "authFullNameIdHal_fs", "authFullNameIdFormPerson_fs",
    "authORCIDIdExt_s", "authIdRefIdExt_s", "authIdHasPrimaryStructure_fs",
    "authIdHasStructure_fs", "structHasAuthId_fs", "structName_s",
    "structType_s", "structValid_s", "structCountry_s",
    "deptStructIdName_fs", "deptStructAcronym_s", "deptStructRnsrIdExt_s",
    "deptStructIdrefIdExt_s", "deptStructRorIdExt_s", "deptStructCountry_s",
    "labStructIdName_fs", "labStructAcronym_s", "labStructRnsrIdExt_s",
    "labStructIdrefIdExt_s", "labStructRorIdExt_s", "labStructCountry_s",
    "rgrpLabStructIdName_fs", "rgrpLabStructAcronym_s",
    "rgrpLabStructRnsrIdExt_s", "rgrpLabStructIdrefIdExt_s",
    "rgrpLabStructRorIdExt_s", "rgrpLabStructCountry_s",
    "instStructIdName_fs", "instStructAcronym_s", "instStructRnsrIdExt_s",
    "instStructIdrefIdExt_s", "instStructRorIdExt_s", "instStructCountry_s",
    "rgrpInstStructIdName_fs", "rgrpInstStructAcronym_s",
    "rgrpInstStructIdrefIdExt_s", "rgrpInstStructRorIdExt_s",
    "rgrpInstStructCountry_s", "publicationDateY_i", "publicationDateM_i",
    "publicationDateD_i", "publicationDate_s", "producedDate_s",
    "submittedDate_s", "inPress_bool", "instance_s",
    "contributorFullName_s", "title_s", "subTitle_s", "abstract_s",
    "en_abstract_s", "fr_abstract_s", "keyword_s", "en_keyword_s",
    "fr_keyword_s", "language_s", "volume_s", "issue_s", "page_s",
    "researchData_s", "anrProjectTitle_s", "anrProjectAcronym_s",
    "anrProjectReference_s", "europeanProjectTitle_s",
    "europeanProjectAcronym_s", "europeanProjectCallId_s",
    "anses_funding_title_s", "anses_funding_acronym_s",
    "ademe_funding_title_s", "ademe_funding_call_reference_s", "funding_s",
    "popularLevel_s", "peerReviewing_s", "audience_s", "publisherLink_s",
    "comment_s", "localReference_s", "seeAlso_s", "irThesaurusName_s",
    "irThesaurusAcronym_s", "collCategoryCodeName_fs", "isbn_s",
    "publisher_s", "scientificEditor_s", "linkExtUrl_s", "linkExtId_s",
    "openAccess_bool", "citationFull_s", "selfArchiving_bool",
    "journalTitle_s", "journalPublisher_s", "journalIssn_s",
    "journalEissn_s", "journalSherpaColor_s", "journalSherpaPostPrint_s",
    "journalSherpaCondition_s", "conferenceTitle_s",
    "conferenceOrganizer_s", "conferenceStartDate_s",
    "conferenceEndDate_s", "city_s", "country_s", "proceedings_s",
    "source_s", "bookTitle_s", "publicationLocation_s",
    "authorityinstitution_s", "thesisSchool_s", "director_s", "nntId_s",
    "committee_s", "defenseDate_s", "description_s", "isDoublon_bool",
    "relatedData_s",
])

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_page(start: int) -> requests.Response:
    """Appelle l'API HAL pour une page donnée, avec retry automatique."""
    params = {
        "q":    "*",
        "wt":   "csv",
        "rows": PAGE_SIZE,
        "fl":   FIELDS,
        "sort": "docid asc",
        "start": start,
    }
    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=120)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            print(f"  ⚠ Tentative {attempt}/{RETRY_MAX} échouée : {exc}")
            if attempt < RETRY_MAX:
                time.sleep(RETRY_DELAY)
    print("✗ Abandon après plusieurs échecs.", file=sys.stderr)
    sys.exit(1)


def get_total_results() -> int:
    """Récupère le nombre total de dépôts via une requête JSON minimale."""
    params = {"q": "*", "wt": "json", "rows": 0}
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["response"]["numFound"]


# ── Programme principal ───────────────────────────────────────────────────────

def main() -> None:
    print("🔍 Récupération du nombre total de dépôts…")
    total = get_total_results()
    print(f"   → {total:,} dépôts trouvés au total.")

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE  # arrondi vers le haut
    print(f"   → {pages} page(s) de {PAGE_SIZE:,} résultats à télécharger.\n")

    header_written = False
    total_rows = 0

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as out_file:
        writer = None  # sera initialisé après la première page

        for page_num in range(pages):
            start = page_num * PAGE_SIZE
            print(f"📥 Page {page_num + 1}/{pages}  (start={start:,})…", end=" ", flush=True)

            resp = fetch_page(start)

            # Lire le CSV retourné par l'API
            text = resp.text
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)

            if not rows:
                print("vide, on passe.")
                continue

            api_header = rows[0]
            data_rows  = rows[1:]  # on exclut l'en-tête de chaque page

            # Écriture de l'en-tête une seule fois
            if not header_written:
                writer = csv.writer(out_file, lineterminator="\n")
                writer.writerow(api_header)
                header_written = True

            writer.writerows(data_rows)
            total_rows += len(data_rows)
            print(f"{len(data_rows):,} lignes écrites. (total : {total_rows:,})")

    print(f"\n✅ Export terminé : {total_rows:,} lignes → « {OUTPUT_FILE} »")


if __name__ == "__main__":
    main()


# In[ ]:




