import type { Catalog } from "./runtime";

/** German catalogue. See `en` for the reference wording and the key layout. */
export const de: Catalog = {
  "common.ok": "OK",
  "common.cancel": "Abbrechen",
  "common.retry": "Wiederholen",
  "common.delete": "Löschen",
  "common.save": "Speichern",
  "common.done": "Fertig",
  "common.close": "Schließen",
  "common.dismiss": "Ausblenden",
  "common.loading": "Wird geladen …",
  "common.continue": "Weiter",
  "common.back": "Zurück",
  "common.error": "Fehler",
  "common.untitled": "Ohne Titel",
  "common.somethingWentWrong": "Etwas ist schiefgelaufen",
  "common.itemCount.one": "{count} Element",
  "common.itemCount.other": "{count} Elemente",
  "trial.badge": "Kostenlose Testphase",
  "trial.lastDay": "Kostenlose Testphase - letzter Tag",
  "trial.daysLeft.one": "Kostenlose Testphase - noch {count} Tag",
  "trial.daysLeft.other": "Kostenlose Testphase - noch {count} Tage",
  "home.tile.a11yCollection": "Sammlung {name}, {count}",
  "home.tile.a11yByCreator": "{title} von {creator}",
  "quota.warning.trial":
    "Du hast {percent} % der Minuten deiner kostenlosen Testphase verbraucht.",
  "quota.warning.trialWithDate":
    "Du hast {percent} % der Minuten deiner kostenlosen Testphase verbraucht. Sie füllen sich nicht wieder auf — deine Testphase endet am {date}.",
  "quota.warning.monthly":
    "Du hast {percent} % der Minuten dieses Monats verbraucht.",
  "quota.warning.monthlyWithDate":
    "Du hast {percent} % der Minuten dieses Monats verbraucht. Sie werden am {date} zurückgesetzt.",
  "quota.seePlans": "Tarife ansehen",
  "quota.dismissWarning": "Minutenhinweis ausblenden",
  "artifacts.sourceCount.one": "{count} Quelle",
  "artifacts.sourceCount.other": "{count} Quellen",
  "artifacts.status.queued": "Wartet",
  "artifacts.status.generating": "Wird erstellt …",
  "artifacts.status.failed": "Fehler",
  "artifacts.status.generated": "Erstellt",
  "artifacts.history.a11yRow": "{type}: {title}",
  "mediaType.podcast": "PODCAST",
  "mediaType.article": "ARTIKEL",
  "mediaType.video": "VIDEO",
  "mediaType.short": "KURZ",
  "mediaType.audio": "AUDIO",
  "mediaType.text": "TEXT",
  "mediaType.document": "DOK",
  "mediaType.link": "LINK",
  "mediaCard.a11yByCreator": "{title} von {creator}, {type}",
  "mediaCard.a11yFromDomain": "{title}, {type} von {domain}",
  "mediaCard.longPressHint":
    "Zweimal tippen und halten, um diese Quelle zu verschieben, umzubenennen oder zu löschen",
  "mediaActions.move.label": "Verschieben",
  "mediaActions.rename.label": "Umbenennen",
  "mediaActions.delete.label": "Löschen",
  "mediaActions.rename.title": "Diese Quelle umbenennen",
  "mediaActions.rename.placeholder": "Name der Quelle",
  "mediaActions.renameFailed":
    "Diese Quelle konnte nicht umbenannt werden. Ihr Name ist unverändert.",
  "mediaActions.deleteTitle": "Diese Quelle löschen?",
  "mediaActions.deleteBody":
    "„{title}“ wird aus deiner Bibliothek entfernt. Das lässt sich nicht rückgängig machen.",
  "mediaActions.deleteFailed":
    "Diese Quelle konnte nicht gelöscht werden. Sie ist weiterhin in deiner Bibliothek.",
  "collectionActions.longPressHint":
    "Zweimal tippen und halten, um diese Sammlung umzubenennen oder zu löschen",
  "collectionActions.rename.label": "Umbenennen",
  "collectionActions.delete.label": "Löschen",
  "collectionActions.rename.title": "Diese Sammlung umbenennen",
  "collectionActions.rename.placeholder": "Name der Sammlung",
  "collectionActions.renameFailed":
    "Diese Sammlung konnte nicht umbenannt werden. Ihr Name ist unverändert.",
  "collectionActions.deleteTitle": "Diese Sammlung löschen?",
  "collectionActions.deleteBody":
    "„{name}“ wird gelöscht. Alle darin enthaltenen Quellen wandern nach {unsorted} – keine davon wird gelöscht.",
  "collectionActions.deleteSubCollections.one":
    "Ihre Untersammlung wird ebenfalls gelöscht, und die Quellen darin wandern ebenfalls nach {unsorted}.",
  "collectionActions.deleteSubCollections.other":
    "Ihre {count} Untersammlungen werden ebenfalls gelöscht, und die Quellen darin wandern ebenfalls nach {unsorted}.",
  "collectionActions.deleteFailed":
    "Diese Sammlung konnte nicht gelöscht werden. Sie ist weiterhin in deiner Bibliothek.",
  "addSource.title": "Zu deinem Posteingang hinzufügen",
  "addSource.importFile.label": "Datei importieren",
  "addSource.importFile.description":
    "Ein PDF, ein Office-Dokument, ein Bild oder eine Audiodatei von deinem Telefon.",
  "addSource.importPhoto.label": "Foto importieren",
  "addSource.importPhoto.description":
    "Wähle ein Foto, das du bereits in deiner Galerie hast.",
  "auth.or": "oder",
  "auth.continueWithGoogle": "Mit Google fortfahren",
  "auth.signInWithApple": "Mit Apple anmelden",
  "auth.google.notCompleted":
    "Die Google-Anmeldung wurde nicht abgeschlossen. Bitte versuche es erneut.",
  "auth.google.noIdToken":
    "Das Google-ID-Token konnte nicht abgerufen werden. Bitte versuche es erneut.",
  "auth.google.noGoogleAccount":
    "Auf diesem Gerät ist kein Google-Konto vorhanden. Füge in den Geräteeinstellungen eines hinzu und versuche es erneut.",
  "auth.google.failed":
    "Die Google-Anmeldung konnte nicht abgeschlossen werden. Bitte versuche es erneut.",
  "auth.apple.noIdentityToken":
    "Das Apple-Identitätstoken konnte nicht abgerufen werden. Bitte versuche es erneut.",
  "artifacts.type.summaryShort": "Zusammenfassung",
  "artifacts.type.summaryDetailed": "Ausführliche Zusammenfassung",
  "artifacts.type.notes": "Lernnotizen",
  "artifacts.type.flashcards": "Lernkarten",
  "artifacts.type.quiz": "Quiz",
  "artifacts.generate": "Erstellen",
  "artifacts.a11yGenerate": "{label} erstellen",
  "artifacts.processing": "Wird verarbeitet …",
  "artifacts.panel.generateHeading": "Erstellen",
  "artifacts.panel.generatedHeading": "Erstellt",
  "artifacts.panel.retryA11y": "Erstellte Inhalte erneut laden",
  "artifacts.panel.empty":
    "Noch nichts erstellt. Wähle oben ein Format, um etwas zu erstellen.",
  "duration.minutes.one": "{count} Min.",
  "duration.minutes.other": "{count} Min.",
  "duration.hours.one": "{count} Std.",
  "duration.hours.other": "{count} Std.",
  "duration.hoursMinutes": "{hours} {minutes}",
  "time.justNow": "Gerade eben",
  "time.minutesAgo.one": "vor {count} Min.",
  "time.minutesAgo.other": "vor {count} Min.",
  "time.hoursAgo.one": "vor {count} Std.",
  "time.hoursAgo.other": "vor {count} Std.",
  "time.yesterday": "Gestern",
  "time.today": "Heute",
  "time.daysAgo.one": "vor {count} T.",
  "time.daysAgo.other": "vor {count} T.",
  "subscription.resetLabel.trialEnds": "TESTPHASE ENDET",
  "subscription.resetLabel.resets": "ZURÜCKSETZUNG",
  "subscription.resetLabel.ends": "ENDET",
  "subscription.resetLabel.periodEnds": "ZEITRAUM ENDET",
  "subscription.status.paymentIssue": "Zahlungsproblem",
  "subscription.status.cancelled": "Gekündigt",
  "error.sessionExpired":
    "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.",
  "error.invalidCredentials":
    "E-Mail oder Passwort ist falsch. Bitte versuche es erneut.",
  "error.emailNotVerified":
    "Bitte bestätige deine E-Mail-Adresse, bevor du dich anmeldest.",
  "error.emailAlreadyExists":
    "Mit dieser E-Mail-Adresse existiert bereits ein Konto.",
  "error.invalidVerificationToken":
    "Ungültiger Bestätigungslink. Bitte fordere einen neuen an.",
  "error.userNotFound":
    "Kein Konto mit dieser E-Mail-Adresse gefunden. Prüfe die Adresse oder erstelle ein neues Konto.",
  "error.notAuthorized": "Du hast keine Berechtigung für diese Aktion.",
  "error.notFound": "Inhalt nicht gefunden. Versuche es mit einer anderen Suche.",
  "error.mediaNotFound":
    "Dieses Medium wurde nicht gefunden oder ist nicht mehr verfügbar.",
  "error.artifactNotFound":
    "Dieser erstellte Inhalt wurde nicht gefunden oder ist nicht mehr verfügbar.",
  "error.invalidUrl": "Dieser Link ist ungültig. Versuche eine andere URL.",
  "error.unsupportedUrl":
    "Dieser Link wird noch nicht unterstützt. Versuche eine andere Quelle.",
  "error.validation": "Bitte fülle alle Pflichtfelder aus.",
  "error.rateLimited":
    "Zu viele Anfragen. Warte einen Moment und versuche es erneut.",
  "error.conflict":
    "Diese Aktion steht im Konflikt mit vorhandenen Daten. Aktualisiere und versuche es erneut.",
  "error.badRequest": "Bitte prüfe deine Eingabe und versuche es erneut.",
  "error.invalidEmail": "Bitte gib eine gültige E-Mail-Adresse ein.",
  "error.passwordTooShort":
    "Das Passwort muss mindestens 8 Zeichen lang sein.",
  "error.passwordsDoNotMatch":
    "Die Passwörter stimmen nicht überein. Bitte versuche es erneut.",
  "error.network":
    "Netzwerkfehler. Prüfe deine Verbindung und versuche es erneut.",
  "error.timeout":
    "Zeitüberschreitung bei der Anfrage. Bitte versuche es erneut.",
  "error.outOfMinutes":
    "Deine Minuten für diesen Zeitraum sind aufgebraucht. Wechsle den Tarif, um weiter Audio und Video zu importieren.",
  "quota.title.outOfMinutes": "Keine Minuten mehr",
  "quota.title.itemTooLong": "Zu lang für einen Import",
  "quota.refusal.noPlan":
    "Dein Tarif ist beendet. Abonniere, um weiter in deiner Bibliothek zu speichern.",
  "quota.refusal.outOfMinutes":
    "Deine Minuten für diesen Zeitraum sind aufgebraucht. Wechsle den Tarif, um dies jetzt zu verarbeiten.",
  "quota.refusal.outOfMinutesUntil":
    "Du hast bis zum {date} keine Minuten mehr. Wechsle den Tarif, um dies jetzt zu verarbeiten.",
  "quota.refusal.needsMore":
    "Dieser Import benötigt {needed}, und dir bleiben {remaining} bis zum {date}. Wechsle den Tarif, um ihn jetzt zu verarbeiten.",
  "quota.refusal.needsMoreNoDate":
    "Dieser Import benötigt {needed}, und dir bleiben {remaining}. Wechsle den Tarif, um ihn jetzt zu verarbeiten.",
  "quota.refusal.itemTooLong":
    "Das dauert {duration} und liegt damit über den {max}, die ein einzelner Import in deinem Tarif nutzen darf. Teile es in kürzere Teile auf.",
  "quota.refusal.itemTooLongGeneric":
    "Das ist zu lang für einen einzelnen Import in deinem Tarif. Teile es in kürzere Teile auf.",
  "artifacts.refusal.collectionEmpty":
    "Diese Sammlung hat noch keine Quelle mit Transkript. Füge Medien hinzu oder warte, bis die gespeicherten fertig verarbeitet sind.",
  "artifacts.refusal.mediaEmpty":
    "Dieses Element hat noch kein Transkript, also gibt es nichts, woraus etwas erstellt werden könnte.",
  "artifacts.refusal.tooManySources":
    "Diese Sammlung hat {count} Quellen, mehr als die {max}, die eine einzelne Erstellung lesen kann. Erstelle es auf einer kleineren Untersammlung.",
  "artifacts.refusal.tooMuchText":
    "Hier ist zu viel Text für eine einzelne Erstellung. Erstelle es auf einer kleineren Untersammlung.",
  "artifacts.refusal.sourcesPending.one":
    "{count} Quelle wird noch vorbereitet. Versuche es gleich noch einmal.",
  "artifacts.refusal.sourcesPending.other":
    "{count} Quellen werden noch vorbereitet. Versuche es gleich noch einmal.",
  "artifacts.refusal.transcriptPending":
    "Das Transkript wird noch vorbereitet. Versuche es gleich noch einmal.",
  "artifacts.refusal.translationFailed":
    "Dieses Transkript konnte nicht übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.sourcesTranslationFailed.one":
    "Die einzige Quelle hier konnte nicht übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.sourcesTranslationFailed.other":
    "Keine dieser {count} Quellen konnte übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.generic":
    "Diese Erstellung konnte nicht gestartet werden. Bitte versuche es erneut.",
  "plan.hourlyRate": "≈ {price} pro Stunde",
  "plan.card.allowance": "{duration} Transkription",
  "plan.card.perImport": "bis zu {duration} pro Import",
  "plan.rec.cappedLargest":
    "Du hast alle {duration} dieses Zeitraums verbraucht. {plan} ist der größte Tarif, den wir anbieten.",
  "plan.rec.cappedNextUp":
    "Du hast alle {duration} dieses Zeitraums verbraucht. {plan} ist die nächste Stufe.",
  "plan.rec.overLargest":
    "Du hast in diesem Zeitraum {duration} verbraucht — mehr, als irgendein Tarif enthält. {plan} ist der größte, den wir anbieten.",
  "plan.rec.trialFloor":
    "Du hast bisher {duration} deiner Testphase verbraucht. {plan} hält dich auf dem Tarif, den du bereits nutzt.",
  "plan.rec.covering":
    "Du hast in diesem Zeitraum {duration} verbraucht. {plan} ist der kleinste Tarif, der das abdeckt.",
  "plan.badge.recommended": "FÜR DICH EMPFOHLEN",
  "plan.badge.yourTrial": "DEIN TESTTARIF",
  "plan.badge.bestValue": "BESTPREIS",
  "paywall.reason.trialOut":
    "Die Minuten deiner Testphase sind verbraucht und füllen sich nicht wieder auf. Wähle einen Tarif, um weiter Audio und Video zu importieren.",
  "paywall.reason.outNoDate":
    "Deine Minuten für diesen Zeitraum sind aufgebraucht. Ein größerer Tarif gibt dir jetzt mehr.",
  "paywall.reason.outWithDate":
    "Du hast bis zum {date} keine Minuten mehr. Ein größerer Tarif gibt dir jetzt mehr.",
  "paywall.reason.trialLow":
    "Noch {left} in deiner Testphase, und Testminuten füllen sich nicht wieder auf.",
  "paywall.reason.lowNoDate": "Noch {left} in diesem Zeitraum.",
  "paywall.reason.lowWithDate": "Noch {left} bis zum {date}.",
  "plan.minutesRule":
    "Minuten decken Audio und Video ab, die wir transkribieren. Artikel und Webseiten kosten keine Minuten. Deine Bibliothek zu lesen, ist unbegrenzt.",
  "plan.legend.realLength":
    "Audio und Video zählen ihre tatsächliche Länge, Minute für Minute.",
  "plan.legend.captions":
    "Ein Video, das bereits kaufbare Untertitel hat, kostet {duration}, egal wie lang es ist.",
  "plan.legend.documents":
    "Ein PDF, ein Office-Dokument oder ein Foto, von dem wir den Text lesen, kostet 1 Min. pro {pages} Seiten.",
  "plan.legend.collections":
    "Eine Erstellung über eine ganze Sammlung kostet 1 Min. pro {sources} Elemente darin. Auf einem einzelnen Element ist sie kostenlos.",
  "plan.legend.free":
    "Artikel, Webseiten, TikToks und Instagram-Fotobeiträge kosten gar nichts: Sie werden nicht transkribiert.",
  "plan.legend.overLimit":
    "Über dem Maximum eines Tarifs pro Import wird ein Import abgelehnt statt berechnet — teile ihn in kürzere Teile auf.",
  "plan.list.separator": ", ",
  "plan.list.lastConjunction": "{list} und {last}",
  "plan.highlight.capture":
    "Speichere aus jeder App: YouTube, Podcasts, TikTok, Instagram, X, Artikel, PDFs, Dokumente, Fotos und Audiodateien",
  "plan.highlight.read":
    "Lies das vollständige Transkript, übersetzt in deine Lesesprache",
  "plan.highlight.generate":
    "Erstelle {list} auf Abruf, pro Element oder pro Sammlung",
  "plan.highlight.organise":
    "Ordne in Sammlungen und Tags, durchsuche alles, täglicher Digest",
  "plan.includes.capture.title": "Speichere alles, aus jeder App",
  "plan.includes.capture.links":
    "Teile einen Link aus jeder App oder füge ihn ein: YouTube-Videos, Podcast-Folgen von Apple Podcasts, Spotify, Deezer oder jedem RSS-Feed, TikToks, Instagram-Reels und -Fotobeiträge, X-Beiträge, Nachrichtenartikel und jede Webseite.",
  "plan.includes.capture.files":
    "Sende eine Datei von deinem Telefon: PDF-, Word-, PowerPoint- und Excel-Dokumente, Fotos und Screenshots, von denen wir den Text lesen, und Audioaufnahmen (MP3, M4A, WAV, FLAC, AAC, OGG, Opus).",
  "plan.includes.read.title": "Lies es, was auch immer es war",
  "plan.includes.read.transcripts":
    "Audio und Video kommen als vollständiger Text zurück, Wort für Wort transkribiert: Eine Folge, für die du keine Zeit zum Hören hast, kannst du stattdessen lesen, überfliegen oder durchsuchen.",
  "plan.includes.read.translation":
    "Transkripte werden in deine Lesesprache übersetzt, {count} zur Auswahl, und du kannst sie jederzeit ändern.",
  "plan.includes.generate.title": "Mach etwas daraus, das bleibt",
  "plan.includes.generate.onDemand": "Auf jedem Element, auf Abruf: {list}.",
  "plan.includes.generate.collection":
    "Führe dieselben Erstellungen über eine ganze Sammlung aus, um eine einzige Synthese von allem zu erhalten, was du dort abgelegt hast.",
  "plan.includes.generate.kept":
    "Jede Erstellung bleibt erhalten, du kannst also darauf zurückkommen oder später eine neue anfordern.",
  "plan.includes.organise.title": "Finde es Monate später wieder",
  "plan.includes.organise.file":
    "Lege alles in Sammlungen und Tags ab, beim Speichern oder jederzeit danach.",
  "plan.includes.organise.search":
    "Volltextsuche über alles, was du je gespeichert hast, Transkripte inbegriffen.",
  "plan.includes.organise.digest":
    "Ein täglicher und ein wöchentlicher Digest darüber, was hereinkam und was es wert ist, noch einmal angesehen zu werden.",
  "plan.includes.minutes.title": "Was die monatlichen Minuten zählen",
  "plan.trial.accessFull": "voller Zugang",
  "plan.trial.accessTier": "{tier}-Zugang",
  "plan.trial.generic":
    "Deine kostenlose Testphase läuft: {access}, ohne Kosten und ohne etwas zu kündigen.",
  "plan.trial.genericWithDate":
    "Deine kostenlose Testphase läuft: {access} bis zum {date}, ohne Kosten und ohne etwas zu kündigen.",
  "plan.trial.days":
    "Deine {days}-tägige kostenlose Testphase läuft: {access}, ohne Kosten und ohne etwas zu kündigen.",
  "plan.trial.daysWithDate":
    "Deine {days}-tägige kostenlose Testphase läuft: {access} bis zum {date}, ohne Kosten und ohne etwas zu kündigen.",
  "account.plan.heading": "DEIN TARIF",
  "account.plan.checking": "Dein Tarif wird geprüft …",
  "account.plan.unavailable": "Tarifstatus nicht verfügbar",
  "account.plan.unavailableHint":
    "Wir konnten die Details deines Abos nicht laden. Dein Tarif selbst ist davon nicht betroffen.",
  "account.plan.retryA11y": "Tarifdetails erneut laden",
  "account.plan.none": "Kein aktiver Tarif",
  "account.plan.noneHint":
    "Deine Minuten und dein Zurücksetzungsdatum erscheinen hier, sobald ein Abo aktiv ist.",
  "account.plan.freeTrial": "Kostenlose Testphase",
  "account.plan.active": "Aktiver Tarif",
  "account.plan.minutesLeft": "VERBLEIBENDE MINUTEN",
  "account.plan.minutesLeftA11y":
    "{remaining} von {included} Minuten in diesem Zeitraum verbleibend",
  "account.plan.unknownDate": "Unbekannt",
  "account.plan.resetDateA11y": "{label} {date}",
  "account.plan.resetDateUnknownA11y": "Zurücksetzungsdatum unbekannt",
  "account.plan.minutesRuleTrial":
    "{rule} Testminuten füllen sich nicht wieder auf.",
  "transcript.heading": "Transkript",
  "transcript.empty": "Noch kein Transkript verfügbar.",
  "transcript.emptyHint":
    "Das Transkript erscheint, sobald die Verarbeitung abgeschlossen ist.",
  "transcript.status.pending":
    "Die Verarbeitung des Transkripts beginnt in Kürze.",
  "transcript.status.extracting": "Audioinhalt wird extrahiert …",
  "transcript.status.transcribing": "Audio wird in Text transkribiert …",
  "transcript.status.ready": "Das Transkript ist fertig.",
  "transcript.status.failed": "Die Verarbeitung des Transkripts ist fehlgeschlagen.",
  "transcript.paragraphCount.one": "{count} Absatz",
  "transcript.paragraphCount.other": "{count} Absätze",
  "transcript.loading": "Transkript wird geladen …",
  "transcript.notAvailable":
    "Der Transkriptinhalt ist für dieses Element nicht verfügbar.",
  "transcript.retryA11y": "Transkript erneut laden",
  "auth.email": "E-Mail",
  "auth.password": "Passwort",
  "auth.emailPlaceholder": "du@beispiel.com",
  "login.title": "Willkommen zurück",
  "login.subtitle": "Melde dich an, um auf deine Bibliothek zuzugreifen",
  "login.passwordPlaceholder": "Dein Passwort",
  "login.submit": "Anmelden",
  "login.submitA11y": "Mit E-Mail anmelden",
  "login.noAccount": "Noch kein Konto?",
  "login.signUpLink": "Registrieren",
  "register.title": "Konto erstellen",
  "register.subtitle": "Beginne, deine Wissensbasis aufzubauen",
  "register.passwordPlaceholder": "Mindestens 6 Zeichen",
  "register.submit": "Konto erstellen",
  "register.submitA11y": "Konto mit E-Mail erstellen",
  "register.hasAccount": "Du hast bereits ein Konto?",
  "register.signInLink": "Anmelden",
  "common.goBack": "Zurück",
  "readingLanguage.title": "Lesesprache",
  "readingLanguage.selectA11y": "{language} als Lesesprache wählen",
  "readingLanguage.disclaimer":
    "Diese Einstellung wirkt sich nur auf künftige Inhalte aus. Vorhandene Zusammenfassungen und Übersetzungen werden nicht erneut verarbeitet.",
  "readingLanguage.saved": "Sprache aktualisiert",
  "readingLanguage.saveA11y": "Lesesprache speichern",
  "deleteAccount.title": "Konto löschen",
  "deleteAccount.warningTitle": "Das lässt sich nicht rückgängig machen",
  "deleteAccount.warningBody":
    "Dein Konto zu löschen, entfernt es dauerhaft, zusammen mit allem, was du gespeichert hast. Wir können es danach nicht wiederherstellen, auch nicht auf Anfrage.",
  "deleteAccount.erasedHeading": "Was gelöscht wird",
  "deleteAccount.erased.library": "Deine Bibliothek, Ordner und Tags",
  "deleteAccount.erased.artifacts":
    "Alle Transkripte, Zusammenfassungen, Notizen und Lernkarten",
  "deleteAccount.erased.schedule": "Dein Wiederholungsplan und deine Digests",
  "deleteAccount.erased.search": "Deine Suchergebnisse in der ganzen App",
  "deleteAccount.erased.identity": "Deine E-Mail-Adresse und deine Anmeldedaten",
  "deleteAccount.subscriptionHeading": "Dein Abo",
  "deleteAccount.subscriptionBodyApple":
    "Dein Konto zu löschen, kündigt dein Abo nicht. Apple berechnet dir weiterhin Gebühren, bis du es in den Einstellungen deines Stores kündigst — kündige es also zuerst dort.",
  "deleteAccount.subscriptionBodyGoogle":
    "Dein Konto zu löschen, kündigt dein Abo nicht. Google berechnet dir weiterhin Gebühren, bis du es in den Einstellungen deines Stores kündigst — kündige es also zuerst dort.",
  "deleteAccount.manageApple": "Abo im App Store verwalten",
  "deleteAccount.manageGoogle": "Abo im Play Store verwalten",
  "deleteAccount.copyHeading": "Erst eine Kopie?",
  "deleteAccount.copyBody":
    "Schreib uns, bevor du löschst, und wir senden dir innerhalb eines Monats eine Kopie deiner Daten.",
  "deleteAccount.emailA11y": "E-Mail an {address}",
  "deleteAccount.acknowledge":
    "Mir ist klar, dass mein Konto und alle meine Daten dauerhaft gelöscht werden.",
  "deleteAccount.acknowledgeA11y":
    "Mir ist klar, dass sich das nicht rückgängig machen lässt",
  "deleteAccount.submit": "Mein Konto löschen",
  "deleteAccount.submitA11y": "Mein Konto löschen",
  "deleteAccount.confirmTitle": "Konto löschen?",
  "deleteAccount.confirmBody":
    "Das löscht dein Konto und alles darin dauerhaft. Es lässt sich nicht rückgängig machen.",
  "deleteAccount.confirmAction": "Endgültig löschen",
  "account.title": "Konto",
  "account.notSet": "Nicht gesetzt",
  "account.subscription.manage": "Abo verwalten",
  "account.subscription.manageHint": "Tarif wechseln oder Kauf wiederherstellen",
  "account.subscription.viewPlans": "Tarife ansehen",
  "account.subscription.viewPlansHint": "Sieh, was jedes Abo enthält",
  "account.subscription.upgrade": "Upgrade",
  "account.subscription.upgradeHint": "Schalte mehr Audio- und Videominuten frei",
  "account.featureRequests": "Funktionswünsche",
  "account.reportBug": "Fehler melden",
  "account.signOut": "Abmelden",
  "account.signOutConfirm": "Möchtest du dich wirklich abmelden?",
  "account.signOutAction": "Ja, abmelden",
  "account.feedbackUnavailable": "Feedback nicht verfügbar",
  "account.feedbackUnavailableBody":
    "Das Feedback-Board ist noch nicht eingerichtet. Bitte versuche es später erneut.",
  "uiLanguage.title": "App-Sprache",
  "uiLanguage.disclaimer":
    "Das ist die Sprache der App selbst. Die Sprache, in der deine Zusammenfassungen und Transkripte geschrieben sind, ist die Lesesprache und wird separat eingestellt.",
  "uiLanguage.followDevice": "Meinem Gerät folgen",
  "uiLanguage.selectA11y": "{language} für die App verwenden",
  "settings.uiLanguage.restartTitle": "Neu starten, um den Wechsel abzuschließen",
  "settings.uiLanguage.restartBody":
    "Diese Sprache wird von rechts nach links gelesen, daher muss die App neu starten, damit das Layout folgt. Schließe sie und öffne sie erneut.",
  "onboarding.language.title": "Wähle deine Lesesprache",
  "onboarding.language.subtitle":
    "Inhalte werden bei Bedarf in diese Sprache übersetzt.",
  "onboarding.language.continueA11y": "Mit der gewählten Sprache fortfahren",
  "mediaType.unknownSource": "Unbekannt",
  "search.placeholder": "Durchsuche deine Bibliothek …",
  "search.clearA11y": "Suche löschen",
  "search.collections": "Sammlungen",
  "search.allMedia": "Alle Medien",
  "search.noCollections":
    "Noch keine Sammlungen. Ordne Medien beim Speichern in Sammlungen ein.",
  "search.openCollectionA11y": "Sammlung {name} öffnen",
  "search.resultCount.one": "{count} Ergebnis",
  "search.resultCount.other": "{count} Ergebnisse",
  "search.endOfResults": "Ende der Ergebnisse",
  "search.noResultsTitle": "Keine Ergebnisse",
  "search.noMatches":
    "Keine Treffer für „{query}“. Versuche andere Suchbegriffe.",
  "search.emptyLibrary": "Deine Bibliothek ist leer",
  "search.emptyLibraryHint":
    "Teile einen Link aus einer beliebigen App oder importiere eine Datei aus dem Posteingang, dann erscheint sie hier.",
  "search.failed": "Die Suche ist fehlgeschlagen",
  "search.collectionsLoadFailed": "Deine Sammlungen konnten nicht geladen werden.",
  "search.libraryLoadFailed": "Deine Bibliothek konnte nicht geladen werden.",
  "search.retryLibraryA11y": "Bibliothek erneut laden",
  "search.retryCollectionsA11y": "Sammlungen erneut laden",
  "search.retrySearchA11y": "Suche erneut ausführen",
  "tabs.home": "Start",
  "tabs.search": "Suche",
  "tabs.digest": "Digest",
  "home.loading": "Dein Posteingang wird geladen …",
  "home.retryA11y": "Posteingang erneut laden",
  "home.continueLearning": "Weiterlernen",
  "home.recentlyAdded": "Kürzlich hinzugefügt",
  "home.takePhotoA11y": "Foto aufnehmen",
  "home.unsortedReview": "Unsortiertes durchgehen",
  "home.unsortedReviewA11y": "Unsortierte Medien durchgehen, {count}",
  "home.empty": "Deine geteilten Medien erscheinen hier.",
  "home.emptyHint":
    "Teile einen Link aus einer beliebigen App oder tippe auf +, um eine Datei zu importieren oder ein Foto aufzunehmen.",
  "home.untitledCollection": "Sammlung",
  "unsortedReview.title": "Unsortiertes durchgehen",
  "unsortedReview.position": "{current} / {total}",
  "unsortedReview.positionA11y": "Quelle {current} von {total}",
  "unsortedReview.closeA11y": "Durchgehen beenden",
  "unsortedReview.loadFailed":
    "Deine unsortierten Medien konnten nicht geladen werden. Bitte versuche es erneut.",
  "unsortedReview.noBlurb": "Für dieses hier noch keine Kurzfassung.",
  "unsortedReview.discard": "Verwerfen",
  "unsortedReview.discardA11y": "{title} verwerfen",
  "unsortedReview.discardFailed":
    "Diese Quelle konnte nicht verworfen werden. Bitte versuche es erneut.",
  "unsortedReview.deepen": "Vertiefen",
  "unsortedReview.deepenA11y": "{title} öffnen",
  "unsortedReview.save": "Ablegen",
  "unsortedReview.saveA11y": "{title} in einer Sammlung ablegen",
  "unsortedReview.doneTitle": "Nichts mehr zu sortieren",
  "unsortedReview.doneBody": "Alles, was wartete, ist erledigt.",
  "digest.daily": "Täglich",
  "digest.weekly": "Wöchentlich",
  "digest.dailyTitle": "Dein Tag im Rückblick",
  "digest.weeklyTitle": "Deine Woche im Rückblick",
  "digest.dailySubtitle.one": "{count} Erkenntnis von heute",
  "digest.dailySubtitle.other": "{count} Erkenntnisse von heute",
  "digest.weeklySubtitle.one": "{count} Erkenntnis zum Durchsehen",
  "digest.weeklySubtitle.other": "{count} Erkenntnisse zum Durchsehen",
  "digest.loadFailed": "Digest konnte nicht geladen werden",
  "digest.tryAgain": "Erneut versuchen",
  "digest.emptyDaily": "Heute noch keine Erkenntnisse",
  "digest.emptyWeekly": "Diese Woche keine Erkenntnisse",
  "digest.emptyDailyHint":
    "Teile Medien in deine Bibliothek und komm später für deinen persönlichen Digest zurück.",
  "digest.emptyWeeklyHint":
    "Verarbeite im Laufe der Woche einige Medien, um hier deine Wochenübersicht zu sehen.",
  "digest.readTime.one": "{count} Min. Lesezeit",
  "digest.readTime.other": "{count} Min. Lesezeit",
  "digest.type.podcast": "Podcast",
  "digest.type.article": "Artikel",
  "digest.type.youtube": "YouTube",
  "digest.type.video": "Video",
  "digest.type.audio": "Audio",
  "digest.type.text": "Text",
  "tags.selectedCount.one": "{count} Tag",
  "tags.selectedCount.other": "{count} Tags",
  "tags.saveA11y": "Tags speichern",
  "tags.removeA11y": "{name} entfernen",
  "tags.addPlaceholder": "Tag hinzufügen",
  "tags.createA11y": "Tag „{name}“ erstellen",
  "tags.otherHeading": "WEITERE",
  "tags.loadFailed": "Tags konnten nicht geladen werden",
  "tags.createFailed": "Tag konnte nicht erstellt werden",
  "tags.saveFailed": "Tags konnten nicht gespeichert werden",
  "collectionPicker.title": "Sammlung",
  "collectionPicker.saveA11y": "Auswahl speichern",
  "collectionPicker.searchPlaceholder": "Suchen",
  "collectionPicker.unsorted": "Unsortiert",
  "collectionPicker.myCollections": "Meine Sammlungen",
  "collectionPicker.createA11y": "Neue Sammlung erstellen",
  "collectionPicker.namePlaceholder": "Name der Sammlung",
  "collectionPicker.confirm": "Bestätigen",
  "collectionPicker.collapse": "Einklappen",
  "collectionPicker.expand": "Ausklappen",
  "collectionPicker.noMatches": "Keine Sammlung passt zu deiner Suche",
  "collectionPicker.loadFailed": "Sammlungen konnten nicht geladen werden",
  "collectionPicker.saveFailed": "Sammlung konnte nicht gespeichert werden",
  "collectionPicker.createFailed": "Sammlung konnte nicht erstellt werden",
  "collections.loading": "Sammlungen werden geladen …",
  "collections.loadFailed":
    "Deine Sammlungen konnten nicht geladen werden. Bitte versuche es erneut.",
  "collections.empty": "Noch keine Sammlungen",
  "collections.emptyHint":
    "Ordne Medien beim Speichern in Sammlungen ein, um sie hier wiederzufinden.",
  "collections.emptyFolder": "Leer",
  "collections.childCount.one": "{count} Sammlung",
  "collections.childCount.other": "{count} Sammlungen",
  "media.tab.reader": "Lesen",
  "media.tab.ai": "KI",
  "media.sectionsA11y": "Medienbereiche",
  "media.loadFailed": "Die Mediendetails konnten nicht geladen werden.",
  "media.retryA11y": "Mediendetails erneut laden",
  "media.processingHint": "Das dauert meist weniger als eine Minute.",
  "media.timeoutTitle": "Das dauert länger als gewöhnlich.",
  "media.timeoutHint": "Zieh nach unten zum Aktualisieren oder komm später wieder.",
  "media.refresh": "Aktualisieren",
  "media.refreshA11y": "Medienstatus aktualisieren",
  "media.failedTitle": "Verarbeitung fehlgeschlagen",
  "media.failedFallback": "Ein unerwarteter Fehler ist aufgetreten.",
  "media.processingFailed":
    "Die Verarbeitung ist fehlgeschlagen. Bitte versuche es später erneut.",
  "media.processing.audio": "Audio wird transkribiert …",
  "media.processing.video": "Video wird transkribiert …",
  "media.processing.extracting": "Inhalt wird extrahiert …",
  "media.processing.generating": "Text wird erstellt …",
  "media.transcriptLoadFailed":
    "Das Transkript kann gerade nicht geladen werden.",
  "media.movedToNamed": "Verschoben nach „{name}“",
  "media.movedToCollection": "In eine Sammlung verschoben",
  "media.removedFromCollection": "Aus der Sammlung entfernt",
  "media.openFailed": "{host} konnte nicht geöffnet werden",
  "media.moveToCollectionA11y": "In eine Sammlung verschieben",
  "media.shareA11y": "Teilen",
  "collection.tab.sources": "Quellen",
  "collection.tab.ai": "KI",
  "collection.sectionsA11y": "Bereiche der Sammlung",
  "collection.loadFailed":
    "Diese Sammlung konnte nicht geladen werden. Bitte versuche es erneut.",
  "collection.retryA11y": "Sammlung erneut laden",
  "collection.artifactsLoadFailed":
    "Erstellte Inhalte konnten nicht geladen werden. Bitte versuche es erneut.",
  "collection.empty": "Diese Sammlung ist leer",
  "collection.emptyHint":
    "Medien, die du in dieser Sammlung speicherst, erscheinen hier.",
  "bugReport.subject": "Betreff",
  "bugReport.subjectPlaceholder": "Kurze Zusammenfassung des Problems",
  "bugReport.subjectA11y": "Betreff der Fehlermeldung",
  "bugReport.description": "Beschreibung",
  "bugReport.descriptionPlaceholder":
    "Schritte zum Reproduzieren, was du erwartet hast, was stattdessen passiert ist …",
  "bugReport.descriptionA11y": "Beschreibung der Fehlermeldung",
  "bugReport.attachment": "Anhang (optional)",
  "bugReport.attach": "Datei anhängen",
  "bugReport.attachA11y": "Eine Datei an die Fehlermeldung anhängen",
  "bugReport.attachChoose": "Wähle eine Quelle",
  "bugReport.photoLibrary": "Fotomediathek",
  "bugReport.files": "Dateien",
  "bugReport.removeFileA11y": "Angehängte Datei entfernen",
  "bugReport.submit": "Senden",
  "bugReport.submitA11y": "Fehlermeldung senden",
  "bugReport.submitting": "Meldung wird gesendet …",
  "bugReport.uploading": "Anhang wird hochgeladen …",
  "bugReport.submitted": "Meldung gesendet",
  "bugReport.ticketId": "Ticket-Nummer",
  "bugReport.doneA11y": "Fertig, zurück zum Konto",
  "bugReport.closeA11y": "Formular für Fehlermeldung schließen",
  "bugReport.submitFailed":
    "Die Fehlermeldung konnte nicht gesendet werden. Bitte versuche es erneut.",
  "bugReport.pickFileFailed":
    "Die Datei konnte nicht ausgewählt werden. Bitte versuche es erneut.",
  "bugReport.pickImageFailed":
    "Das Bild konnte nicht ausgewählt werden. Bitte versuche es erneut.",
  "bugReport.fileTypeTitle": "Dateityp nicht erlaubt",
  "bugReport.fileTypeAccepted": "Akzeptierte Dateitypen: {list}",
  "bugReport.fileTypeRejected":
    "Der gewählte Dateityp ({type}) wird nicht akzeptiert.",
  "bugReport.fileTooLargeTitle": "Datei zu groß",
  "bugReport.fileTooLarge":
    "Die maximale Dateigröße beträgt {max}. Deine Datei ist {size} groß.",
  "paywall.title": "Wähle deinen Tarif",
  "paywall.plansLoadFailed":
    "Wir konnten die Tarife nicht laden. Prüfe deine Verbindung und versuche es erneut.",
  "paywall.tryAgain": "Erneut versuchen",
  "paywall.pricesUnavailable":
    "Preise sind nicht verfügbar — der {store} bietet diese Abos gerade nicht an.",
  "paywall.selectorLabel": "Wähle deine monatliche Transkriptionszeit",
  "paywall.selectorLabelReadOnly": "Was dir jeder Tarif gibt",
  "paywall.priceUnavailableA11y": "Preis nicht verfügbar",
  "paywall.pricePerMonthA11y": "{price} pro Monat",
  "paywall.includedHeading": "In jedem Tarif enthalten",
  "paywall.showDetails": "Genau ansehen, was enthalten ist",
  "paywall.hideDetails": "Details ausblenden",
  "paywall.ctaChoose": "Tarif wählen",
  "paywall.ctaStart": "Mit {plan} starten — {price}/Mon.",
  "paywall.purchaseSuccess": "Kauf erfolgreich",
  "paywall.purchaseSuccessBody": "Dein Abo ist jetzt aktiv. Viel Freude damit!",
  "paywall.purchasePending": "Kauf ausstehend",
  "paywall.purchasePendingBody":
    "Dein Kauf wartet auf Freigabe. Du wirst benachrichtigt, sobald er abgeschlossen ist.",
  "paywall.purchaseFailed": "Kauf fehlgeschlagen",
  "paywall.unexpectedError":
    "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es erneut.",
  "paywall.renewalTerms":
    "Die Zahlung wird bei Bestätigung des Kaufs deinem {store}-Konto belastet. Das Abo verlängert sich monatlich, sofern es nicht mindestens 24 Stunden vor Ende des laufenden Zeitraums gekündigt wird, und dein Konto wird innerhalb der 24 Stunden davor für die Verlängerung belastet.",
  "paywall.terms": "Nutzungsbedingungen",
  "paywall.privacy": "Datenschutzerklärung",
  "paywall.cancelAnytime": "Jederzeit in deinem {store}-Konto kündbar.",
  "artifact.loadFailed": "Dieser erstellte Inhalt konnte nicht geladen werden.",
  "artifact.failedTitle": "Laden nicht möglich",
  "artifact.retryA11y": "Erstellten Inhalt erneut laden",
  "artifact.notReady": "Noch nicht fertig",
  "artifact.pendingBody":
    "Dieser Inhalt wird noch erstellt. Schau in einem Moment wieder vorbei.",
  "artifact.refreshA11y": "Erstellten Inhalt aktualisieren",
  "artifact.generationFailedTitle": "Erstellung fehlgeschlagen",
  "artifact.generationFailedBody":
    "Dieser Inhalt konnte nicht erstellt werden, und es läuft nichts mehr. Starte die Erstellung erneut, um es zu versuchen.",
  "artifact.regenerate": "Erneut erstellen",
  "artifact.regenerateA11y": "Diesen Inhalt erneut erstellen",
  "artifact.regenerating": "Wird gestartet...",
  "artifact.regenerationQueued":
    "Erstellung neu gestartet. Schau in einem Moment wieder vorbei.",
  "artifact.anotherLanguage": "eine andere Sprache",
  "artifact.translatedFrom": "Übersetzt aus dem {language}",
  "artifact.translationFailed":
    "Übersetzung nicht verfügbar — angezeigt auf {language}",
  "artifact.translationFailedA11y":
    "Übersetzung nicht verfügbar. Dieser Inhalt wird in seiner Originalsprache angezeigt, {language}.",
  "artifact.section.keyPoints": "Kernpunkte",
  "artifact.section.takeaway": "Fazit",
  "artifact.section.context": "Kontext",
  "artifact.section.mainTopics": "Hauptthemen",
  "artifact.section.quotes": "Bemerkenswerte Zitate",
  "artifact.section.conclusion": "Schluss",
  "artifact.section.objectives": "Ziele",
  "artifact.section.concepts": "Konzepte",
  "artifact.section.actionItems": "Aufgaben",
  "artifact.section.glossary": "Glossar",
  "artifact.noFlashcards": "Keine Lernkarten in diesem Inhalt.",
  "artifact.cardCount.one": "{count} Karte",
  "artifact.cardCount.other": "{count} Karten",
  "artifact.question": "FRAGE",
  "artifact.answer": "ANTWORT",
  "artifact.tapToReveal": "Zum Aufdecken tippen",
  "artifact.revealAnswerA11y": "Tippe, um die Antwort aufzudecken",
  "artifact.hideAnswer": "Antwort ausblenden",
  "artifact.noQuestions": "Keine Fragen in diesem Inhalt.",
  "artifact.quizProgress": "Quiz-Fortschritt",
  "artifact.questionPosition": "Frage {index} von {total}",
  "artifact.quizComplete": "Quiz abgeschlossen",
  "artifact.explanation": "ERKLÄRUNG",
  "artifact.optionA11y": "Option {label}: {text}{state}",
  "share.title.url": "Link speichern",
  "share.title.text": "Text speichern",
  "share.title.audio": "Audio speichern",
  "share.title.file": "Datei importieren",
  "share.title.photo": "Foto speichern",
  "share.processing": "Geteilter Inhalt wird verarbeitet …",
  "share.invalid": "Dieser Inhalt kann nicht gespeichert werden",
  "share.saved": "Gespeichert!",
  "share.saveFailed": "Speichern fehlgeschlagen",
  "share.saving": "Wird gespeichert …",
  "share.uploadingAudio": "Audio wird hochgeladen …",
  "share.uploadingFile": "Datei wird hochgeladen …",
  "share.whatsappText": "WhatsApp-Textnachricht",
  "share.tags": "Tags",
  "share.chooseCollection": "Sammlung wählen",
  "share.chooseTags": "Tags wählen",
  "share.success.duplicate": "Dieser Inhalt war schon in deinem Posteingang.",
  "share.success.audio":
    "Audio gespeichert. Die Transkription beginnt in Kürze.",
  "share.success.text": "Text in deinem Posteingang gespeichert.",
  "share.success.photo":
    "Foto importiert. Die Texterkennung beginnt in Kürze.",
  "share.success.audioFile":
    "Audiodatei importiert. Die Transkription beginnt in Kürze.",
  "share.success.file": "Datei importiert. Die Verarbeitung beginnt in Kürze.",
  "share.success.url":
    "Link zu deinem Posteingang hinzugefügt. Die Verarbeitung beginnt in Kürze.",
  "import.filesUnavailable": "Deine Dateien konnten nicht geöffnet werden",
  "import.filesUnavailableBody":
    "Der Dateibrowser konnte nicht geöffnet werden. Bitte versuche es erneut.",
  "import.formatNotSupported": "Format nicht unterstützt",
  "import.cameraUnavailable": "Kamera nicht verfügbar",
  "import.cameraUnavailableBody":
    "Die Kamera konnte auf diesem Gerät nicht gestartet werden.",
  "import.cameraPermission": "Kamerazugriff erforderlich",
  "import.cameraPermissionAsk":
    "Erlaube den Kamerazugriff, um ein Dokument oder eine Seite zum Importieren aufzunehmen.",
  "import.cameraPermissionSettings":
    "Der Kamerazugriff ist deaktiviert. Aktiviere ihn für diese App in den Geräteeinstellungen, um ein Dokument aufzunehmen.",
  "import.galleryUnavailable": "Galerie nicht verfügbar",
  "import.galleryUnavailableBody":
    "Deine Fotogalerie konnte nicht geöffnet werden. Bitte versuche es erneut.",
  "import.photoTooLarge": "Foto zu groß",
  "import.photoNotSupported": "Foto nicht unterstützt",
  "upload.reject.extension":
    "Dateien mit der Endung .{extension} können nicht importiert werden. Unterstützte Formate: {formats}.",
  "upload.reject.noExtension":
    "Diese Datei hat keine erkennbare Endung. Unterstützte Formate: {formats}.",
  "upload.reject.empty": "Diese Datei ist leer, es gibt also nichts zu importieren.",
  "upload.reject.tooLarge":
    "Diese Datei ist {size} groß, über dem Limit von {max} für einen einzelnen Import.",
  "upload.transferFailed":
    "Diese Datei konnte nicht gesendet werden. Prüfe deine Verbindung und versuche es erneut.",
  "home.loadFailed":
    "Dein Posteingang konnte nicht geladen werden. Bitte versuche es erneut.",
  "share.unsupportedFile": "Dieser Dateityp wird noch nicht unterstützt.",
  "share.signInLinks": "Du musst angemeldet sein, um Links zu speichern.",
  "share.signInContent": "Du musst angemeldet sein, um Inhalte zu speichern.",
  "share.signInFiles": "Du musst angemeldet sein, um Dateien zu importieren.",
  "transcript.translating": "Transkript wird übersetzt …",
  "transcript.translationFailed":
    "Die Übersetzung ist fehlgeschlagen. Es wird das Originaltranskript angezeigt.",
  "paywall.subtitle":
    "Jeder Tarif kann alles. Nur die monatliche Transkriptionszeit ändert sich.",
  "startupError.title": "Die App konnte nicht starten",
  "startupError.body":
    "Ein unerwarteter Fehler hat den Start der App unterbrochen. Ein neuer Versuch genügt meistens.",
  "startupError.retryA11y": "Erneut versuchen, die App zu starten",
  "startupError.showDetails": "Technische Details anzeigen",
  "startupError.hideDetails": "Technische Details ausblenden",
};
