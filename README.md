# Veille tech automatisée (cyber / IT / pharma)

Agent de veille qui s'exécute sur GitHub Actions, sans dépendance à une infra
locale. Il collecte une quinzaine de flux RSS, filtre sur les dernières 24 h,
puis génère un digest synthétique en français via l'API Anthropic. Le rapport
est commité dans `reports/` et publié en artifact téléchargeable.

## Mise en place (5 minutes)

1. Créer un dépôt **privé** sur GitHub (ex. `veille-tech`).

2. Y déposer deux fichiers en respectant l'arborescence :
   ```
   veille.py
   .github/workflows/veille.yml
   ```
   (le fichier `veille.yml` fourni va dans le dossier `.github/workflows/`).

3. Ajouter la clé API en secret chiffré :
   `Settings` > `Secrets and variables` > `Actions` > `New repository secret`
   Nom : `ANTHROPIC_API_KEY` · Valeur : ta clé `sk-ant-...` (perso, pas Sanofi).

4. Onglet `Actions` : activer les workflows si demandé. Le job tourne ensuite
   chaque jour ouvré, et peut se lancer à la main via **Run workflow**.

## Récupérer le digest

Trois accès, au choix :
- dans le dépôt, dossier `reports/veille_AAAA-MM-JJ.md` (lisible depuis l'app
  mobile GitHub) ;
- en artifact téléchargeable depuis la page du run (rétention 30 jours) ;
- via une notification GitHub si tu actives le suivi du dépôt.

## Recevoir le digest par mail (optionnel)

Le workflow peut envoyer le digest **par e-mail** à chaque exécution (corps du
mail rendu en HTML + rapport `.md` en pièce jointe). L'étape ne s'active que si
le secret `MAIL_USERNAME` est présent ; sinon elle est ignorée, sans erreur.

Mise en place avec une boîte **Gmail** :

1. Activer la **validation en deux étapes** sur le compte Google (obligatoire
   pour générer un mot de passe d'application).
2. Créer un **mot de passe d'application** :
   `myaccount.google.com` > `Sécurité` > `Mots de passe des applications`.
   Google génère un code de 16 caractères.
3. Ajouter deux secrets (`Settings` > `Secrets and variables` > `Actions`) :
   - `MAIL_USERNAME` : ton adresse Gmail (sert aussi d'expéditeur **et** de
     destinataire) ;
   - `MAIL_PASSWORD` : le mot de passe d'application de 16 caractères.

Le prochain run enverra alors le digest dans ta boîte. Pour un **autre
destinataire** ou un **autre fournisseur SMTP** (Outlook, Brevo, etc.), ajuster
les champs `to`, `server_address` et `server_port` de l'étape « Envoyer le
digest par mail » dans `veille.yml`.

## Publier un flux RSS (optionnel)

À chaque run, `make_feed.py` régénère un flux **`docs/feed.xml`** (RSS 2.0, les
30 derniers digests, contenu complet) et une page **`docs/index.html`**. Pour
l'exposer publiquement via **GitHub Pages** :

1. `Settings` > `Pages` > **Source** : *Deploy from a branch*.
2. **Branch** : `claude/admiring-cori-m8qur1` · **Folder** : `/docs` > `Save`.
3. Après le déploiement, le flux est à :
   `https://<utilisateur>.github.io/veille-tech/feed.xml`

⚠️ **Disponibilité de Pages** : publier depuis un dépôt **privé** nécessite un
plan **Pro / Team / Enterprise**. Sur un compte **Free**, soit rendre le dépôt
**public** (le contenu de la veille n'est pas sensible — aucun secret n'y
figure), soit héberger le flux dans un dépôt public séparé. Dans tous les cas le
flux publié est **public**.

> Le nom d'hôte de Pages est en minuscules. Si tu changes de dépôt/compte,
> mets à jour `FEED_SITE_URL` dans l'étape « Construire le flux RSS » de
> `veille.yml`.

**Lire le flux depuis une autre boîte mail :**
- **Outlook** (bureau) : dossier *Flux RSS* > clic droit > *Ajouter un flux RSS*
  > coller l'URL `…/feed.xml`. Chaque digest arrive comme un message.
- **Gmail / autre** (pas de RSS natif) : utiliser un service *RSS-to-email*
  gratuit (Blogtrottr, Feedrabbit…) en y collant l'URL du flux.

## Réglages

- **Cadence** : modifier la ligne `cron` dans `veille.yml`. Attention, l'heure
  est en UTC et les runners peuvent démarrer avec quelques minutes de retard.
  Pour un bilan hebdomadaire, dupliquer le job avec `--hours 168` un cron du
  type `0 6 * * 1`.
- **Sources, mots-clés, modèle** : tout est en tête de `veille.py`.
- **Coût** : un run prend une à deux minutes. Le quota gratuit GitHub Actions
  (2000 min/mois sur un compte Free) est très largement suffisant.

## Notes

- Les RSS de la FDA et de l'EMA bloquent les accès machine ; à suivre par
  newsletter ou Google Alerts ciblé.
- CISA répond de façon intermittente selon l'IP du runner ; le script ignore
  proprement un flux indisponible.
