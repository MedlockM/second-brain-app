import type { Catalog } from "./runtime";

/** German catalogue. See `en` for the reference wording and the key layout. */
export const de: Catalog = {
  "common.ok": "OK",
  "common.yes": "Ja",
  "common.no": "Nein",
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
  "home.tile.a11yFolder": "Ordner {name}, {count}",
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

  // --- Markierung für fehlgeschlagenen Import, für Liste und Kachel ---
  "mediaStatus.failedBadge": "FEHLER",
  "mediaStatus.a11yFailed": "{label}. Import fehlgeschlagen.",
  "mediaActions.move.label": "Verschieben",
  "mediaActions.rename.label": "Umbenennen",
  "mediaActions.delete.label": "Löschen",
  "mediaActions.moreA11y": "Aktionen für diese Quelle",
  "mediaActions.rename.title": "Diese Quelle umbenennen",
  "mediaActions.rename.placeholder": "Name der Quelle",
  "mediaActions.renameFailed":
    "Diese Quelle konnte nicht umbenannt werden. Ihr Name ist unverändert.",
  "mediaActions.deleteTitle": "Diese Quelle löschen?",
  "mediaActions.deleteBody":
    "„{title}“ wird aus deiner Bibliothek entfernt. Das lässt sich nicht rückgängig machen.",
  "mediaActions.deleteFailed":
    "Diese Quelle konnte nicht gelöscht werden. Sie ist weiterhin in deiner Bibliothek.",
  "folderActions.longPressHint":
    "Zweimal tippen und halten, um diesen Ordner umzubenennen oder zu löschen",
  "folderActions.rename.label": "Umbenennen",
  "folderActions.delete.label": "Löschen",
  "folderActions.moreA11y": "Aktionen für diesen Ordner",
  "folderActions.rename.title": "Diesen Ordner umbenennen",
  "folderActions.rename.placeholder": "Name des Ordners",
  "folderActions.renameFailed":
    "Dieser Ordner konnte nicht umbenannt werden. Sein Name ist unverändert.",
  "folderActions.deleteTitle": "Diesen Ordner löschen?",
  "folderActions.deleteBody":
    "„{name}“ wird gelöscht. Alle darin enthaltenen Quellen wandern nach {unsorted} – keine davon wird gelöscht.",
  "folderActions.deleteSubfolders.one":
    "Sein Unterordner wird ebenfalls gelöscht, und die Quellen darin wandern ebenfalls nach {unsorted}.",
  "folderActions.deleteSubfolders.other":
    "Seine {count} Unterordner werden ebenfalls gelöscht, und die Quellen darin wandern ebenfalls nach {unsorted}.",
  "folderActions.deleteFailed":
    "Dieser Ordner konnte nicht gelöscht werden. Er ist weiterhin in deiner Bibliothek.",
  "addSource.title": "Zu deinem Posteingang hinzufügen",
  "addSource.enterUrl.label": "Link einfügen",
  "addSource.enterUrl.description":
    "Ein Artikel, ein Video oder eine Podcast-Folge — von überall im Web.",
  "addUrl.title": "Link hinzufügen",
  "addUrl.placeholder": "https://",
  "addUrl.hint":
    "Die Verarbeitung startet, sobald du ihn hinzufügst. Den Ordner wählst du danach.",
  "addUrl.submit": "Hinzufügen",
  "addUrl.error.invalid":
    "In deiner Eingabe wurde kein Link gefunden. Füge eine Webadresse wie https://beispiel.de/artikel ein.",
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
  "mediaError.mediaUnavailable": "Dieses Medium ist an seiner Quelle nicht mehr verfügbar.",
  "mediaError.geoRestricted": "Dieses Medium ist in der Region, aus der wir importieren, nicht verfügbar.",
  "mediaError.ageRestricted": "Dieses Medium ist durch eine Altersprüfung geschützt, die wir nicht passieren können.",
  "mediaError.liveContentUnsupported": "Live-Inhalte lassen sich nicht importieren. Versuche es erneut, sobald die Aufzeichnung veröffentlicht ist.",
  "mediaError.imagePostUnsupported": "Dieser Beitrag ist ein Foto – es gibt nichts zu transkribieren.",
  "mediaError.noTranscribableMedia": "Dieser Link enthält weder Audio noch Video noch Untertitel, mit denen wir arbeiten können.",
  "mediaError.noTranscriptAvailable": "Für dieses Medium war kein Transkript zu bekommen.",
  "mediaError.postTextEmpty": "Dieser Beitrag enthält keinen Text zum Speichern.",
  "mediaError.notAnArticlePage": "Dieser Link führt nicht zu einem lesbaren Artikel.",
  "mediaError.articleTextNotFound": "Wir konnten den Text dieses Artikels nicht lesen.",
  "mediaError.documentParseFailed": "Dieses Dokument war nicht lesbar. Versuche eine andere Datei oder ein anderes Format.",
  "mediaError.providerUnavailable": "Die Quelle war nicht erreichbar. Bitte versuche es später erneut.",
  "mediaError.providerResultInvalid": "Der Import kam unbrauchbar zurück. Bitte versuche es später erneut.",
  "mediaError.providerRateLimited": "Die Quelle bremst uns gerade aus. Bitte versuche es in einigen Minuten erneut.",
  "mediaError.providerTimedOut": "Der Import hat zu lange gedauert. Bitte versuche es erneut.",
  "mediaError.serviceUnavailable": "Importe sind vorübergehend nicht verfügbar. Wir kümmern uns darum.",
  "mediaError.itemTooLong": "Dieses Element ist länger, als dein Tarif in einem Import erlaubt.",
  "mediaError.internal": "Bei uns ist etwas schiefgelaufen. Versuche den Import bitte noch einmal.",

  // --- Unterstützung für die Quelle eines nicht importierbaren Mediums anfragen ---
  // Die letzten zwei Schlüssel erscheinen nicht auf dem Bildschirm: Sie sind
  // Betreff und Text der gesendeten Meldung.
  "sourceRequest.title": "Diese Medienquelle wird noch nicht unterstützt.",
  "sourceRequest.intro": "Wenn du möchtest, dass sie es eines Tages wird:",
  "sourceRequest.action": "Diese Quelle anfragen",
  "sourceRequest.actionA11y": "Uns um Unterstützung für diese Quelle bitten",
  "sourceRequest.sending": "Wird gesendet...",
  "sourceRequest.sent": "Anfrage gesendet. Danke!",
  "sourceRequest.reportSubject": "Anfrage zur Unterstützung einer Quelle",
  "sourceRequest.reportDescription":
    "Vom Fehlerbildschirm eines gespeicherten Mediums gesendet: Diese Person möchte, dass wir seine Quelle unterstützen.",

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
  "artifacts.refusal.folderEmpty":
    "Dieser Ordner hat noch keine Quelle mit Transkript. Füge Medien hinzu oder warte, bis die gespeicherten fertig verarbeitet sind.",
  "artifacts.refusal.mediaEmpty":
    "Dieses Element hat noch kein Transkript, also gibt es nichts, woraus etwas erstellt werden könnte.",
  "artifacts.refusal.tooManySources":
    "Dieser Ordner hat {count} Quellen, mehr als die {max}, die eine einzelne Erstellung lesen kann. Erstelle es auf einem kleineren Unterordner.",
  "artifacts.refusal.tooMuchText":
    "Hier ist zu viel Text für eine einzelne Erstellung. Erstelle es auf einem kleineren Unterordner.",
  "artifacts.refusal.translationFailed":
    "Dieses Transkript konnte nicht übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.sourcesTranslationFailed.one":
    "Die einzige Quelle hier konnte nicht übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.sourcesTranslationFailed.other":
    "Keine dieser {count} Quellen konnte übersetzt werden, und das wird nicht automatisch wiederholt. Versuche es später erneut.",
  "artifacts.refusal.generic":
    "Diese Erstellung konnte nicht gestartet werden. Bitte versuche es erneut.",
  "plan.hourlyRate": "≈ {price} pro Stunde",
  "plan.card.allowance": "{duration} pro Monat",
  "plan.card.perImport": "bis zu {duration} pro Sendung",
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
    "Minuten decken das Audio und Video ab, das du sendest. Artikel und Webseiten kosten keine, und deine Bibliothek zu lesen ist unbegrenzt.",
  "plan.list.separator": ", ",
  "plan.list.lastConjunction": "{list} und {last}",
  "plan.source.web": "Artikel & Webseiten",
  "plan.source.audioUrl": "Jeder Audio-Link",
  "plan.source.notes": "Notizen",
  "plan.cost.free.label": "Artikel, Webseiten, X-Posts",
  "plan.cost.captions.label": "Ein YouTube-Video, egal wie lang",
  "plan.cost.transcript.label": "Ein Podcast, der seinen Text schon mitliefert",
  "plan.cost.duration.label": "Audio, Video, Reels, Sprachnachrichten",
  "plan.cost.document.label": "Ein Dokument oder das Foto einer Seite",
  "plan.cost.textFile.label": "Eine Notiz oder eine Textdatei",
  "plan.cost.folder.label": "Eine Generierung über einen ganzen Ordner",
  "plan.cost.value.free": "Kostenlos",
  "plan.cost.value.realLength": "Die tatsächliche Länge",
  "plan.cost.value.perPages": "eine Minute pro {pages} Seiten",
  "plan.cost.value.perSources": "eine Minute pro {sources} Elemente",
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
  "preview.heading": "Vorschau",
  "preview.pending": "Die Vorschau wird geschrieben …",
  "preview.unavailable": "Keine Vorschau für diese Quelle.",
  "transcript.heading": "Volltext",
  "transcript.empty": "Noch kein Text verfügbar.",
  "transcript.emptyHint":
    "Der Text erscheint, sobald die Verarbeitung abgeschlossen ist.",
  "transcript.status.pending": "Die Aufbereitung des Textes beginnt in Kürze.",
  "transcript.status.extracting": "Audioinhalt wird extrahiert …",
  "transcript.status.transcribing": "Audio wird in Text umgewandelt …",
  "transcript.status.ready": "Der Text ist fertig.",
  "transcript.status.failed": "Die Aufbereitung des Textes ist fehlgeschlagen.",
  "transcript.paragraphCount.one": "{count} Absatz",
  "transcript.paragraphCount.other": "{count} Absätze",
  "transcript.loading": "Text wird geladen …",
  "transcript.notAvailable":
    "Der Volltext ist für dieses Element nicht verfügbar.",
  "transcript.retryA11y": "Text erneut laden",
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
  "readingLanguage.changeLimit":
    "Du kannst die Lesesprache einmal im Monat ändern. Die nächste Änderung ist ab dem {date} möglich.",
  "readingLanguage.changeLimitNoDate":
    "Du kannst die Lesesprache einmal im Monat ändern, und die Änderung dieses Monats ist bereits verbraucht.",
  "deleteAccount.title": "Konto löschen",
  "deleteAccount.warningTitle": "Das lässt sich nicht rückgängig machen",
  "deleteAccount.warningBody":
    "Dein Konto zu löschen, entfernt es dauerhaft, zusammen mit allem, was du gespeichert hast. Wir können es danach nicht wiederherstellen, auch nicht auf Anfrage.",
  "deleteAccount.erasedHeading": "Was gelöscht wird",
  "deleteAccount.erased.library": "Deine Bibliothek und Ordner",
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
  "account.subscription.manage": "Tarif wechseln",
  "account.subscription.manageHint": "Tarife vergleichen und wechseln",
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
  "search.placeholder": "Durchsuche deine Bibliothek …",
  "search.clearA11y": "Suche löschen",
  "search.folders": "Ordner",
  "search.allMedia": "Alle Medien",
  "search.noFolders":
    "Noch keine Ordner. Ordne Medien beim Speichern in Ordner ein.",
  "search.openFolderA11y": "Ordner {name} öffnen",
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
  "search.foldersLoadFailed": "Deine Ordner konnten nicht geladen werden.",
  "search.libraryLoadFailed": "Deine Bibliothek konnte nicht geladen werden.",
  "search.retryLibraryA11y": "Bibliothek erneut laden",
  "search.retryFoldersA11y": "Ordner erneut laden",
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
  "home.untitledFolder": "Ordner",
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
  "unsortedReview.saveA11y": "{title} in einem Ordner ablegen",
  "unsortedReview.doneTitle": "Nichts mehr zu sortieren",
  "unsortedReview.doneBody": "Alles, was wartete, ist erledigt.",
  "digest.daily": "Täglich",
  "digest.weekly": "Wöchentlich",
  "digest.dailyTitle": "Dein Tag im Rückblick",
  "digest.weeklyTitle": "Deine Woche im Rückblick",
  "digest.position": "{current} / {total}",
  "digest.positionA11y": "Medium {current} von {total}",
  "digest.loadFailed": "Digest konnte nicht geladen werden",
  "digest.tryAgain": "Erneut versuchen",
  "digest.emptyDaily": "Heute nichts zum Durchsehen",
  "digest.emptyWeekly": "Diese Woche nichts zum Durchsehen",
  "digest.emptyDailyHint":
    "Was du speicherst, erscheint hier im nächsten Digest.",
  "digest.emptyWeeklyHint":
    "Was du diese Woche speicherst, erscheint hier am Montag.",
  "folderPicker.title": "Ordner",
  "folderPicker.saveA11y": "Auswahl speichern",
  "folderPicker.searchPlaceholder": "Suchen",
  "folderPicker.unsorted": "Unsortiert",
  "folderPicker.myFolders": "Meine Ordner",
  "folderPicker.createA11y": "Neuen Ordner erstellen",
  "folderPicker.namePlaceholder": "Name des Ordners",
  "folderPicker.confirm": "Bestätigen",
  "folderPicker.collapse": "Einklappen",
  "folderPicker.expand": "Ausklappen",
  "folderPicker.noMatches": "Kein Ordner passt zu deiner Suche",
  "folderPicker.loadFailed": "Ordner konnten nicht geladen werden",
  "folderPicker.saveFailed": "Ordner konnte nicht gespeichert werden",
  "folderPicker.createFailed": "Ordner konnte nicht erstellt werden",
  "folders.loading": "Ordner werden geladen …",
  "folders.loadFailed":
    "Deine Ordner konnten nicht geladen werden. Bitte versuche es erneut.",
  "folders.empty": "Noch keine Ordner",
  "folders.emptyHint":
    "Ordne Medien beim Speichern in Ordner ein, um sie hier wiederzufinden.",
  "folders.emptySubtitle": "Leer",
  "folders.childCount.one": "{count} Ordner",
  "folders.childCount.other": "{count} Ordner",
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
  "media.processing.audio": "Audio wird transkribiert …",
  "media.processing.video": "Video wird transkribiert …",
  "media.processing.extracting": "Inhalt wird extrahiert …",
  "media.processing.generating": "Text wird erstellt …",
  "media.transcriptLoadFailed": "Der Text kann gerade nicht geladen werden.",
  "media.movedToNamed": "Verschoben nach „{name}“",
  "media.movedToFolder": "In einen Ordner verschoben",
  "media.removedFromFolder": "Aus dem Ordner entfernt",
  "media.openFailed": "{host} konnte nicht geöffnet werden",
  "media.moveToFolderA11y": "In einen Ordner verschieben",
  "folder.tab.sources": "Quellen",
  "folder.tab.ai": "KI",
  "folder.sectionsA11y": "Bereiche des Ordners",
  "folder.loadFailed":
    "Dieser Ordner konnte nicht geladen werden. Bitte versuche es erneut.",
  "folder.retryA11y": "Ordner erneut laden",
  "folder.artifactsLoadFailed":
    "Erstellte Inhalte konnten nicht geladen werden. Bitte versuche es erneut.",
  "folder.empty": "Dieser Ordner ist leer",
  "folder.emptyHint":
    "Medien, die du in diesem Ordner speicherst, erscheinen hier.",
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
  "paywall.selectorLabel": "Wähle, wie viel du pro Monat sendest",
  "paywall.selectorLabelReadOnly": "Was dir jeder Tarif gibt",
  "paywall.priceUnavailableA11y": "Preis nicht verfügbar",
  "paywall.pricePerMonthA11y": "{price} pro Monat",
  "paywall.promise":
    "Alles, was du sendest, kommt als Text zurück – zum Lesen, Suchen und Behalten.",
  "paywall.pricePeriod": "/Mon.",
  "paywall.sourcesHeading": "Was du senden kannst",
  "paywall.filesHeading": "Dateien von deinem Handy",
  "paywall.costHeading": "Was es an Minuten kostet",
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
  "share.inProgress.body": "Dein Inhalt wird in deinem zweiten Gehirn gespeichert.",
  "share.inProgress.duplicate": "Dieser Inhalt ist schon in deinem zweiten Gehirn.",
  "share.inProgress.question": "Möchtest du ihn außerdem in einem Ordner ablegen?",
  "share.processing": "Geteilter Inhalt wird verarbeitet …",
  "share.invalid": "Dieser Inhalt kann nicht gespeichert werden",
  "share.saveFailed": "Speichern fehlgeschlagen",
  "share.reject.noText":
    "Diese Notiz enthält keinen Text zum Speichern. Wenn sie gesperrt ist, entsperre sie und teile sie erneut.",
  "share.reject.tooLong":
    "Diese Notiz ist zu lang zum Speichern: {count} Zeichen, das Maximum liegt bei {max}.",
  "share.reject.nothingToSave":
    "Hier ist nichts, das wir speichern können. Teile stattdessen den Text der Notiz.",
  "share.folderFailed":
    "Der Ordner konnte nicht übernommen werden. Dein Inhalt ist gespeichert, und du kannst ihn aus deiner Bibliothek ablegen.",
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
  "upload.diagnostics.title": "Technische Details",
  "upload.diagnostics.hint":
    "Füge diese Zeile bei, wenn du das Problem meldest – sie nennt den Schritt, der fehlgeschlagen ist.",
  "home.loadFailed":
    "Dein Posteingang konnte nicht geladen werden. Bitte versuche es erneut.",
  "share.unsupportedFile": "Dieser Dateityp wird noch nicht unterstützt.",
  "share.signInLinks": "Du musst angemeldet sein, um Links zu speichern.",
  "share.signInContent": "Du musst angemeldet sein, um Inhalte zu speichern.",
  "share.signInFiles": "Du musst angemeldet sein, um Dateien zu importieren.",
  "transcript.translating": "Text wird übersetzt …",
  "transcript.translationFailed":
    "Die Übersetzung ist fehlgeschlagen. Es wird der Originaltext angezeigt.",
  "paywall.subtitle":
    "Jeder Tarif kann alles. Sie unterscheiden sich nur darin, wie viel du sendest.",
  "startupError.title": "Die App konnte nicht starten",
  "startupError.body":
    "Ein unerwarteter Fehler hat den Start der App unterbrochen. Ein neuer Versuch genügt meistens.",
  "startupError.retryA11y": "Erneut versuchen, die App zu starten",
  "startupError.showDetails": "Technische Details anzeigen",
  "startupError.hideDetails": "Technische Details ausblenden",
};
