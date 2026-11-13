# mobile-money-audit

[Français](#français) | [English](#english)

## Français

Je développe des apps PHP (Laravel et PHP natif) et Flutter à Dakar. Quand j'ai intégré mes premiers paiements mobile money, j'ai cherché un outil pour relire mon code avant la mise en ligne. Il existe de bons audits PHP et Laravel, mais aucun ne connaît Wave, PayTech, Bictorys ou PayDunya, ni les pièges propres au XOF. J'ai donc écrit ce skill.

Vous le lancez depuis votre agent IA (Claude Code, Cursor, Codex...) dans votre projet. Il fonctionne avec Laravel comme avec du PHP natif (routeur maison, `curl`, scripts cron, fichiers SQL). Il lit le code qui gère vos paiements, ne modifie rien, et vous dit si vous pouvez passer en prod.

### À quoi ressemble le résultat

```
NO-GO — 2 bloquants

1. [Bloquant] Le webhook Wave est traité sans vérifier la signature Wave-Signature.
   N'importe qui peut envoyer une fausse notification de paiement.
   -> Vérifier le HMAC-SHA256 sur le corps brut avec hash_equals, refuser au-delà de 5 min.
   (app/Http/Controllers/WaveWebhookController.php:18)

2. [Bloquant] La page de succès marque la commande comme payée.
   -> Ne faire qu'afficher le statut ; seul le webhook ou l'API de statut valide.
   (app/Http/Controllers/PaymentController.php:74)

3. [Important] Aucune tâche planifiée ne relance les paiements restés « en attente ».
   ...

À confirmer manuellement
- Le webhook est bien enregistré en mode live dans le tableau de bord.
- ...
```

(Exemple fictif, pour montrer le format.)

### Ce qu'il cherche

Les erreurs qui coûtent vraiment de l'argent, en premier :

- **Les fausses notifications.** Si votre webhook ou votre IPN ne vérifie pas la signature ou le secret du prestataire, quelqu'un peut appeler cette URL et faire passer une commande pour payée.
- **Les doublons.** Les prestataires renvoient parfois la même notification plusieurs fois. Sans contrainte unique ou verrou en base, le client est crédité deux fois.
- **Le montant venu du client.** Le prix doit être recalculé côté serveur et comparé à ce qui a été payé. Un champ caché dans un formulaire ne suffit pas.
- **La page de succès qui valide le paiement.** Elle n'est qu'une redirection : n'importe qui peut l'ouvrir.
- **Le `* 100` hérité de Stripe.** Le XOF n'a pas de centimes. 5000 F se transmettent 5000, et on évite les float.
- **Le webhook perdu.** Si personne ne revérifie les paiements restés en attente, un client qui a payé peut ne jamais recevoir ce qu'il a acheté.

Et tout ce qu'on oublie la veille d'un lancement : les clés de test ou une URL ngrok restées en prod, un secret commité dans git, la route webhook bloquée par le CSRF (ou au contraire tout le site exclu du CSRF), la vérification SSL désactivée, des clés dans les logs, des appels API sans timeout.

Pour Bictorys, Wave, PayTech et PayDunya, le skill s'appuie sur une fiche par prestataire : nom de l'en-tête de signature, algorithme, statuts, URL de sandbox et de prod. Chaque information vient de la documentation officielle, avec le lien et la date de vérification. Quand la doc ne dit rien, la fiche l'écrit plutôt que de deviner.

Pour un autre prestataire, les vérifications générales s'appliquent quand même, et le rapport vous dit quoi aller vérifier dans sa doc. Orange Money en intégration directe n'est pas couvert, faute de documentation technique publique.

Le skill ne touche jamais à vos fichiers, n'appelle aucune API de paiement, et quand il trouve une clé il donne seulement l'endroit et un début masqué (`9f3a****`).

### Installation

Avec Claude Code :

```bash
claude plugin marketplace add youkc/mobile-money-audit
```

```bash
claude plugin install mobile-money-audit@mobile-money-audit
```

Avec un autre agent (Cursor, Codex...), via la CLI [skills](https://github.com/vercel-labs/skills) :

```bash
npx skills add youkc/mobile-money-audit
```

Ensuite, dans votre projet : « Audite mon intégration mobile money avant la prod ». Il répond dans la langue de votre question.

### Garder les fiches à jour

Les prestataires changent leur doc sans prévenir, et une fiche périmée donne une fausse impression de sécurité. Chaque lundi, une GitHub Action télécharge les pages de doc listées dans `watch/docs.json`, compare leur texte avec la version précédente et ouvre une issue s'il y a une différence. Je relis alors le changement et je mets la fiche à jour à la main. Il n'y a pas d'IA dans cette boucle.

De son côté, le skill vous prévient si la fiche qu'il utilise a plus de six mois.

Les tests du script de veille : `python3 watch/test_check.py`.

### Ce qu'il ne fait pas

C'est une relecture du code. Il ne voit ni votre tableau de bord chez le prestataire, ni votre serveur, ni le trafic réel. Un GO veut dire qu'il n'a pas trouvé de problème dans le code, pas que votre application est certifiée sûre.

### Contribuer

Vous avez repéré une erreur dans une fiche, ou vous voulez ajouter un prestataire ? Ouvrez une issue ou une pull request avec le lien vers la doc officielle qui justifie le changement. Une information sans source ne sera pas intégrée.

Licence MIT.

## English

I build PHP (Laravel and plain PHP) and Flutter apps in Dakar. When I wired up my first mobile money payments, I looked for something to review that code before going live. There are good PHP and Laravel audits out there, but none of them know Wave, PayTech, Bictorys or PayDunya, or the traps that come with XOF. So I wrote this skill.

You run it from your AI agent (Claude Code, Cursor, Codex...) inside your project. It works with Laravel and with plain PHP (custom router, `curl`, cron scripts, SQL files). It reads the code that handles your payments, changes nothing, and tells you whether you're ready for production.

### What you get

```
NO-GO - 2 blockers

1. [Blocker] The Wave webhook is processed without checking the Wave-Signature header.
   Anyone can send a fake payment notification.
   -> Verify the HMAC-SHA256 of the raw body with hash_equals, reject anything older than 5 min.
   (app/Http/Controllers/WaveWebhookController.php:18)

2. [Blocker] The success page marks the order as paid.
   -> Only display the status; only the webhook or the status API may validate.
   (app/Http/Controllers/PaymentController.php:74)

3. [Important] No scheduled task re-checks payments stuck in "pending".
   ...

To confirm manually
- The webhook is registered in live mode in the provider dashboard.
- ...
```

(Made-up example, to show the format.)

### What it looks for

The mistakes that actually lose money come first:

- **Fake notifications.** If your webhook or IPN doesn't check the provider's signature or secret, anyone can call that URL and mark an order as paid.
- **Duplicates.** Providers sometimes send the same notification more than once. Without a unique constraint or a lock, the customer gets credited twice.
- **Amounts coming from the client.** The price has to be computed on the server and compared with what was actually paid. A hidden form field won't do.
- **A success page that validates the payment.** It's just a redirect, and anyone can open it.
- **The `* 100` copied from Stripe code.** XOF has no cents: 5000 F is sent as 5000, and floats stay out of it.
- **The lost webhook.** If nothing re-checks payments stuck in pending, a customer who paid may never get what they bought.

Then everything that slips through the night before launch: test keys or an ngrok URL left in production, a secret committed to git, a webhook route blocked by CSRF (or the whole site excluded from it), SSL verification turned off, keys in the logs, API calls with no timeout.

For Bictorys, Wave, PayTech and PayDunya, the skill relies on one reference file per provider: signature header, algorithm, status names, sandbox and production URLs. Every fact comes from the official documentation, with the link and the date it was checked. When the docs are silent, the file says so instead of guessing.

For any other provider, the general checks still run, and the report tells you what to look up in that provider's docs. Direct Orange Money integration isn't covered, as its technical documentation isn't public.

The skill never touches your files, never calls a payment API, and when it finds a key it only shows where it is and a masked prefix (`9f3a****`).

### Install

With Claude Code:

```bash
claude plugin marketplace add youkc/mobile-money-audit
```

```bash
claude plugin install mobile-money-audit@mobile-money-audit
```

With another agent (Cursor, Codex...), through the [skills](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add youkc/mobile-money-audit
```

Then, in your project: "Audit my mobile money integration before production". It answers in the language you ask in.

### Keeping the references current

Providers change their docs without notice, and an outdated reference gives a false sense of safety. Every Monday, a GitHub Action downloads the doc pages listed in `watch/docs.json`, compares their text with the previous version, and opens an issue if anything changed. I then read the change and update the reference by hand. There's no AI in that loop.

On its side, the skill warns you when the reference it uses is more than six months old.

Tests for the watch script: `python3 watch/test_check.py`.

### What it doesn't do

It's a code review. It can't see your provider dashboard, your server or real traffic. A GO means it found no problem in the code, not that your app is certified secure.

### Contributing

Found a mistake in a reference, or want to add a provider? Open an issue or a pull request with a link to the official docs that back the change. Facts without a source won't be merged.

MIT license.
