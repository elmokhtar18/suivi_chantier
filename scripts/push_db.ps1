# Pousse database/suivi_chantier.db vers GitHub si son contenu a changé
# depuis le dernier commit. Ne fait rien (silencieusement) s'il n'y a aucun
# changement. Appelé quotidiennement par la tâche planifiée Windows
# "SuiviChantier_PushDB" (voir scripts/installer_push_auto.ps1).

$ErrorActionPreference = "Stop"
Set-Location "c:\Users\elmok\OneDrive\Bureau\Suivi_Chantier"

$logFile = "database\push_auto.log"
$horodatage = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    git add database/suivi_chantier.db

    git diff --cached --quiet -- database/suivi_chantier.db
    if ($LASTEXITCODE -eq 0) {
        Add-Content -Path $logFile -Value "$horodatage - aucun changement, rien à pousser."
        exit 0
    }

    git commit -m "Mise à jour automatique de la base ($horodatage)" | Out-Null
    git push | Out-Null
    Add-Content -Path $logFile -Value "$horodatage - poussé avec succès."
}
catch {
    Add-Content -Path $logFile -Value "$horodatage - ERREUR : $_"
}
