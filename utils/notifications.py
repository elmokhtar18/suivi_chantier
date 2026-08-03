"""
Notifications de l'application — architecture prête, non activée pour la
partie "push serveur" (voir plus bas), comme demandé dans la mission PWA.

Deux familles bien distinctes :

1. **Notification immédiate côté client** (`utils.helpers.notification_client`,
   via `flash(..., notifier=True)`) : déclenchée directement en JavaScript
   pendant que l'utilisateur a l'application ouverte. Ne nécessite aucun
   serveur de push — c'est ce que ce module utilise pour "Nouvelle dépense
   enregistrée" et "Budget d'étape dépassé", puisque ces deux événements se
   produisent alors que l'utilisateur est justement en train d'utiliser l'app.

2. **Notification push serveur → téléphone, app fermée** (ex. un rappel de
   saisie envoyé le soir) : demande une infrastructure que ce module ne met
   PAS en œuvre, mais dont le terrain est déjà préparé :
   - table `push_subscriptions` (voir `database.py`, colonnes endpoint/p256dh/auth)
     pour stocker les abonnements Web Push des navigateurs ;
   - `static/sw.js` gère déjà les événements `push`/`notificationclick` ;
   - il manque : générer une paire de clés VAPID, installer `pywebpush`,
     enregistrer réellement l'abonnement du navigateur dans
     `push_subscriptions` (ce qui demande un composant Streamlit bidirectionnel
     ou un petit service HTTP à côté, Streamlit seul ne recevant pas de JSON
     depuis le JS), et un déclencheur planifié (ex. tâche cron) qui appelle
     `pywebpush.webpush(...)` pour chaque abonnement enregistré.
   `notifier_rappel_saisie()` ci-dessous reste donc un « stub » documenté :
   il ne fait rien tant que cette infrastructure n'est pas branchée.
"""

from database import database as db
from utils.helpers import flash


def notifier_nouvelle_depense(designation, montant_texte):
    """À appeler juste après un `db.add_depense(...)` réussi (voir
    `pages/01_🧾_Dépenses.py`). Affiche un toast + une notification navigateur
    immédiate si l'app est ouverte."""
    flash(
        f"Dépense « {designation} » enregistrée pour {montant_texte}.",
        notifier=True, titre_notification="Nouvelle dépense enregistrée",
    )


def verifier_budget_etape(etape_id):
    """À appeler après l'ajout/la modification d'une dépense liée à une étape :
    si le budget de cette étape vient d'être atteint ou dépassé, déclenche une
    notification (en plus du badge coloré déjà affiché sur la page Étapes).
    Ne fait rien si l'étape n'a pas de budget défini (`budget_alloue` = 0)."""
    if not etape_id:
        return
    for etape in db.get_couts_par_etape():
        if etape["id"] == etape_id and etape["pct_budget"] is not None and etape["pct_budget"] >= 100:
            flash(
                f"L'étape « {etape['nom']} » a atteint {etape['pct_budget']}% de son budget alloué.",
                icone="⚠️", notifier=True, titre_notification="Budget d'étape dépassé",
            )
            return


def notifier_rappel_saisie():
    """Stub : rappel périodique de saisie ("vous n'avez enregistré aucune
    dépense depuis N jours"). Non activé — nécessiterait un déclencheur
    planifié côté serveur et le push VAPID/pywebpush décrits en en-tête de ce
    module. Ne rien appeler pour l'instant : conservé comme point d'entrée
    documenté pour une implémentation future."""
    raise NotImplementedError(
        "Rappel de saisie non activé : nécessite l'infrastructure de push serveur "
        "décrite en en-tête de utils/notifications.py (VAPID, pywebpush, planificateur)."
    )
