import type { Catalog } from "./runtime";

/**
 * French catalogue.
 *
 * Machine-produced from `en`, which stays the reference: every key it declares
 * has to be here, and `Catalog` makes a missing one a `tsc` error rather than a
 * raw key on screen. Product names (Reader, Mix, Audio-Heavy), platform names
 * and the app's own name are not translated.
 */
export const fr: Catalog = {
  "common.ok": "OK",
  "common.cancel": "Annuler",
  "common.retry": "Réessayer",
  "common.delete": "Supprimer",
  "common.save": "Enregistrer",
  "common.done": "Terminé",
  "common.close": "Fermer",
  "common.dismiss": "Fermer",
  "common.loading": "Chargement…",
  "common.continue": "Continuer",
  "common.back": "Retour",
  "common.error": "Erreur",
  "common.untitled": "Sans titre",
  "common.somethingWentWrong": "Une erreur est survenue",
  "common.itemCount.one": "{count} élément",
  "common.itemCount.other": "{count} éléments",
  "trial.badge": "Essai gratuit",
  "trial.lastDay": "Essai gratuit - dernier jour",
  "trial.daysLeft.one": "Essai gratuit - {count} jour restant",
  "trial.daysLeft.other": "Essai gratuit - {count} jours restants",
  "home.tile.a11yFolder": "Dossier {name}, {count}",
  "home.tile.a11yByCreator": "{title} par {creator}",
  "quota.warning.trial":
    "Vous avez utilisé {percent} % des minutes de votre essai gratuit.",
  "quota.warning.trialWithDate":
    "Vous avez utilisé {percent} % des minutes de votre essai gratuit. Elles ne se rechargent pas — votre essai se termine le {date}.",
  "quota.warning.monthly":
    "Vous avez utilisé {percent} % des minutes de ce mois-ci.",
  "quota.warning.monthlyWithDate":
    "Vous avez utilisé {percent} % des minutes de ce mois-ci. Elles se rechargent le {date}.",
  "quota.seePlans": "Voir les formules",
  "quota.dismissWarning": "Masquer l'alerte de minutes",
  "artifacts.sourceCount.one": "{count} source",
  "artifacts.sourceCount.other": "{count} sources",
  "artifacts.status.queued": "En attente",
  "artifacts.status.generating": "Génération…",
  "artifacts.status.failed": "Échec",
  "artifacts.status.generated": "Généré",
  "artifacts.history.a11yRow": "{type} : {title}",
  "mediaType.podcast": "PODCAST",
  "mediaType.article": "ARTICLE",
  "mediaType.video": "VIDÉO",
  "mediaType.short": "COURT",
  "mediaType.audio": "AUDIO",
  "mediaType.text": "TEXTE",
  "mediaType.document": "DOC",
  "mediaType.link": "LIEN",
  "mediaCard.a11yByCreator": "{title} par {creator}, {type}",
  "mediaCard.a11yFromDomain": "{title}, {type} de {domain}",
  "mediaCard.longPressHint":
    "Appuyez deux fois et maintenez pour déplacer, renommer ou supprimer cette source",
  "mediaActions.move.label": "Déplacer",
  "mediaActions.rename.label": "Renommer",
  "mediaActions.delete.label": "Supprimer",
  "mediaActions.moreA11y": "Actions pour cette source",
  "mediaActions.rename.title": "Renommer cette source",
  "mediaActions.rename.placeholder": "Nom de la source",
  "mediaActions.renameFailed":
    "Cette source n'a pas pu être renommée. Son nom n'a pas changé.",
  "mediaActions.deleteTitle": "Supprimer cette source ?",
  "mediaActions.deleteBody":
    "« {title} » sera retirée de votre bibliothèque. Cette action est irréversible.",
  "mediaActions.deleteFailed":
    "Cette source n'a pas pu être supprimée. Elle est toujours dans votre bibliothèque.",
  "folderActions.longPressHint":
    "Appuyez deux fois et maintenez pour renommer ou supprimer ce dossier",
  "folderActions.rename.label": "Renommer",
  "folderActions.delete.label": "Supprimer",
  "folderActions.moreA11y": "Actions pour ce dossier",
  "folderActions.rename.title": "Renommer ce dossier",
  "folderActions.rename.placeholder": "Nom du dossier",
  "folderActions.renameFailed":
    "Ce dossier n'a pas pu être renommé. Son nom n'a pas changé.",
  "folderActions.deleteTitle": "Supprimer ce dossier ?",
  "folderActions.deleteBody":
    "« {name} » sera supprimé. Toutes les sources qu'il contient passent dans {unsorted} — aucune n'est supprimée.",
  "folderActions.deleteSubfolders.one":
    "Son sous-dossier est également supprimé, et les sources qu'il contient passent aussi dans {unsorted}.",
  "folderActions.deleteSubfolders.other":
    "Ses {count} sous-dossiers sont également supprimés, et les sources qu'ils contiennent passent aussi dans {unsorted}.",
  "folderActions.deleteFailed":
    "Ce dossier n'a pas pu être supprimé. Il est toujours dans votre bibliothèque.",
  "addSource.title": "Ajouter à votre boîte de réception",
  "addSource.importFile.label": "Importer un fichier",
  "addSource.importFile.description":
    "Un PDF, un document Office, une image ou un fichier audio depuis votre téléphone.",
  "addSource.importPhoto.label": "Importer une photo",
  "addSource.importPhoto.description":
    "Choisissez une photo déjà présente dans votre galerie.",
  "auth.or": "ou",
  "auth.continueWithGoogle": "Continuer avec Google",
  "auth.signInWithApple": "Se connecter avec Apple",
  "auth.google.notCompleted":
    "La connexion Google n'a pas abouti. Veuillez réessayer.",
  "auth.google.noIdToken":
    "Impossible d'obtenir le jeton d'identification Google. Veuillez réessayer.",
  "auth.google.noGoogleAccount":
    "Aucun compte Google sur cet appareil. Ajoutez-en un dans les réglages de l'appareil, puis réessayez.",
  "auth.google.failed":
    "La connexion Google n'a pas pu aboutir. Veuillez réessayer.",
  "auth.apple.noIdentityToken":
    "Impossible d'obtenir le jeton d'identité Apple. Veuillez réessayer.",
  "artifacts.type.summaryShort": "Résumé",
  "artifacts.type.summaryDetailed": "Résumé détaillé",
  "artifacts.type.notes": "Notes de cours",
  "artifacts.type.flashcards": "Cartes mémo",
  "artifacts.type.quiz": "Quiz",
  "artifacts.generate": "Générer",
  "artifacts.a11yGenerate": "Générer {label}",
  "artifacts.processing": "Traitement…",
  "artifacts.panel.generateHeading": "Générer",
  "artifacts.panel.generatedHeading": "Généré",
  "artifacts.panel.retryA11y": "Réessayer de charger le contenu généré",
  "artifacts.panel.empty":
    "Rien de généré pour l'instant. Choisissez un format ci-dessus pour commencer.",
  "duration.minutes.one": "{count} min",
  "duration.minutes.other": "{count} min",
  "duration.hours.one": "{count} h",
  "duration.hours.other": "{count} h",
  "duration.hoursMinutes": "{hours} {minutes}",
  "time.justNow": "À l'instant",
  "time.minutesAgo.one": "il y a {count} min",
  "time.minutesAgo.other": "il y a {count} min",
  "time.hoursAgo.one": "il y a {count} h",
  "time.hoursAgo.other": "il y a {count} h",
  "time.yesterday": "Hier",
  "time.daysAgo.one": "il y a {count} j",
  "time.daysAgo.other": "il y a {count} j",
  "subscription.resetLabel.trialEnds": "FIN DE L'ESSAI",
  "subscription.resetLabel.resets": "RECHARGE",
  "subscription.resetLabel.ends": "FIN",
  "subscription.resetLabel.periodEnds": "FIN DE PÉRIODE",
  "subscription.status.paymentIssue": "Problème de paiement",
  "subscription.status.cancelled": "Résilié",
  "error.sessionExpired":
    "Votre session a expiré. Veuillez vous reconnecter.",
  "error.invalidCredentials":
    "E-mail ou mot de passe incorrect. Veuillez réessayer.",
  "error.emailNotVerified":
    "Veuillez vérifier votre adresse e-mail avant de vous connecter.",
  "error.emailAlreadyExists": "Un compte existe déjà avec cette adresse e-mail.",
  "error.invalidVerificationToken":
    "Lien de vérification invalide. Veuillez en demander un nouveau.",
  "error.userNotFound":
    "Aucun compte trouvé pour cette adresse e-mail. Vérifiez l'adresse ou créez un compte.",
  "error.notAuthorized":
    "Vous n'avez pas l'autorisation d'effectuer cette action.",
  "error.notFound": "Contenu introuvable. Essayez une autre recherche.",
  "error.mediaNotFound":
    "Ce média est introuvable ou n'est plus disponible.",
  "error.artifactNotFound":
    "Ce contenu généré est introuvable ou n'est plus disponible.",
  "error.invalidUrl": "Ce lien est invalide. Essayez une autre URL.",
  "error.unsupportedUrl":
    "Ce lien n'est pas encore pris en charge. Essayez une autre source.",
  "error.validation": "Veuillez remplir tous les champs obligatoires.",
  "error.rateLimited":
    "Trop de requêtes. Patientez un instant et réessayez.",
  "error.conflict":
    "Cette action entre en conflit avec des données existantes. Actualisez puis réessayez.",
  "error.badRequest": "Vérifiez votre saisie et réessayez.",
  "error.invalidEmail": "Veuillez saisir une adresse e-mail valide.",
  "error.passwordTooShort":
    "Le mot de passe doit contenir au moins 8 caractères.",
  "error.passwordsDoNotMatch":
    "Les mots de passe ne correspondent pas. Veuillez réessayer.",
  "error.network":
    "Erreur réseau. Vérifiez votre connexion et réessayez.",
  "error.timeout": "La requête a expiré. Veuillez réessayer.",
  "error.outOfMinutes":
    "Vous n'avez plus de minutes pour cette période. Passez à une formule supérieure pour continuer à importer de l'audio et de la vidéo.",
  "mediaError.mediaUnavailable": "Ce média n'est plus disponible à sa source.",
  "mediaError.geoRestricted": "Ce média n'est pas disponible dans la région depuis laquelle nous importons.",
  "mediaError.ageRestricted": "Ce média est protégé par une vérification d'âge que nous ne pouvons pas franchir.",
  "mediaError.liveContentUnsupported": "Le direct ne peut pas être importé. Réessayez une fois l'enregistrement publié.",
  "mediaError.imagePostUnsupported": "Cette publication est une photo : il n'y a rien à transcrire.",
  "mediaError.noTranscribableMedia": "Ce lien ne contient ni audio, ni vidéo, ni sous-titres exploitables.",
  "mediaError.noTranscriptAvailable": "Aucune transcription n'a pu être obtenue pour ce média.",
  "mediaError.postTextEmpty": "Cette publication ne contient aucun texte à enregistrer.",
  "mediaError.notAnArticlePage": "Ce lien ne mène pas à un article lisible.",
  "mediaError.articleTextNotFound": "Nous n'avons pas pu lire le texte de cet article.",
  "mediaError.documentParseFailed": "Ce document n'a pas pu être lu. Essayez un autre fichier ou un autre format.",
  "mediaError.providerUnavailable": "La source n'a pas pu être atteinte. Réessayez plus tard.",
  "mediaError.providerResultInvalid": "L'import est revenu inexploitable. Réessayez plus tard.",
  "mediaError.providerRateLimited": "La source nous limite pour le moment. Réessayez dans quelques minutes.",
  "mediaError.providerTimedOut": "L'import a pris trop de temps. Réessayez.",
  "mediaError.serviceUnavailable": "Les imports sont momentanément indisponibles. Nous nous en occupons.",
  "mediaError.itemTooLong": "Cet élément est plus long que ce que votre formule autorise en un seul import.",
  "mediaError.internal": "Un problème est survenu de notre côté. Réessayez d'importer cet élément.",

  "quota.title.outOfMinutes": "Plus de minutes",
  "quota.title.itemTooLong": "Trop long pour un seul import",
  "quota.refusal.noPlan":
    "Votre formule a pris fin. Abonnez-vous pour continuer à enregistrer dans votre bibliothèque.",
  "quota.refusal.outOfMinutes":
    "Vous n'avez plus de minutes pour cette période. Passez à une formule supérieure pour traiter ce contenu maintenant.",
  "quota.refusal.outOfMinutesUntil":
    "Vous n'avez plus de minutes jusqu'au {date}. Passez à une formule supérieure pour traiter ce contenu maintenant.",
  "quota.refusal.needsMore":
    "Cet import nécessite {needed} et il vous reste {remaining} jusqu'au {date}. Passez à une formule supérieure pour le traiter maintenant.",
  "quota.refusal.needsMoreNoDate":
    "Cet import nécessite {needed} et il vous reste {remaining}. Passez à une formule supérieure pour le traiter maintenant.",
  "quota.refusal.itemTooLong":
    "Ce contenu dure {duration}, au-delà des {max} qu'un import unique peut utiliser sur votre formule. Découpez-le en parties plus courtes.",
  "quota.refusal.itemTooLongGeneric":
    "C'est trop long pour un import unique sur votre formule. Découpez-le en parties plus courtes.",
  "artifacts.refusal.folderEmpty":
    "Ce dossier n'a encore aucune source avec transcription. Ajoutez des médias, ou attendez la fin du traitement de ceux que vous avez enregistrés.",
  "artifacts.refusal.mediaEmpty":
    "Cet élément n'a pas encore de transcription : il n'y a rien à générer.",
  "artifacts.refusal.tooManySources":
    "Ce dossier compte {count} sources, au-delà des {max} qu'une seule génération peut lire. Générez sur un sous-dossier plus petit.",
  "artifacts.refusal.tooMuchText":
    "Il y a trop de texte ici pour une seule génération. Générez sur un sous-dossier plus petit.",
  "artifacts.refusal.translationFailed":
    "Cette transcription n'a pas pu être traduite, et cela ne sera pas retenté automatiquement. Réessayez plus tard.",
  "artifacts.refusal.sourcesTranslationFailed.one":
    "La seule source ici n'a pas pu être traduite, et cela ne sera pas retenté automatiquement. Réessayez plus tard.",
  "artifacts.refusal.sourcesTranslationFailed.other":
    "Aucune de ces {count} sources n'a pu être traduite, et cela ne sera pas retenté automatiquement. Réessayez plus tard.",
  "artifacts.refusal.generic":
    "Impossible de lancer cette génération. Veuillez réessayer.",
  "plan.hourlyRate": "≈ {price} de l'heure",
  "plan.card.allowance": "{duration} par mois",
  "plan.card.perImport": "jusqu'à {duration} par envoi",
  "plan.rec.cappedLargest":
    "Vous avez utilisé les {duration} de cette période. {plan} est la formule la plus grande que nous proposons.",
  "plan.rec.cappedNextUp":
    "Vous avez utilisé les {duration} de cette période. {plan} est la taille au-dessus.",
  "plan.rec.overLargest":
    "Vous avez utilisé {duration} cette période — plus que ce qu'inclut n'importe quelle formule. {plan} est la plus grande que nous proposons.",
  "plan.rec.trialFloor":
    "Vous avez utilisé {duration} de votre essai jusqu'ici. {plan} vous garde sur la formule que vous utilisez déjà.",
  "plan.rec.covering":
    "Vous avez utilisé {duration} cette période. {plan} est la plus petite formule qui couvre cela.",
  "plan.badge.recommended": "RECOMMANDÉ POUR VOUS",
  "plan.badge.yourTrial": "VOTRE FORMULE D'ESSAI",
  "plan.badge.bestValue": "MEILLEUR PRIX",
  "paywall.reason.trialOut":
    "Les minutes de votre essai sont épuisées, et elles ne se rechargent pas. Choisissez une formule pour continuer à importer de l'audio et de la vidéo.",
  "paywall.reason.outNoDate":
    "Vous n'avez plus de minutes pour cette période. Une formule plus grande vous en donne davantage dès maintenant.",
  "paywall.reason.outWithDate":
    "Vous n'avez plus de minutes jusqu'au {date}. Une formule plus grande vous en donne davantage dès maintenant.",
  "paywall.reason.trialLow":
    "{left} restant dans votre essai, et les minutes d'essai ne se rechargent pas.",
  "paywall.reason.lowNoDate": "{left} restant sur cette période.",
  "paywall.reason.lowWithDate": "{left} restant jusqu'au {date}.",
  "plan.minutesRule":
    "Les minutes couvrent l'audio et la vidéo que vous envoyez. Les articles et les pages web n'en coûtent aucune, et lire votre bibliothèque est illimité.",
  "plan.list.separator": ", ",
  "plan.list.lastConjunction": "{list} et {last}",
  "plan.source.web": "Articles & pages web",
  "plan.source.audioUrl": "Tout lien audio",
  "plan.source.notes": "Notes",
  "plan.cost.free.label": "Articles, pages web, posts X",
  "plan.cost.captions.label": "Une vidéo YouTube, quelle que soit sa durée",
  "plan.cost.transcript.label": "Un podcast qui publie déjà son texte",
  "plan.cost.duration.label": "Audio, vidéo, reels, notes vocales",
  "plan.cost.document.label": "Un document ou la photo d'une page",
  "plan.cost.textFile.label": "Une note ou un fichier texte",
  "plan.cost.folder.label": "Une génération sur tout un dossier",
  "plan.cost.value.free": "Gratuit",
  "plan.cost.value.realLength": "Sa durée réelle",
  "plan.cost.value.perPages": "une minute par {pages} pages",
  "plan.cost.value.perSources": "une minute par {sources} éléments",
  "plan.trial.accessFull": "accès complet",
  "plan.trial.accessTier": "accès {tier}",
  "plan.trial.generic":
    "Votre essai gratuit est en cours : {access}, sans frais et sans rien à résilier.",
  "plan.trial.genericWithDate":
    "Votre essai gratuit est en cours : {access} jusqu'au {date}, sans frais et sans rien à résilier.",
  "plan.trial.days":
    "Votre essai gratuit de {days} jours est en cours : {access}, sans frais et sans rien à résilier.",
  "plan.trial.daysWithDate":
    "Votre essai gratuit de {days} jours est en cours : {access} jusqu'au {date}, sans frais et sans rien à résilier.",
  "account.plan.heading": "VOTRE FORMULE",
  "account.plan.checking": "Vérification de votre formule…",
  "account.plan.unavailable": "État de la formule indisponible",
  "account.plan.unavailableHint":
    "Nous n'avons pas pu charger les détails de votre abonnement. Votre formule elle-même n'est pas affectée.",
  "account.plan.retryA11y": "Réessayer de charger les détails de la formule",
  "account.plan.none": "Aucune formule active",
  "account.plan.noneHint":
    "Vos minutes et votre date de recharge apparaîtront ici dès qu'un abonnement sera actif.",
  "account.plan.freeTrial": "Essai gratuit",
  "account.plan.active": "Formule active",
  "account.plan.minutesLeft": "MINUTES RESTANTES",
  "account.plan.minutesLeftA11y":
    "{remaining} minutes restantes sur {included} pour cette période",
  "account.plan.unknownDate": "Inconnue",
  "account.plan.resetDateA11y": "{label} {date}",
  "account.plan.resetDateUnknownA11y": "Date de recharge inconnue",
  "account.plan.minutesRuleTrial":
    "{rule} Les minutes d'essai ne se rechargent pas.",
  "preview.heading": "Aperçu",
  "preview.pending": "L'aperçu est en cours de rédaction…",
  "preview.failed": "Pas d'aperçu pour cette source.",
  "transcript.heading": "Texte complet",
  "transcript.empty": "Aucun texte disponible pour l'instant.",
  "transcript.emptyHint":
    "Le texte apparaîtra une fois le traitement terminé.",
  "transcript.status.pending": "La préparation du texte va bientôt commencer.",
  "transcript.status.extracting": "Extraction du contenu audio…",
  "transcript.status.transcribing": "Conversion de l'audio en texte…",
  "transcript.status.ready": "Le texte est prêt.",
  "transcript.status.failed": "La préparation du texte a échoué.",
  "transcript.paragraphCount.one": "{count} paragraphe",
  "transcript.paragraphCount.other": "{count} paragraphes",
  "transcript.loading": "Chargement du texte…",
  "transcript.notAvailable":
    "Le texte complet n'est pas disponible pour cet élément.",
  "transcript.retryA11y": "Réessayer de charger le texte",
  "auth.email": "E-mail",
  "auth.password": "Mot de passe",
  "auth.emailPlaceholder": "vous@exemple.com",
  "login.title": "Bon retour",
  "login.subtitle": "Connectez-vous pour accéder à votre bibliothèque",
  "login.passwordPlaceholder": "Votre mot de passe",
  "login.submit": "Se connecter",
  "login.submitA11y": "Se connecter par e-mail",
  "login.noAccount": "Pas encore de compte ?",
  "login.signUpLink": "S'inscrire",
  "register.title": "Créer un compte",
  "register.subtitle": "Commencez à bâtir votre base de connaissances",
  "register.passwordPlaceholder": "Au moins 6 caractères",
  "register.submit": "Créer le compte",
  "register.submitA11y": "Créer un compte par e-mail",
  "register.hasAccount": "Vous avez déjà un compte ?",
  "register.signInLink": "Se connecter",
  "common.goBack": "Retour",
  "readingLanguage.title": "Langue de lecture",
  "readingLanguage.selectA11y":
    "Choisir {language} comme langue de lecture",
  "readingLanguage.disclaimer":
    "Ce réglage n'affecte que les contenus à venir. Les résumés et traductions existants ne seront pas retraités.",
  "readingLanguage.saved": "Langue mise à jour",
  "readingLanguage.saveA11y": "Enregistrer la langue de lecture",
  "deleteAccount.title": "Supprimer le compte",
  "deleteAccount.warningTitle": "Cette action est irréversible",
  "deleteAccount.warningBody":
    "Supprimer votre compte l'efface définitivement, avec tout ce que vous avez enregistré. Nous ne pouvons pas le restaurer ensuite, même sur demande.",
  "deleteAccount.erasedHeading": "Ce qui est effacé",
  "deleteAccount.erased.library": "Votre bibliothèque et vos dossiers",
  "deleteAccount.erased.artifacts":
    "Toutes vos transcriptions, résumés, notes et cartes mémo",
  "deleteAccount.erased.schedule": "Votre planning de révision et vos digests",
  "deleteAccount.erased.search": "Vos résultats de recherche dans toute l'app",
  "deleteAccount.erased.identity":
    "Votre adresse e-mail et vos identifiants de connexion",
  "deleteAccount.subscriptionHeading": "Votre abonnement",
  "deleteAccount.subscriptionBodyApple":
    "Supprimer votre compte ne résilie pas votre abonnement. Apple continue de vous facturer tant que vous ne l'avez pas résilié dans les réglages de votre store : résiliez-le là-bas d'abord.",
  "deleteAccount.subscriptionBodyGoogle":
    "Supprimer votre compte ne résilie pas votre abonnement. Google continue de vous facturer tant que vous ne l'avez pas résilié dans les réglages de votre store : résiliez-le là-bas d'abord.",
  "deleteAccount.manageApple": "Gérer l'abonnement dans l'App Store",
  "deleteAccount.manageGoogle": "Gérer l'abonnement dans le Play Store",
  "deleteAccount.copyHeading": "Vous voulez une copie d'abord ?",
  "deleteAccount.copyBody":
    "Écrivez-nous avant de supprimer et nous vous enverrons une copie de vos données sous un mois.",
  "deleteAccount.emailA11y": "Écrire à {address}",
  "deleteAccount.acknowledge":
    "Je comprends que mon compte et toutes mes données seront effacés définitivement.",
  "deleteAccount.acknowledgeA11y": "Je comprends que cette action est irréversible",
  "deleteAccount.submit": "Supprimer mon compte",
  "deleteAccount.submitA11y": "Supprimer mon compte",
  "deleteAccount.confirmTitle": "Supprimer le compte ?",
  "deleteAccount.confirmBody":
    "Cela efface définitivement votre compte et tout ce qu'il contient. Cette action est irréversible.",
  "deleteAccount.confirmAction": "Supprimer définitivement",
  "account.title": "Compte",
  "account.notSet": "Non défini",
  "account.subscription.manage": "Changer de formule",
  "account.subscription.manageHint": "Comparez les formules et changez",
  "account.subscription.viewPlans": "Voir les formules",
  "account.subscription.viewPlansHint":
    "Découvrez ce que comprend chaque abonnement",
  "account.subscription.upgrade": "Changer d'offre",
  "account.subscription.upgradeHint":
    "Débloquez plus de minutes d'audio et de vidéo",
  "account.featureRequests": "Suggestions",
  "account.reportBug": "Signaler un bug",
  "account.signOut": "Se déconnecter",
  "account.signOutConfirm": "Voulez-vous vraiment vous déconnecter ?",
  "account.signOutAction": "Oui, me déconnecter",
  "account.feedbackUnavailable": "Suggestions indisponibles",
  "account.feedbackUnavailableBody":
    "L'espace de suggestions n'est pas encore configuré. Veuillez réessayer plus tard.",
  "uiLanguage.title": "Langue de l'app",
  "uiLanguage.disclaimer":
    "Il s'agit de la langue de l'application elle-même. La langue dans laquelle vos résumés et transcriptions sont écrits est la langue de lecture, réglée séparément.",
  "uiLanguage.followDevice": "Suivre mon appareil",
  "uiLanguage.selectA11y": "Utiliser {language} pour l'app",
  "settings.uiLanguage.restartTitle": "Redémarrez pour terminer",
  "settings.uiLanguage.restartBody":
    "Cette langue se lit de droite à gauche : l'app doit redémarrer pour que la mise en page suive. Fermez-la et rouvrez-la.",
  "onboarding.language.title": "Choisissez votre langue de lecture",
  "onboarding.language.subtitle":
    "Les contenus seront traduits dans cette langue si nécessaire.",
  "onboarding.language.continueA11y": "Continuer avec la langue sélectionnée",
  "search.placeholder": "Rechercher dans votre bibliothèque…",
  "search.clearA11y": "Effacer la recherche",
  "search.folders": "Dossiers",
  "search.allMedia": "Tous les médias",
  "search.noFolders":
    "Aucun dossier pour l'instant. Classez vos médias en dossiers au moment de les enregistrer.",
  "search.openFolderA11y": "Ouvrir le dossier {name}",
  "search.resultCount.one": "{count} résultat",
  "search.resultCount.other": "{count} résultats",
  "search.endOfResults": "Fin des résultats",
  "search.noResultsTitle": "Aucun résultat",
  "search.noMatches":
    "Aucune correspondance pour « {query} ». Essayez d'autres mots-clés.",
  "search.emptyLibrary": "Votre bibliothèque est vide",
  "search.emptyLibraryHint":
    "Partagez un lien depuis n'importe quelle app, ou importez un fichier depuis la boîte de réception, et il apparaîtra ici.",
  "search.failed": "La recherche a échoué",
  "search.foldersLoadFailed": "Impossible de charger vos dossiers.",
  "search.libraryLoadFailed": "Impossible de charger votre bibliothèque.",
  "search.retryLibraryA11y": "Réessayer de charger votre bibliothèque",
  "search.retryFoldersA11y": "Réessayer de charger les dossiers",
  "search.retrySearchA11y": "Relancer la recherche",
  "tabs.home": "Accueil",
  "tabs.search": "Recherche",
  "tabs.digest": "Digest",
  "home.loading": "Chargement de votre boîte de réception…",
  "home.retryA11y": "Réessayer de charger la boîte de réception",
  "home.continueLearning": "Reprendre",
  "home.recentlyAdded": "Ajouts récents",
  "home.takePhotoA11y": "Prendre une photo",
  "home.unsortedReview": "Revue des non classés",
  "home.unsortedReviewA11y": "Passer en revue vos médias non classés, {count}",
  "home.empty": "Vos médias partagés apparaîtront ici.",
  "home.emptyHint":
    "Partagez un lien depuis n'importe quelle app, ou touchez + pour importer un fichier ou prendre une photo.",
  "home.untitledFolder": "Dossier",
  "unsortedReview.title": "Revue des non classés",
  "unsortedReview.position": "{current} / {total}",
  "unsortedReview.positionA11y": "Source {current} sur {total}",
  "unsortedReview.closeA11y": "Fermer la revue des non classés",
  "unsortedReview.loadFailed":
    "Impossible de charger vos médias non classés. Veuillez réessayer.",
  "unsortedReview.noBlurb": "Pas encore de résumé court pour celui-ci.",
  "unsortedReview.discard": "Jeter",
  "unsortedReview.discardA11y": "Jeter {title}",
  "unsortedReview.discardFailed":
    "Cette source n'a pas pu être jetée. Veuillez réessayer.",
  "unsortedReview.deepen": "Approfondir",
  "unsortedReview.deepenA11y": "Ouvrir {title}",
  "unsortedReview.save": "Ranger",
  "unsortedReview.saveA11y": "Ranger {title} dans un dossier",
  "unsortedReview.doneTitle": "Plus rien à trier",
  "unsortedReview.doneBody": "Tout ce qui attendait a été traité.",
  "digest.daily": "Quotidien",
  "digest.weekly": "Hebdomadaire",
  "digest.dailyTitle": "Votre journée en revue",
  "digest.weeklyTitle": "Votre semaine en revue",
  "digest.position": "{current} / {total}",
  "digest.positionA11y": "Média {current} sur {total}",
  "digest.loadFailed": "Impossible de charger le digest",
  "digest.tryAgain": "Réessayer",
  "digest.emptyDaily": "Rien à revoir aujourd'hui",
  "digest.emptyWeekly": "Rien à revoir cette semaine",
  "digest.emptyDailyHint":
    "Ce que vous enregistrez apparaîtra ici dans le prochain digest.",
  "digest.emptyWeeklyHint":
    "Ce que vous enregistrez cette semaine apparaîtra ici lundi.",
  "folderPicker.title": "Dossier",
  "folderPicker.saveA11y": "Enregistrer la sélection",
  "folderPicker.searchPlaceholder": "Rechercher",
  "folderPicker.unsorted": "Non trié",
  "folderPicker.myFolders": "Mes dossiers",
  "folderPicker.createA11y": "Créer un dossier",
  "folderPicker.namePlaceholder": "Nom du dossier",
  "folderPicker.confirm": "Confirmer",
  "folderPicker.collapse": "Replier",
  "folderPicker.expand": "Déplier",
  "folderPicker.noMatches": "Aucun dossier ne correspond à votre recherche",
  "folderPicker.loadFailed": "Impossible de charger les dossiers",
  "folderPicker.saveFailed": "Impossible d'enregistrer le dossier",
  "folderPicker.createFailed": "Impossible de créer le dossier",
  "folders.loading": "Chargement des dossiers…",
  "folders.loadFailed":
    "Impossible de charger vos dossiers. Veuillez réessayer.",
  "folders.empty": "Aucun dossier",
  "folders.emptyHint":
    "Classez vos médias en dossiers au moment de les enregistrer pour les retrouver ici.",
  "folders.emptySubtitle": "Vide",
  "folders.childCount.one": "{count} dossier",
  "folders.childCount.other": "{count} dossiers",
  "media.tab.reader": "Lecture",
  "media.tab.ai": "IA",
  "media.sectionsA11y": "Sections du média",
  "media.loadFailed": "Impossible de charger les détails du média.",
  "media.retryA11y": "Réessayer de charger les détails du média",
  "media.processingHint": "Cela prend généralement moins d'une minute.",
  "media.timeoutTitle": "Cela prend plus de temps que d'habitude.",
  "media.timeoutHint": "Tirez pour actualiser ou revenez plus tard.",
  "media.refresh": "Actualiser",
  "media.refreshA11y": "Actualiser l'état du média",
  "media.failedTitle": "Le traitement a échoué",
  "media.failedFallback": "Une erreur inattendue est survenue.",
  "media.processing.audio": "Transcription de l'audio…",
  "media.processing.video": "Transcription de la vidéo…",
  "media.processing.extracting": "Extraction du contenu…",
  "media.processing.generating": "Génération du texte…",
  "media.transcriptLoadFailed":
    "Impossible de charger le texte pour le moment.",
  "media.movedToNamed": "Déplacé vers « {name} »",
  "media.movedToFolder": "Déplacé vers un dossier",
  "media.removedFromFolder": "Retiré du dossier",
  "media.openFailed": "Impossible d'ouvrir {host}",
  "media.moveToFolderA11y": "Déplacer vers un dossier",
  "folder.tab.sources": "Sources",
  "folder.tab.ai": "IA",
  "folder.sectionsA11y": "Sections du dossier",
  "folder.loadFailed":
    "Impossible de charger ce dossier. Veuillez réessayer.",
  "folder.retryA11y": "Réessayer de charger le dossier",
  "folder.artifactsLoadFailed":
    "Impossible de charger le contenu généré. Veuillez réessayer.",
  "folder.empty": "Ce dossier est vide",
  "folder.emptyHint":
    "Les médias que vous classez dans ce dossier apparaîtront ici.",
  "bugReport.subject": "Objet",
  "bugReport.subjectPlaceholder": "Résumé bref du problème",
  "bugReport.subjectA11y": "Objet du rapport de bug",
  "bugReport.description": "Description",
  "bugReport.descriptionPlaceholder":
    "Étapes pour reproduire, ce que vous attendiez, ce qui s'est passé à la place…",
  "bugReport.descriptionA11y": "Description du rapport de bug",
  "bugReport.attachment": "Pièce jointe (facultatif)",
  "bugReport.attach": "Joindre un fichier",
  "bugReport.attachA11y": "Joindre un fichier au rapport de bug",
  "bugReport.attachChoose": "Choisissez une source",
  "bugReport.photoLibrary": "Photothèque",
  "bugReport.files": "Fichiers",
  "bugReport.removeFileA11y": "Retirer le fichier joint",
  "bugReport.submit": "Envoyer",
  "bugReport.submitA11y": "Envoyer le rapport de bug",
  "bugReport.submitting": "Envoi du rapport…",
  "bugReport.uploading": "Envoi de la pièce jointe…",
  "bugReport.submitted": "Rapport envoyé",
  "bugReport.ticketId": "Numéro de ticket",
  "bugReport.doneA11y": "Terminé, revenir au compte",
  "bugReport.closeA11y": "Fermer le formulaire de rapport de bug",
  "bugReport.submitFailed":
    "Impossible d'envoyer le rapport de bug. Veuillez réessayer.",
  "bugReport.pickFileFailed":
    "Impossible de sélectionner le fichier. Veuillez réessayer.",
  "bugReport.pickImageFailed":
    "Impossible de sélectionner l'image. Veuillez réessayer.",
  "bugReport.fileTypeTitle": "Type de fichier non autorisé",
  "bugReport.fileTypeAccepted": "Types de fichiers acceptés : {list}",
  "bugReport.fileTypeRejected":
    "Le type de fichier sélectionné ({type}) n'est pas accepté.",
  "bugReport.fileTooLargeTitle": "Fichier trop volumineux",
  "bugReport.fileTooLarge":
    "La taille maximale est {max}. Votre fichier fait {size}.",
  "paywall.title": "Choisissez votre formule",
  "paywall.plansLoadFailed":
    "Nous n'avons pas pu charger les formules. Vérifiez votre connexion et réessayez.",
  "paywall.tryAgain": "Réessayer",
  "paywall.pricesUnavailable":
    "Les prix sont indisponibles — le {store} ne propose pas ces abonnements pour le moment.",
  "paywall.selectorLabel": "Choisissez combien vous envoyez chaque mois",
  "paywall.selectorLabelReadOnly": "Ce que chaque formule vous donne",
  "paywall.priceUnavailableA11y": "prix indisponible",
  "paywall.pricePerMonthA11y": "{price} par mois",
  "paywall.promise":
    "Tout ce que vous envoyez revient en texte que vous pouvez lire, chercher et garder.",
  "paywall.pricePeriod": "/mois",
  "paywall.sourcesHeading": "Ce que vous pouvez envoyer",
  "paywall.filesHeading": "Fichiers de votre téléphone",
  "paywall.costHeading": "Ce que ça consomme en minutes",
  "paywall.ctaChoose": "Choisir une formule",
  "paywall.ctaStart": "Commencer avec {plan} — {price}/mois",
  "paywall.purchaseSuccess": "Achat réussi",
  "paywall.purchaseSuccessBody":
    "Votre abonnement est maintenant actif. Profitez-en !",
  "paywall.purchasePending": "Achat en attente",
  "paywall.purchasePendingBody":
    "Votre achat est en attente d'approbation. Vous serez notifié une fois terminé.",
  "paywall.purchaseFailed": "Échec de l'achat",
  "paywall.unexpectedError":
    "Une erreur inattendue est survenue. Veuillez réessayer.",
  "paywall.renewalTerms":
    "Le paiement est débité de votre compte {store} à la confirmation de l'achat. L'abonnement se renouvelle chaque mois sauf résiliation au moins 24 heures avant la fin de la période en cours, et votre compte est débité du renouvellement dans les 24 heures qui la précèdent.",
  "paywall.terms": "Conditions d'utilisation",
  "paywall.privacy": "Politique de confidentialité",
  "paywall.cancelAnytime": "Résiliez à tout moment dans votre compte {store}.",
  "artifact.loadFailed": "Impossible de charger ce contenu généré.",
  "artifact.failedTitle": "Chargement impossible",
  "artifact.retryA11y": "Réessayer de charger le contenu généré",
  "artifact.notReady": "Pas encore prêt",
  "artifact.pendingBody":
    "Ce contenu est encore en cours de génération. Revenez dans un instant.",
  "artifact.refreshA11y": "Actualiser le contenu généré",
  "artifact.generationFailedTitle": "La génération a échoué",
  "artifact.generationFailedBody":
    "Ce contenu n'a pas pu être généré, et plus rien n'est en cours. Relancez la génération pour réessayer.",
  "artifact.regenerate": "Relancer la génération",
  "artifact.regenerateA11y": "Relancer la génération de ce contenu",
  "artifact.regenerating": "Lancement...",
  "artifact.regenerationQueued":
    "Génération relancée. Revenez dans un instant.",
  "artifact.anotherLanguage": "une autre langue",
  "artifact.translatedFrom": "Traduit depuis {language}",
  "artifact.translationFailed":
    "Traduction indisponible — affiché en {language}",
  "artifact.translationFailedA11y":
    "Traduction indisponible. Ce contenu est affiché dans sa langue d'origine, {language}.",
  "artifact.section.keyPoints": "Points clés",
  "artifact.section.takeaway": "À retenir",
  "artifact.section.context": "Contexte",
  "artifact.section.mainTopics": "Thèmes principaux",
  "artifact.section.quotes": "Citations marquantes",
  "artifact.section.conclusion": "Conclusion",
  "artifact.section.objectives": "Objectifs",
  "artifact.section.concepts": "Concepts",
  "artifact.section.actionItems": "Actions à mener",
  "artifact.section.glossary": "Glossaire",
  "artifact.noFlashcards": "Aucune carte mémo dans ce contenu.",
  "artifact.cardCount.one": "{count} carte",
  "artifact.cardCount.other": "{count} cartes",
  "artifact.question": "QUESTION",
  "artifact.answer": "RÉPONSE",
  "artifact.tapToReveal": "Toucher pour révéler",
  "artifact.revealAnswerA11y": "Toucher pour révéler la réponse",
  "artifact.hideAnswer": "Masquer la réponse",
  "artifact.noQuestions": "Aucune question dans ce contenu.",
  "artifact.quizProgress": "Progression du quiz",
  "artifact.questionPosition": "Question {index} sur {total}",
  "artifact.quizComplete": "Quiz terminé",
  "artifact.explanation": "EXPLICATION",
  "artifact.optionA11y": "Option {label} : {text}{state}",
  "share.title.url": "Enregistrer le lien",
  "share.title.text": "Enregistrer la note",
  "share.title.audio": "Enregistrer l'audio",
  "share.title.file": "Importer le fichier",
  "share.title.photo": "Enregistrer la photo",
  "share.processing": "Traitement du contenu partagé…",
  "share.invalid": "Impossible d'enregistrer ce contenu",
  "share.saved": "Enregistré !",
  "share.saveFailed": "Échec de l'enregistrement",
  "share.saving": "Enregistrement…",
  "share.uploadingAudio": "Envoi de l'audio…",
  "share.uploadingFile": "Envoi du fichier…",
  "share.noteText": "Note",
  "share.reject.noText":
    "Cette note ne contient aucun texte à enregistrer. Si elle est verrouillée, déverrouillez-la puis partagez-la à nouveau.",
  "share.reject.tooLong":
    "Cette note est trop longue pour être enregistrée : {count} caractères, et le maximum est {max}.",
  "share.reject.nothingToSave":
    "Il n'y a rien ici que nous puissions enregistrer. Essayez de partager le texte de la note.",
  "share.chooseFolder": "Choisir un dossier",
  "share.folderPlaceholder": "Ranger dans un dossier",
  "share.success.duplicate": "Ce contenu était déjà dans votre boîte de réception.",
  "share.success.audio":
    "Audio enregistré. La transcription va bientôt commencer.",
  "share.success.text": "Note enregistrée dans votre boîte de réception.",
  "share.success.photo":
    "Photo importée. L'extraction du texte va bientôt commencer.",
  "share.success.audioFile":
    "Fichier audio importé. La transcription va bientôt commencer.",
  "share.success.file": "Fichier importé. Le traitement va bientôt commencer.",
  "share.success.url":
    "Lien ajouté à votre boîte de réception. Le traitement va bientôt commencer.",
  // Auto-started ingestion: what the two header buttons do (task-378)
  "share.autoStart.hint": "Le traitement a déjà commencé.",
  "share.autoStart.keep":
    "Choisissez un dossier si vous le souhaitez, puis appuyez sur Enregistrer pour le conserver. Fermer le supprime.",
  "share.autoStart.done": "Traitement lancé",
  "share.cancel.action": "Supprimer cette sauvegarde",
  "share.cancel.inProgress": "Suppression de cette sauvegarde…",
  "share.cancel.failedTitle": "Suppression impossible",
  "share.cancel.failed":
    "Cette sauvegarde n'a pas pu être supprimée. Vérifiez votre connexion et réessayez.",
  "share.cancel.keepHint":
    "Ou appuyez sur Enregistrer pour finalement le conserver.",
  "share.folderFailed":
    "Le dossier n'a pas pu être appliqué. Appuyez sur Enregistrer pour réessayer.",
  "import.filesUnavailable": "Impossible d'ouvrir vos fichiers",
  "import.filesUnavailableBody":
    "Le navigateur de fichiers n'a pas pu être ouvert. Veuillez réessayer.",
  "import.formatNotSupported": "Format non pris en charge",
  "import.cameraUnavailable": "Appareil photo indisponible",
  "import.cameraUnavailableBody":
    "L'appareil photo n'a pas pu être démarré sur cet appareil.",
  "import.cameraPermission": "Accès à l'appareil photo requis",
  "import.cameraPermissionAsk":
    "Autorisez l'accès à l'appareil photo pour capturer un document ou une page à importer.",
  "import.cameraPermissionSettings":
    "L'accès à l'appareil photo est désactivé. Activez-le pour cette app dans les réglages de votre appareil pour capturer un document.",
  "import.galleryUnavailable": "Galerie indisponible",
  "import.galleryUnavailableBody":
    "Votre galerie photo n'a pas pu être ouverte. Veuillez réessayer.",
  "import.photoTooLarge": "Photo trop volumineuse",
  "import.photoNotSupported": "Photo non prise en charge",
  "upload.reject.extension":
    "Les fichiers avec l'extension .{extension} ne peuvent pas être importés. Formats pris en charge : {formats}.",
  "upload.reject.noExtension":
    "Ce fichier n'a pas d'extension reconnaissable. Formats pris en charge : {formats}.",
  "upload.reject.empty": "Ce fichier est vide : il n'y a rien à importer.",
  "upload.reject.tooLarge":
    "Ce fichier fait {size}, au-delà de la limite de {max} pour un import unique.",
  "upload.transferFailed":
    "Ce fichier n'a pas pu être envoyé. Vérifiez votre connexion et réessayez.",
  "upload.diagnostics.title": "Détails techniques",
  "upload.diagnostics.hint":
    "Joignez cette ligne si vous signalez le problème : elle nomme l'étape qui a échoué.",
  "home.loadFailed":
    "Impossible de charger votre boîte de réception. Veuillez réessayer.",
  "share.unsupportedFile": "Ce type de fichier n'est pas encore pris en charge.",
  "share.signInLinks": "Vous devez être connecté pour enregistrer des liens.",
  "share.signInContent": "Vous devez être connecté pour enregistrer du contenu.",
  "share.signInFiles": "Vous devez être connecté pour importer des fichiers.",
  "transcript.translating": "Traduction du texte…",
  "transcript.translationFailed":
    "La traduction a échoué. Affichage du texte original.",
  "paywall.subtitle":
    "Chaque formule fait tout. Elles ne diffèrent que par ce que vous pouvez envoyer.",
  "startupError.title": "L'application n'a pas pu démarrer",
  "startupError.body":
    "Une erreur inattendue a interrompu le démarrage de l'application. Un nouvel essai suffit généralement à repartir.",
  "startupError.retryA11y": "Réessayer de démarrer l'application",
  "startupError.showDetails": "Afficher les détails techniques",
  "startupError.hideDetails": "Masquer les détails techniques",
};
