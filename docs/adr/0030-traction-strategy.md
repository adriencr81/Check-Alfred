# 0030 — Stratégie de traction : cible, canal possédé, signal payant, actif composé

**Date** : 2026-07-26 · **Statut** : Accepté · **Signé** : Adrien (demande et
arbitrages), Claude Code (audit et rédaction)

## Contexte

Demande utilisateur du 2026-07-26 : « on a un plan pour le lancement, mais
est-ce qu'on a une vraie stratégie marketing ? », puis « créons une vraie
stratégie de traction pour que les gens installent le produit et le faire
connaître ».

Audit de PLAN.md §2, §6, §8-§10 et de `docs/GROWTH_PLAN_3M.md`. Le socle
stratégique **existe** et n'est pas un simple calendrier de canaux : le
positionnement différenciant (§2 et « Why not X »), la thèse que chaque contenu
doit ré-encoder avec une règle de preuve obligatoire (§6.1), un funnel dont le
goulot est nommé mois par mois, un backlog négatif assumé (§10), et le garde-fou
« un tir raté ne conclut rien » (§9). Quatre trous **structurels** — pas
tactiques — ont en revanche été identifiés.

**1. La cible et les canaux sont désaccordés.** La landing dit « for the person
accountable for it » et §2 oppose compte-rendu *manager* à observabilité
*développeur*. Or M1 vise exclusivement HN, r/AI_Agents, r/LocalLLaMA, les issues
de `langgraph`/`crewAI`, les awesome-lists et les PRs d'exemples : 100 % dev. Le
seul canal manager, le post LinkedIn FR, a été rétrogradé en « hors séquence,
sans objectif chiffré » (ADR 0027) sans remplacement. La thèse manager n'a donc
aujourd'hui **aucune distribution**.

**2. Aucun canal possédé.** Ni liste mail, ni télémétrie (exclue par choix
produit), ni Discord (exclu §10). Les 4 newsletters du lundi J+7 sont *les
audiences des autres*. Conséquence : passé le mardi du launch, personne ayant
montré de l'intérêt n'est recontactable, et le re-launch M3 que prévoit le
garde-fou §9 repartirait de zéro acquisition — ce qu'une assurance est justement
censée éviter.

**3. Le critère qui tranche n'est pas instrumenté.** §8 fait des « demandes de
payant spontanées » la ligne qui décide entre CDI premium, freelance-runway et
fondation. Or rien dans les trois mois de marketing n'est conçu pour en
susciter : l'open-core tient en une ligne en bas du README et de la landing, et
l'export dossier de preuve (le pont vers le payant, v0.4) démarre *après*
l'horizon. Le risque n'est pas marketing, il est décisionnel : conclure « pas
d'acheteurs, ne pas fonder » à partir d'une absence qu'on a soi-même organisée.

**4. Le seul actif composé arrive en dernier, et porte deux rôles.** Le
leaderboard mensuel de fiabilité est le seul contenu du plan qui rapporte sans
effort marginal, et le seul qui soit intéressant sans qu'Alfred soit déjà adopté.
Il est à J+120, derrière tout, *et* il sert d'angle au re-launch (§6.4 et §3.2 du
plan de croissance). Moteur de croissance et plan B sont deux rôles
incompatibles : si le launch rate, l'assurance n'existe que quatre mois plus
tard. Tout le reste de la cadence est linéaire — un post, un pic, retour à zéro.

## Décisions

**1. Dev-champion assumé.** Le développeur est l'utilisateur *et* le relais
interne. Tous les canaux restent dev — ils sont déjà là où le problème s'exprime
publiquement (§6.2) — et le vocabulaire manager reste dans le positionnement,
parce que c'est lui qui différencie Alfred de l'observabilité. Ce qu'on change :
on **outille le transfert** vers le décideur au lieu d'essayer de l'atteindre
directement. L'artefact de ce transfert existe déjà — le rapport HTML autonome et
partageable (ADR 0020). L'option « ouvrir un vrai canal manager » a été écartée
pour la même raison que l'ADR 0027 avait rétrogradé le LinkedIn FR : elle suppose
un réseau de décideurs qui n'existe pas, et un second moteur de contenu à
alimenter sur un budget déjà contraint à ~1 h/jour.

**2. Liste mail minimale comme canal possédé.** Une liste opt-in, annoncée sur la
landing et dans le README, alimentée par une édition par release plus le finding
mensuel — de la matière qui existe déjà au calendrier, pas un contenu de plus.
C'est le seul canal qui survit à un post HN raté, à un re-launch, et au transfert
du dépôt vers l'org `alfred-ai` (D3). L'option « GitHub Releases seules » a été
écartée : elle est gratuite mais on ne possède pas la liste, donc elle ne répare
pas le trou qu'elle est censée combler.

**3. Page « Alfred for teams » passive pour instrumenter le signal payant.** Une
page qui décrit l'étage closed-source **déjà annoncé** (verdicts formels,
politiques vérifiables, multi-agents, rétention, conformité) et invite à ouvrir
une demande qualifiée. Pas de prix, pas de date, pas de promesse. La capture est
GitHub-native — un template d'issue étiqueté `teams-inquiry`, calqué sur
`show_your_digest.md` — plutôt qu'une adresse mail : chaque demande est ainsi
datée, attribuable et **comptable**, et aucune adresse personnelle n'est exposée
sur une page publique. Une waitlist explicite annoncée dans les posts de launch a
été écartée : elle donnerait un signal plus rapide, mais transformerait un
lancement open-source en collecte de leads, ce qui se paie sur HN et Reddit.

**4. Édition zéro du leaderboard dès M2.** Une version minimale — 2-3 frameworks,
un mandat commun, données brutes committées et rejouables — est publiée en M2 au
lieu de M3. Le leaderboard cesse d'être un plan B qu'on découvrirait sous
pression : il devient un moteur qui tourne, et l'angle de re-launch est déjà rodé
le jour où le garde-fou §9 doit servir. Coût assumé : cela consomme la priorité
technique de M2, jusqu'ici « intégralement pilotée par les issues ». La règle de
priorité reste néanmoins intacte dans un cas — **la dette d'entonnoir signalée
par des inconnus pendant le launch passe devant**, parce qu'une friction
d'installation coûte des utilisateurs tant qu'elle dure.

**5. Le pointeur teams est imprimé par le CLI, jamais écrit dans le rapport.**
Sans lui, le motion dev-champion de la décision 1 s'arrête sur un fichier HTML
sans suite. La première intention était de l'ajouter au `<footer>` du rapport
partageable ; elle a été **abandonnée en cours d'exécution**. L'ADR 0020
décision 2 pose que ce fichier ne contient « aucune ressource externe (pas de
`<script>`, pas de `src=`, pas de CDN/police/`http`) », propriété verrouillée par
`test_render_html_is_a_self_contained_document`. Deux raisons de ne pas la
relâcher : ce fichier est décrit par l'ADR 0020 lui-même comme la preuve qu'on
forwarde « à un audit » — y injecter un appel à l'action éditeur change la nature
de l'artefact ; et le rapport reste ainsi archivable sans réserve, ce qui est un
argument produit plutôt qu'une contrainte subie.

`alfred report --html` imprime donc la ligne sur **stdout**, après les fichiers
écrits. C'est un meilleur ciblage, pas un repli : sous la décision 1, la personne
qu'on outille est le **développeur** — or c'est lui qui lance la commande, au
moment exact où il produit l'artefact à transmettre. Deux tests falsifiables :
la ligne apparaît sur stdout après les chemins écrits, et l'HTML ne contient ni
`teams` ni `http`. Le second est une **régression gardée** : il échouera le jour
où quelqu'un retentera l'idée du footer.

**6. Non-décision : `alfred demo` reste inchangé.** La tentation était d'y
ajouter l'invitation à s'abonner, le moment étant celui d'enthousiasme maximal.
Refusé : la sortie du démo porte déjà une demande (ADR 0027 décision 9,
`_SHOW_YOUR_DIGEST_URL`), et deux demandes au même instant se cannibalisent. Le
digest partagé est le seul proxy qui prouve une *exécution* (§0 du plan de
croissance) — il ne se dilue pas. Une demande par moment.

**7. La liste mail n'est pas de la télémétrie.** Garde-fou ajouté explicitement
au plan de croissance §5. Le paquet continue de n'émettre strictement rien ;
l'abonnement est un geste volontaire depuis une page web, hors du produit.
L'argument d'acquisition « vos traces restent chez vous » (angle r/LocalLLaMA)
n'est pas entamé, et il ne doit jamais le devenir par dérive du nouveau canal.

## Conséquences

- PLAN.md §6 gagne un **§6.0 « Stratégie de traction »** qui énonce ces décisions
  comme politique directrice, avant les principes §6.1. §6.4 est recalé (le
  leaderboard passe en M2, l'assurance re-launch est dissociée) et §8 gagne la
  source de la métrique qui tranche (label `teams-inquiry`) — un critère de
  décision sans compteur n'est pas mesurable.
- `docs/GROWTH_PLAN_3M.md` passe en **révision 1.2** : deux proxies hebdo
  ajoutés (abonnés liste, demandes `teams-inquiry`), M1 gagne les deux canaux
  dans son polish d'entonnoir, M2 gagne l'édition zéro du leaderboard, M3 porte
  l'édition n°2 et le re-launch sous un angle rodé.
- Nouveaux : `docs/site/teams.md` et `.github/ISSUE_TEMPLATE/teams_inquiry.md`.
  `mkdocs.yml` ajoute `teams.md` à la nav — la publication reste **opt-in fichier
  par fichier**, la règle `docs_dir = docs/site` posée par l'ADR 0029 est
  inchangée : ni ce document, ni la VCD, ni les autres ADR ne sont publiés.
- `src/alfred/cli.py` : `_cmd_report` imprime le pointeur teams après les
  fichiers écrits (`_TEAMS_URL`). `src/alfred/report/html.py` est **inchangé** —
  l'ADR 0020 décision 2 n'est ni amendée ni relâchée. Deux tests dans
  `tests/test_cli.py`, dont un qui garde le rapport contre toute réintroduction.
- **Action mainteneur** (comme le « Settings → Pages → Source = GitHub Actions »
  de l'ADR 0029) : choisir le fournisseur de liste (Buttondown, listmonk ou
  équivalent) et brancher l'URL du formulaire dans `docs/site/index.md`. Aucune
  URL n'est inventée ici — la landing porte la section, le formulaire s'y
  connecte. Tant que ce n'est pas fait, le canal possédé n'existe pas : c'est le
  seul item de cet ADR qui bloque une décision, et il est antérieur au launch.
- Ce qui n'est **pas** décidé ici : ni prix, ni packaging, ni date pour l'étage
  payant. La page teams qualifie une demande, elle ne vend pas. L'export dossier
  de preuve reste en v0.4, après l'horizon des trois mois.
