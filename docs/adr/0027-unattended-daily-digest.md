# 0027 — Digest quotidien non surveillé + signal d'activation, avant le launch

**Date** : 2026-07-25 · **Statut** : Accepté · **Signé** : Adrien (demande), Claude Code (rédaction)

## Contexte

Demande utilisateur du 2026-07-25, à 4 jours du launch : identifier ce qui,
ajouté maintenant, rend le lancement plus facile ou la rétention meilleure.

Deux constats à l'origine de cet ADR.

**1. Le trou de rétention est l'exécution non surveillée.** La métrique nord
de `docs/GROWTH_PLAN_3M.md` §0 est « installations qui génèrent un digest
≥ 2 semaines d'affilée ». Or les deux seuls chemins existants pour un digest
*quotidien* supposent une machine allumée en permanence : la ligne de crontab
émise par `alfred schedule` (ADR 0007 §1), ou `alfred watch --loop` dans un
conteneur (ADR 0015). Un utilisateur qui teste sur un portable installe la
ligne cron, ferme le capot, et le digest s'arrête — l'habitude que la métrique
nord mesure ne se forme jamais. C'est un défaut de distribution, pas de calcul.

**2. Sans télémétrie, le launch n'a aucun signal d'activation.** Le paquet
n'émet rien (`GROWTH_PLAN_3M.md` §5, argument produit assumé), donc le nombre
de personnes ayant réellement *exécuté* Alfred le jour du launch est
inobservable. Les stars ne le disent pas. Le seul contournement honnête est
l'auto-déclaration, et elle n'existe nulle part dans le produit.

## Décisions

**1. Exception documentée au gel de features M1.** `GROWTH_PLAN_3M.md` §1.1
acte « aucune feature produit en M1 » et PLAN.md §9 pose « tout ajout
pré-launch = non par défaut ». Les deux ajouts ci-dessous sont classés
**polish d'entonnoir** — la catégorie que §1.1 autorise explicitement en M1 au
même titre que `uvx` et les messages d'erreur actionnables — et non features
produit : ni l'un ni l'autre ne change ce qu'Alfred calcule, ni la règle D5.
Le premier change la façon dont `watch` est *déclenché* ; le second ajoute une
ligne de texte à une sortie. C'est un jugement, pas une évidence : il est
tracé ici pour que la revue mensuelle puisse le contester.

**2. `alfred schedule --github-actions` : un workflow prêt à commiter.**
Même commande, seconde cible. Le workflow tourne sur une infrastructure qui ne
dort jamais, gratuite, que l'utilisateur possède déjà (son dépôt). Génération
de chaîne pure, comme `build_cron_line` — aucun processus d'ordonnancement,
aucune dépendance nouvelle, testable sans réseau.

**3. Chemins relatifs au dépôt, chemin absolu refusé.** `build_cron_line`
résout en absolu parce que cron s'exécute depuis un environnement nu. Un
runner GitHub, lui, checkout le dépôt à un chemin inconnu au moment de la
génération : le workflow doit rester relatif. Un `traces_dir` absolu lève
`ScheduleError` plutôt que d'émettre un workflow qui ne trouvera rien.

**4. Webhook depuis un secret, jamais en clair dans le fichier.**
`ALFRED_SLACK_WEBHOOK_URL` (`config.SLACK_WEBHOOK_ENV`) l'emporte déjà sur
`config.toml` — mécanisme acquis en ADR 0025 décision 7, rien à ajouter. Le
workflow mappe `${{ secrets.ALFRED_SLACK_WEBHOOK_URL }}` dans l'env de l'étape.
Le chemin d'un webhook *est* son credential : il ne doit jamais atterrir dans
un fichier commité.

**5. L'état entre deux runs est best-effort, et le fichier le dit.**
`.alfred/` est gitignoré et un runner est neuf à chaque exécution : sans rien,
`seen.json` (garantie de non-réémission) et `trace.db` (fenêtre de baseline,
ADR 0019) repartiraient vides tous les jours. Le workflow met `.alfred/` en
cache avec une clé roulante + `restore-keys`. Un cache GitHub est évincible
par conception : sur un miss, le digest du jour est recalculé et re-posté.
C'est une duplication de message, pas une perte de vérité — aucune
affirmation ne cesse d'être ancrée. Le compromis est écrit en commentaire en
tête du workflow généré plutôt que masqué.

**6. Config amorcée dans le runner.** `.alfred/config.toml` étant gitignoré,
un cache miss laisse le projet sans config et `watch` sortirait en erreur. Le
workflow écrit une config minimale (`mandate_path`, `trace_db_path`) si elle
est absente. Le `mandate.yaml`, lui, est commité par l'utilisateur : c'est sa
politique déclarée, elle a sa place dans le dépôt.

**7. Le cron GitHub est en UTC.** `--at 09:00` désigne 09:00 UTC dans le
workflow, alors que la ligne de crontab suit l'heure locale de l'hôte. Le
workflow généré le dit en commentaire — un digest décalé de deux heures est
exactement le genre de surprise qui fait désinstaller.

**8. `traces_dir` est échappé à l'écriture du YAML.** C'est du texte
utilisateur inséré dans un document YAML. Il est sérialisé via `json.dumps`
(les scalaires YAML entre guillemets doubles partagent l'échappement JSON —
le même procédé que le writer TOML de `config.py`). Cohérent avec la posture
d'échappement de l'ADR 0026.

**9. Signal d'activation par auto-déclaration.** `alfred demo` se termine par
une invitation à partager le digest obtenu, pointant vers un template d'issue
dédié. C'est la seule mesure d'activation compatible avec l'absence de
télémétrie, et elle produit en même temps la matière que la candidature YC
réclame (PLAN.md §7.2, « trois utilisateurs nommables »). Une ligne de texte,
aucune collecte : c'est l'utilisateur qui poste, ou non.

## Conséquences

- `alfred.schedule` gagne `build_github_actions_workflow` ; `build_cron_line`
  est inchangé, les deux partagent la validation d'heure.
- `alfred schedule` gagne le drapeau `--github-actions`.
- `alfred demo` gagne une ligne finale ; le digest lui-même est inchangé.
- Nouveau `.github/ISSUE_TEMPLATE/show_your_digest.md`.
- **Dépendance de calendrier** : le workflow généré fait
  `pip install alfred-ai`. Il n'est donc fonctionnel qu'une fois le paquet
  publié (ADR 0016, `docs/RELEASING.md`) — publication décidée par
  l'utilisateur comme dernière étape avant le launch.
- Le plan marketing est révisé en parallèle (viviers de sourcing, angle de
  launch, créneau du vendredi) — voir la note de révision dans PLAN.md §6 et
  `docs/GROWTH_PLAN_3M.md`. La section M2 de ce dernier planifiait des
  connecteurs livrés depuis (Briques 12 et 13, ADR 0014 et 0021) : elle est
  recalée sur ce qui reste à faire.
