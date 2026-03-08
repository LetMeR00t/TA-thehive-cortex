# Guide de Contribution - TA-thehive-cortex

## Architecture UCC
L'add-on utilise le framework UCC. Le fichier `globalConfig.json` est la source de vérité pour l'interface utilisateur et les entrées modulaires.

## Leçons Apprises (Migration v4.0.0)

### 1. Gestion des Modular Inputs
- **Logique métier** : Toute la logique de collecte doit résider dans `package/bin/input_module_<nom>.py`.
- **Wrappers** : Ne jamais créer manuellement les scripts d'enveloppe (`thehive_alerts_cases.py`, etc.) dans `package/bin/`. UCC les génère automatiquement dans `output/`. S'ils existent dans la source, ils peuvent causer des conflits ou des comportements inattendus.
- **Paramètres** : Assurez-vous que tous les paramètres définis dans `globalConfig.json` (ex: `max_size_value`, `fields_removal`) sont récupérés via `helper.get_arg('<nom>')` dans le script Python.

### 2. Nettoyage et Redondance
- **Dossiers binaires** : Éviter les dossiers en majuscules type `TA-thehive-cortex/` à l'intérieur de `bin/`. Préférer un package Python en minuscules (ex: `ta_thehive_cortex/`) et configurer `sys.path` dans un fichier de déclaration (ex: `ta_thehive_cortex_declare.py`).
- **Scripts inutiles** : Supprimer systématiquement les anciens scripts de la v3.9.0 qui ne suivent pas le pattern `input_module_*.py`.

### 3. Splunk AppInspect & Qualité
- **DATETIME_CONFIG** : Dans `props.conf`, ne jamais laisser `DATETIME_CONFIG` vide. Si Splunk doit gérer le temps automatiquement, il est préférable de supprimer la ligne plutôt que de la laisser vide, pour éviter un échec AppInspect.
- **Navigation (XML)** : UCC génère son propre `default.xml`. Si vous restaurez un fichier manuel, assurez-vous qu'il contient les entrées nécessaires pour les pages UCC (`configuration`, `inputs`, `dashboard`).
- **Verbose Build** : Toujours utiliser `ucc-gen build ... -v` pour identifier les fichiers en conflit lors de la génération.

### 4. Déploiement (Windows)
- Si des fichiers `.pyd` ou `.exe` sont verrouillés, il est nécessaire d'arrêter complètement Splunk ET de tuer les processus Python orphelins avant de tenter une copie de dossier.
