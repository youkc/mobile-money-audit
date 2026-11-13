# mobile-money-audit

[English](#english) | [Français](#français)

## English

An AI agent skill that audits, **read-only**, the mobile money payment code of a **Laravel** app before it goes to production, and returns a **GO / NO-GO** verdict with precise `file:line` fixes.

Built for apps that take payments in West Africa (XOF), where generic Laravel audits do not know the providers.

### What it checks

- Webhook / IPN authenticity (provider signature or secret, constant-time comparison with `hash_equals`, or server-side status check)
- Idempotency: the same notification twice credits once (unique constraint, lock or transaction)
- Amount and currency recomputed server-side and compared to the order, never read from the client
- XOF amounts are integers (no float, no `* 100` inherited from Stripe)
- Pending payments resolved later by a scheduled status check
- The success / return page never validates a payment
- Test vs live keys and sandbox vs production URLs; no ngrok / localhost in production
- Secrets in `.env`, not in code or git history; masked in the report
- Webhook route excluded from CSRF, and only that route
- HTTPS everywhere, TLS verification not disabled
- No secrets in logs; timeouts and API errors handled

Provider references (facts taken from each provider's official docs, with sources and a "Verified on" date): **Bictorys, Wave, PayTech, PayDunya**. For any other provider, the common checks run and the report lists what to verify in that provider's docs. Orange Money direct integration is not covered: its technical documentation is not public.

The skill never modifies your project, never calls a provider API, and never prints a secret in clear.

### Install

As a Claude Code plugin:

```bash
claude plugin marketplace add youkc/mobile-money-audit
```

```bash
claude plugin install mobile-money-audit@mobile-money-audit
```

Or as a plain skill for Claude Code, Cursor, Codex and other agents, with the open [skills](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add youkc/mobile-money-audit
```

### Use

In your Laravel project, ask your agent: "Audit my mobile money integration before production". The report starts with the verdict, for example `NO-GO - 2 blockers`, then lists findings as `[Blocker | Important | Minor] problem -> fix (file:line)`, then what to confirm manually (dashboard settings, webhook registered in live mode, scheduler running, etc.). It answers in the language you write in.

### Documentation watch

Provider details change. A weekly GitHub Actions workflow (`.github/workflows/doc-watch.yml`) downloads the pages listed in `watch/docs.json` with plain `curl`, extracts the text, compares it with the snapshot in `watch/state/`, and when something changed opens an issue with the diff and mentions the repository owner. No AI, no automatic change to the references: a human reads the diff and updates the reference file and its "Verified on" date. The skill itself warns when a reference is more than 6 months old.

Run the watch tests locally: `python3 watch/test_check.py`.

### Limits

Static review only: it cannot see your provider dashboard, your production server or real traffic. A GO is not a security certification. Provider docs are sometimes incomplete or inconsistent; when a fact is not documented, the reference says "not documented - to confirm" instead of guessing.

### Contributing

Corrections to the references are welcome, with the official URL that supports them. New provider references must follow the same format (sources, "Verified on" date, no undocumented facts).

License: MIT.

## Français

Un skill pour agent IA qui audite, **en lecture seule**, le code de paiement mobile money d'une app **Laravel** avant la mise en production, et rend un verdict **GO / NO-GO** avec des corrections précises `fichier:ligne`.

Pensé pour les apps qui encaissent en Afrique de l'Ouest (XOF), là où les audits Laravel génériques ne connaissent pas les prestataires.

### Ce qui est vérifié

- Authenticité du webhook / IPN (signature ou secret du prestataire, comparaison en temps constant avec `hash_equals`, ou contre-vérification via l'API de statut)
- Idempotence : la même notification reçue deux fois crédite une seule fois (contrainte unique, verrou ou transaction)
- Montant et devise recalculés côté serveur et comparés à la commande, jamais lus depuis le client
- Montants XOF entiers (pas de float, pas de `* 100` hérité de Stripe)
- Paiements « en attente » résolus plus tard par une vérification planifiée du statut
- La page de succès / retour ne valide jamais un paiement
- Clés test vs live et URL sandbox vs prod ; pas de ngrok / localhost en prod
- Secrets dans `.env`, pas dans le code ni dans l'historique git ; masqués dans le rapport
- Route webhook exclue du CSRF, et seulement elle
- HTTPS partout, vérification TLS non désactivée
- Pas de secrets dans les logs ; timeouts et erreurs d'API gérés

Fiches prestataires (faits tirés de la doc officielle de chaque prestataire, avec sources et date « Verified on ») : **Bictorys, Wave, PayTech, PayDunya**. Pour un autre prestataire, les vérifications communes s'appliquent et le rapport liste ce qu'il faut vérifier dans sa doc. L'intégration directe Orange Money n'est pas couverte : sa documentation technique n'est pas publique.

Le skill ne modifie jamais votre projet, n'appelle jamais l'API d'un prestataire et n'affiche jamais un secret en clair.

### Installation

Comme plugin Claude Code :

```bash
claude plugin marketplace add youkc/mobile-money-audit
```

```bash
claude plugin install mobile-money-audit@mobile-money-audit
```

Ou comme skill simple pour Claude Code, Cursor, Codex et d'autres agents, avec la CLI ouverte [skills](https://github.com/vercel-labs/skills) :

```bash
npx skills add youkc/mobile-money-audit
```

### Utilisation

Dans votre projet Laravel, demandez à votre agent : « Audite mon intégration mobile money avant la prod ». Le rapport commence par le verdict, par exemple `NO-GO — 2 bloquants`, puis liste les points sous la forme `[Bloquant | Important | Mineur] problème -> correction (fichier:ligne)`, puis ce qu'il faut confirmer à la main (réglages du tableau de bord, webhook enregistré en mode live, planificateur actif, etc.). Il répond dans votre langue.

### Veille des documentations

Les détails des prestataires changent. Un workflow GitHub Actions hebdomadaire (`.github/workflows/doc-watch.yml`) télécharge les pages listées dans `watch/docs.json` avec un simple `curl`, extrait le texte, le compare à l'instantané de `watch/state/`, et s'il y a un changement ouvre une issue avec le diff en mentionnant le propriétaire du dépôt. Pas d'IA, pas de modification automatique des fiches : un humain lit le diff et met à jour la fiche et sa date « Verified on ». Le skill signale lui-même une fiche vérifiée il y a plus de 6 mois.

Lancer les tests de la veille en local : `python3 watch/test_check.py`.

### Limites

Revue statique uniquement : elle ne voit ni votre tableau de bord prestataire, ni votre serveur de prod, ni le trafic réel. Un GO n'est pas une certification de sécurité. Les docs des prestataires sont parfois incomplètes ou contradictoires ; quand un point n'est pas documenté, la fiche écrit « not documented - to confirm » au lieu de deviner.

### Contribuer

Les corrections des fiches sont bienvenues, avec l'URL officielle qui les justifie. Toute nouvelle fiche suit le même format (sources, date « Verified on », aucun fait non documenté).

Licence : MIT.
