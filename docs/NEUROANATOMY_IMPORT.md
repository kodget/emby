# Neuroanatomy import - 27 October 2026

All 17 source documents in `Anatomy/Third block/Neuro` are uploaded and rendered in the existing LASUCOM / INVICTUS class. They contain **465 pages**.

Open **Learn > Anatomy > Third block > Neuroanatomy** while signed into that class.

Verification exercised the reader API with a class-student profile, checked every page's private media registration and sequence, and fetched the first and last page image of each document. All 17 documents passed. These checks establish reading readiness; they do not claim that AI indexing, flashcards or question banks have finished.

## Documents

| Document | Pages |
| --- | ---: |
| Anatomy of Midbrain | 21 |
| 300L medical student lecture DIENCEPHALON | 45 |
| Anatomy of the Pons | 17 |
| Anatomy of Medulla Oblongata | 38 |
| Anatomy of the Spinal Cord | 33 |
| Basal Ganglia | 9 |
| CERBELLUM | 28 |
| CEREBRUM | 22 |
| Dural venous sinuses and blood supply of the brain | 80 |
| General sensory pathway | 15 |
| Hypothalamus | 16 |
| LASUCOM LECTURE: MOTOR PATHWAY | 32 |
| LIMBIC ONE.docx | 16 |
| LIMBIC THREE | 14 |
| Meninges | 13 |
| The Ventricular System | 56 |
| Visual Pathways | 10 |

The 47.8 MiB General sensory pathway PDF needed a 7.67 MiB upload copy to fit the storage provider's file limit. Its 15 pages and existing text were preserved; sampled text, diagrams and tables were visually checked. Original source files were not modified. LIMBIC THREE succeeded after retrying its initial Office conversion timeout.

Existing matching lecture records and complete rendered pages were reused. Missing subject/block/topic links were repaired. The existing Third block has the opaque ID `first-block`; links keep that ID to avoid breaking existing content. An older empty duplicate block was left untouched.

## Resume and verify

Run from `backend/`, using the production environment only when an actual class import is intended:

```powershell
../.venv/Scripts/python.exe -u manage.py import_slide_folder ../Anatomy --class-code 915085 --owner-email nexatage@gmail.com --state-dir ../.imports/anatomy --only 'Third block/Neuro' --apply --workers 2
../.venv/Scripts/python.exe -u manage.py verify_slide_import ../.imports/anatomy/manifest.json --owner-email nexatage@gmail.com --only 'Third block/Neuro' --media
```

Omitting `--apply` makes the importer a dry run. The local `.imports/anatomy/manifest.json` records source hashes, stable slide IDs and reader paths; `verification.json` records the latest checks. Preserve this state when resuming. It contains no API keys or signed URLs and is excluded from Git.

The remaining Anatomy folders have not been bulk-imported in this Neuroanatomy pass. Two Lower Limb pilot documents were imported earlier and remain available.
