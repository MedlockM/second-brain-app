import type { Catalog } from "./runtime";

/** Spanish catalogue. See `en` for the reference wording and the key layout. */
export const es: Catalog = {
  "common.ok": "OK",
  "common.cancel": "Cancelar",
  "common.retry": "Reintentar",
  "common.delete": "Eliminar",
  "common.save": "Guardar",
  "common.done": "Listo",
  "common.close": "Cerrar",
  "common.dismiss": "Descartar",
  "common.loading": "Cargando…",
  "common.continue": "Continuar",
  "common.back": "Atrás",
  "common.error": "Error",
  "common.untitled": "Sin título",
  "common.somethingWentWrong": "Algo ha salido mal",
  "common.itemCount.one": "{count} elemento",
  "common.itemCount.other": "{count} elementos",
  "trial.badge": "Prueba gratuita",
  "trial.lastDay": "Prueba gratuita - último día",
  "trial.daysLeft.one": "Prueba gratuita - queda {count} día",
  "trial.daysLeft.other": "Prueba gratuita - quedan {count} días",
  "home.tile.saving": "Guardando…",
  "home.tile.saveFailed": "No se ha podido guardar",
  "home.tile.a11yCollection": "Colección {name}, {count}",
  "home.tile.a11ySaving": "{url}, guardándose",
  "home.tile.a11ySaveFailed": "{url} no se ha podido guardar",
  "home.tile.a11yByCreator": "{title} de {creator}",
  "quota.warning.trial":
    "Has usado el {percent} % de los minutos de tu prueba gratuita.",
  "quota.warning.trialWithDate":
    "Has usado el {percent} % de los minutos de tu prueba gratuita. No se recargan: tu prueba termina el {date}.",
  "quota.warning.monthly": "Has usado el {percent} % de los minutos de este mes.",
  "quota.warning.monthlyWithDate":
    "Has usado el {percent} % de los minutos de este mes. Se recargan el {date}.",
  "quota.seePlans": "Ver planes",
  "quota.dismissWarning": "Descartar el aviso de minutos",
  "artifacts.sourceCount.one": "{count} fuente",
  "artifacts.sourceCount.other": "{count} fuentes",
  "artifacts.status.queued": "En cola",
  "artifacts.status.generating": "Generando…",
  "artifacts.status.failed": "Error",
  "artifacts.status.generated": "Generado",
  "artifacts.history.a11yRow": "{type}: {title}",
  "mediaType.podcast": "PÓDCAST",
  "mediaType.article": "ARTÍCULO",
  "mediaType.video": "VÍDEO",
  "mediaType.short": "CORTO",
  "mediaType.audio": "AUDIO",
  "mediaType.text": "TEXTO",
  "mediaType.document": "DOC",
  "mediaType.link": "ENLACE",
  "mediaCard.a11yByCreator": "{title} de {creator}, {type}",
  "mediaCard.a11yFromDomain": "{title}, {type} de {domain}",
  "mediaCard.longPressHint":
    "Toca dos veces y mantén para mover, renombrar o eliminar esta fuente",
  "mediaActions.move.label": "Mover",
  "mediaActions.rename.label": "Renombrar",
  "mediaActions.delete.label": "Eliminar",
  "mediaActions.rename.title": "Renombrar esta fuente",
  "mediaActions.rename.placeholder": "Nombre de la fuente",
  "mediaActions.renameFailed":
    "No se pudo renombrar esta fuente. Su nombre no ha cambiado.",
  "mediaActions.deleteTitle": "¿Eliminar esta fuente?",
  "mediaActions.deleteBody":
    "«{title}» se quitará de tu biblioteca. Esta acción no se puede deshacer.",
  "mediaActions.deleteFailed":
    "No se pudo eliminar esta fuente. Sigue en tu biblioteca.",
  "addSource.title": "Añadir a tu bandeja",
  "addSource.importFile.label": "Importar un archivo",
  "addSource.importFile.description":
    "Un PDF, un documento de Office, una imagen o un archivo de audio de tu teléfono.",
  "addSource.importPhoto.label": "Importar una foto",
  "addSource.importPhoto.description":
    "Elige una foto que ya tengas en tu galería.",
  "auth.or": "o",
  "auth.continueWithGoogle": "Continuar con Google",
  "auth.signInWithApple": "Iniciar sesión con Apple",
  "auth.google.notCompleted":
    "El inicio de sesión con Google no se ha completado. Inténtalo de nuevo.",
  "auth.google.noIdToken":
    "No se ha podido obtener el token de identificación de Google. Inténtalo de nuevo.",
  "auth.google.noGoogleAccount":
    "No hay ninguna cuenta de Google en este dispositivo. Añade una en los ajustes del dispositivo e inténtalo de nuevo.",
  "auth.google.failed":
    "El inicio de sesión con Google no se ha podido completar. Inténtalo de nuevo.",
  "auth.apple.noIdentityToken":
    "No se ha podido obtener el token de identidad de Apple. Inténtalo de nuevo.",
  "artifacts.type.summaryShort": "Resumen",
  "artifacts.type.summaryDetailed": "Resumen detallado",
  "artifacts.type.notes": "Apuntes",
  "artifacts.type.flashcards": "Tarjetas de memoria",
  "artifacts.type.quiz": "Cuestionario",
  "artifacts.generate": "Generar",
  "artifacts.a11yGenerate": "Generar {label}",
  "artifacts.processing": "Procesando…",
  "artifacts.panel.generateHeading": "Generar",
  "artifacts.panel.generatedHeading": "Generado",
  "artifacts.panel.retryA11y": "Reintentar la carga del contenido generado",
  "artifacts.panel.empty":
    "Aún no hay nada generado. Elige un formato arriba para crear uno.",
  "duration.minutes.one": "{count} min",
  "duration.minutes.other": "{count} min",
  "duration.hours.one": "{count} h",
  "duration.hours.other": "{count} h",
  "duration.hoursMinutes": "{hours} {minutes}",
  "time.justNow": "Ahora mismo",
  "time.minutesAgo.one": "hace {count} min",
  "time.minutesAgo.other": "hace {count} min",
  "time.hoursAgo.one": "hace {count} h",
  "time.hoursAgo.other": "hace {count} h",
  "time.yesterday": "Ayer",
  "time.today": "Hoy",
  "time.daysAgo.one": "hace {count} d",
  "time.daysAgo.other": "hace {count} d",
  "subscription.resetLabel.trialEnds": "FIN DE LA PRUEBA",
  "subscription.resetLabel.resets": "SE RECARGA",
  "subscription.resetLabel.ends": "TERMINA",
  "subscription.resetLabel.periodEnds": "FIN DEL PERIODO",
  "subscription.status.paymentIssue": "Problema de pago",
  "subscription.status.cancelled": "Cancelada",
  "error.sessionExpired": "Tu sesión ha caducado. Vuelve a iniciar sesión.",
  "error.invalidCredentials":
    "Correo o contraseña incorrectos. Inténtalo de nuevo.",
  "error.emailNotVerified":
    "Verifica tu dirección de correo antes de iniciar sesión.",
  "error.emailAlreadyExists": "Ya existe una cuenta con este correo.",
  "error.invalidVerificationToken":
    "Enlace de verificación no válido. Solicita uno nuevo.",
  "error.userNotFound":
    "No se ha encontrado ninguna cuenta con este correo. Comprueba la dirección o crea una cuenta.",
  "error.notAuthorized": "No tienes permiso para realizar esta acción.",
  "error.notFound": "Contenido no encontrado. Prueba con otra búsqueda.",
  "error.mediaNotFound": "Este medio no se ha encontrado o ya no está disponible.",
  "error.artifactNotFound":
    "Este contenido generado no se ha encontrado o ya no está disponible.",
  "error.invalidUrl": "Este enlace no es válido. Prueba con otra URL.",
  "error.unsupportedUrl":
    "Este enlace aún no es compatible. Prueba con otra fuente.",
  "error.validation": "Rellena todos los campos obligatorios.",
  "error.rateLimited": "Demasiadas solicitudes. Espera un momento e inténtalo de nuevo.",
  "error.conflict":
    "Esta acción entra en conflicto con datos existentes. Actualiza e inténtalo de nuevo.",
  "error.badRequest": "Revisa lo que has escrito e inténtalo de nuevo.",
  "error.invalidEmail": "Introduce una dirección de correo válida.",
  "error.passwordTooShort":
    "La contraseña debe tener al menos 8 caracteres.",
  "error.passwordsDoNotMatch":
    "Las contraseñas no coinciden. Inténtalo de nuevo.",
  "error.network": "Error de red. Comprueba tu conexión e inténtalo de nuevo.",
  "error.timeout": "La solicitud ha caducado. Inténtalo de nuevo.",
  "error.outOfMinutes":
    "Te has quedado sin minutos en este periodo. Mejora tu plan para seguir importando audio y vídeo.",
  "quota.title.outOfMinutes": "Sin minutos",
  "quota.title.itemTooLong": "Demasiado largo para una importación",
  "quota.refusal.noPlan":
    "Tu plan ha terminado. Suscríbete para seguir guardando en tu biblioteca.",
  "quota.refusal.outOfMinutes":
    "Te has quedado sin minutos en este periodo. Mejora tu plan para procesarlo ahora.",
  "quota.refusal.outOfMinutesUntil":
    "Te has quedado sin minutos hasta el {date}. Mejora tu plan para procesarlo ahora.",
  "quota.refusal.needsMore":
    "Esta importación necesita {needed} y te quedan {remaining} hasta el {date}. Mejora tu plan para procesarla ahora.",
  "quota.refusal.needsMoreNoDate":
    "Esta importación necesita {needed} y te quedan {remaining}. Mejora tu plan para procesarla ahora.",
  "quota.refusal.itemTooLong":
    "Esto dura {duration}, por encima de los {max} que puede usar una sola importación en tu plan. Divídelo en partes más cortas.",
  "quota.refusal.itemTooLongGeneric":
    "Es demasiado largo para una sola importación en tu plan. Divídelo en partes más cortas.",
  "artifacts.refusal.collectionEmpty":
    "Esta colección aún no tiene ninguna fuente con transcripción. Añade medios o espera a que terminen de procesarse los que has guardado.",
  "artifacts.refusal.mediaEmpty":
    "Este elemento aún no tiene transcripción, así que no hay nada a partir de lo que generar.",
  "artifacts.refusal.tooManySources":
    "Esta colección tiene {count} fuentes, por encima de las {max} que puede leer una sola generación. Genera sobre una subcolección más pequeña.",
  "artifacts.refusal.tooMuchText":
    "Hay demasiado texto aquí para una sola generación. Genera sobre una subcolección más pequeña.",
  "artifacts.refusal.sourcesPending.one":
    "{count} fuente aún se está preparando. Inténtalo de nuevo en un momento.",
  "artifacts.refusal.sourcesPending.other":
    "{count} fuentes aún se están preparando. Inténtalo de nuevo en un momento.",
  "artifacts.refusal.transcriptPending":
    "La transcripción aún se está preparando. Inténtalo de nuevo en un momento.",
  "artifacts.refusal.translationFailed":
    "No se ha podido traducir esta transcripción, y no se reintentará automáticamente. Inténtalo más tarde.",
  "artifacts.refusal.sourcesTranslationFailed.one":
    "La única fuente que hay aquí no se ha podido traducir, y no se reintentará automáticamente. Inténtalo más tarde.",
  "artifacts.refusal.sourcesTranslationFailed.other":
    "No se ha podido traducir ninguna de estas {count} fuentes, y no se reintentará automáticamente. Inténtalo más tarde.",
  "artifacts.refusal.generic":
    "No se ha podido iniciar esta generación. Inténtalo de nuevo.",
  "plan.hourlyRate": "≈ {price} por hora",
  "plan.card.allowance": "{duration} de transcripción",
  "plan.card.perImport": "hasta {duration} por importación",
  "plan.rec.cappedLargest":
    "Has consumido los {duration} de este periodo. {plan} es el plan más grande que ofrecemos.",
  "plan.rec.cappedNextUp":
    "Has consumido los {duration} de este periodo. {plan} es la talla siguiente.",
  "plan.rec.overLargest":
    "Has usado {duration} en este periodo, más de lo que incluye cualquier plan. {plan} es el más grande que ofrecemos.",
  "plan.rec.trialFloor":
    "Has usado {duration} de tu prueba hasta ahora. {plan} te mantiene en el plan que ya estás usando.",
  "plan.rec.covering":
    "Has usado {duration} en este periodo. {plan} es el plan más pequeño que lo cubre.",
  "plan.badge.recommended": "RECOMENDADO PARA TI",
  "plan.badge.yourTrial": "TU PLAN DE PRUEBA",
  "plan.badge.bestValue": "MEJOR PRECIO",
  "paywall.reason.trialOut":
    "Los minutos de tu prueba se han agotado y no se recargan. Elige un plan para seguir importando audio y vídeo.",
  "paywall.reason.outNoDate":
    "Te has quedado sin minutos en este periodo. Un plan más grande te da más ahora mismo.",
  "paywall.reason.outWithDate":
    "Te has quedado sin minutos hasta el {date}. Un plan más grande te da más ahora mismo.",
  "paywall.reason.trialLow":
    "Te quedan {left} de prueba, y los minutos de prueba no se recargan.",
  "paywall.reason.lowNoDate": "Te quedan {left} en este periodo.",
  "paywall.reason.lowWithDate": "Te quedan {left} hasta el {date}.",
  "plan.minutesRule":
    "Los minutos cubren el audio y el vídeo que transcribimos. Los artículos y las páginas web no cuestan ningún minuto, y leer tu biblioteca es ilimitado.",
  "plan.legend.realLength":
    "El audio y el vídeo cuentan su duración real, minuto a minuto.",
  "plan.legend.captions":
    "Un vídeo que ya tiene subtítulos que podemos comprar cuesta {duration}, dure lo que dure.",
  "plan.legend.documents":
    "Un PDF, un documento de Office o una foto de la que leemos el texto cuesta 1 min por cada {pages} páginas.",
  "plan.legend.collections":
    "Una generación sobre una colección entera cuesta 1 min por cada {sources} elementos que contenga. Sobre un solo elemento es gratis.",
  "plan.legend.free":
    "Los artículos, las páginas web, los TikToks y las publicaciones de fotos de Instagram no cuestan nada: no se transcriben.",
  "plan.legend.overLimit":
    "Por encima del máximo por importación de un plan, la importación se rechaza en lugar de facturarse: divídela en partes más cortas.",
  "plan.list.separator": ", ",
  "plan.list.lastConjunction": "{list} y {last}",
  "plan.highlight.capture":
    "Guarda desde cualquier app: YouTube, pódcasts, TikTok, Instagram, X, artículos, PDF, documentos, fotos y archivos de audio",
  "plan.highlight.read":
    "Lee la transcripción completa, traducida a tu idioma de lectura",
  "plan.highlight.generate":
    "Genera {list} bajo demanda, por elemento o por colección",
  "plan.highlight.organise":
    "Organiza en colecciones y etiquetas, busca en todo, resumen diario",
  "plan.includes.capture.title": "Guarda cualquier cosa, desde cualquier app",
  "plan.includes.capture.links":
    "Comparte un enlace desde cualquier app, o pégalo: vídeos de YouTube, episodios de pódcast de Apple Podcasts, Spotify, Deezer o cualquier feed RSS, TikToks, reels y publicaciones de fotos de Instagram, publicaciones de X, artículos de prensa y cualquier página web.",
  "plan.includes.capture.files":
    "Envía un archivo desde tu teléfono: documentos PDF, Word, PowerPoint y Excel, fotos y capturas de pantalla de las que leemos el texto, y grabaciones de audio (MP3, M4A, WAV, FLAC, AAC, OGG, Opus).",
  "plan.includes.read.title": "Léelo, sea lo que sea",
  "plan.includes.read.transcripts":
    "El audio y el vídeo vuelven como texto completo, transcrito palabra por palabra, así que un episodio que no tienes tiempo de escuchar es uno que puedes leer, ojear o buscar.",
  "plan.includes.read.translation":
    "Las transcripciones se traducen a tu idioma de lectura, {count} para elegir, y puedes cambiarlo cuando quieras.",
  "plan.includes.generate.title": "Conviértelo en algo que conservas",
  "plan.includes.generate.onDemand":
    "En cualquier elemento, bajo demanda: {list}.",
  "plan.includes.generate.collection":
    "Ejecuta las mismas generaciones sobre una colección entera para obtener una única síntesis de todo lo que has archivado en ella.",
  "plan.includes.generate.kept":
    "Cada generación se conserva, así que puedes volver a ella o pedir una nueva más adelante.",
  "plan.includes.organise.title": "Encuéntralo meses después",
  "plan.includes.organise.file":
    "Archiva cualquier cosa en colecciones y etiquetas, en el momento de guardarla o más tarde.",
  "plan.includes.organise.search":
    "Búsqueda de texto completo en todo lo que has guardado, transcripciones incluidas.",
  "plan.includes.organise.digest":
    "Un resumen diario y otro semanal de lo que ha llegado y de lo que merece la pena revisar.",
  "plan.includes.minutes.title": "Qué cuentan los minutos mensuales",
  "plan.trial.accessFull": "acceso completo",
  "plan.trial.accessTier": "acceso {tier}",
  "plan.trial.generic":
    "Tu prueba gratuita está en marcha: {access}, sin cargo y sin nada que cancelar.",
  "plan.trial.genericWithDate":
    "Tu prueba gratuita está en marcha: {access} hasta el {date}, sin cargo y sin nada que cancelar.",
  "plan.trial.days":
    "Tu prueba gratuita de {days} días está en marcha: {access}, sin cargo y sin nada que cancelar.",
  "plan.trial.daysWithDate":
    "Tu prueba gratuita de {days} días está en marcha: {access} hasta el {date}, sin cargo y sin nada que cancelar.",
  "account.plan.heading": "TU PLAN",
  "account.plan.checking": "Comprobando tu plan…",
  "account.plan.unavailable": "Estado del plan no disponible",
  "account.plan.unavailableHint":
    "No hemos podido cargar los detalles de tu suscripción. Tu plan en sí no se ve afectado.",
  "account.plan.retryA11y": "Reintentar la carga de los detalles del plan",
  "account.plan.none": "Sin plan activo",
  "account.plan.noneHint":
    "Tus minutos y tu fecha de recarga aparecerán aquí en cuanto haya una suscripción activa.",
  "account.plan.freeTrial": "Prueba gratuita",
  "account.plan.active": "Plan activo",
  "account.plan.minutesLeft": "MINUTOS RESTANTES",
  "account.plan.minutesLeftA11y":
    "{remaining} de {included} minutos restantes en este periodo",
  "account.plan.unknownDate": "Desconocida",
  "account.plan.resetDateA11y": "{label} {date}",
  "account.plan.resetDateUnknownA11y": "Fecha de recarga desconocida",
  "account.plan.minutesRuleTrial":
    "{rule} Los minutos de prueba no se recargan.",
  "transcript.heading": "Transcripción",
  "transcript.empty": "Aún no hay transcripción disponible.",
  "transcript.emptyHint":
    "La transcripción aparecerá cuando termine el procesamiento.",
  "transcript.status.pending":
    "El procesamiento de la transcripción empezará pronto.",
  "transcript.status.extracting": "Extrayendo el contenido de audio…",
  "transcript.status.transcribing": "Transcribiendo el audio a texto…",
  "transcript.status.ready": "La transcripción está lista.",
  "transcript.status.failed": "El procesamiento de la transcripción ha fallado.",
  "transcript.paragraphCount.one": "{count} párrafo",
  "transcript.paragraphCount.other": "{count} párrafos",
  "transcript.loading": "Cargando la transcripción…",
  "transcript.notAvailable":
    "El contenido de la transcripción no está disponible para este elemento.",
  "transcript.retryA11y": "Reintentar la carga de la transcripción",
  "auth.email": "Correo",
  "auth.password": "Contraseña",
  "auth.emailPlaceholder": "tu@ejemplo.com",
  "login.title": "Bienvenido de nuevo",
  "login.subtitle": "Inicia sesión para acceder a tu biblioteca",
  "login.passwordPlaceholder": "Tu contraseña",
  "login.submit": "Iniciar sesión",
  "login.submitA11y": "Iniciar sesión con correo",
  "login.noAccount": "¿Aún no tienes cuenta?",
  "login.signUpLink": "Regístrate",
  "register.title": "Crear cuenta",
  "register.subtitle": "Empieza a construir tu base de conocimiento",
  "register.passwordPlaceholder": "Al menos 6 caracteres",
  "register.submit": "Crear cuenta",
  "register.submitA11y": "Crear cuenta con correo",
  "register.hasAccount": "¿Ya tienes cuenta?",
  "register.signInLink": "Iniciar sesión",
  "common.goBack": "Volver",
  "readingLanguage.title": "Idioma de lectura",
  "readingLanguage.selectA11y": "Elegir {language} como idioma de lectura",
  "readingLanguage.disclaimer":
    "Cambiar este ajuste solo afecta al contenido futuro. Los resúmenes y traducciones existentes no se volverán a procesar.",
  "readingLanguage.saved": "Idioma actualizado",
  "readingLanguage.saveA11y": "Guardar el idioma de lectura",
  "deleteAccount.title": "Eliminar la cuenta",
  "deleteAccount.warningTitle": "Esto no se puede deshacer",
  "deleteAccount.warningBody":
    "Eliminar tu cuenta la borra de forma permanente, junto con todo lo que hayas guardado. No podemos restaurarla después, ni siquiera si lo pides.",
  "deleteAccount.erasedHeading": "Qué se borra",
  "deleteAccount.erased.library": "Tu biblioteca, carpetas y etiquetas",
  "deleteAccount.erased.artifacts":
    "Todas tus transcripciones, resúmenes, apuntes y tarjetas",
  "deleteAccount.erased.schedule": "Tu calendario de repaso y tus resúmenes",
  "deleteAccount.erased.search": "Tus resultados de búsqueda en toda la app",
  "deleteAccount.erased.identity":
    "Tu dirección de correo y tus datos de acceso",
  "deleteAccount.subscriptionHeading": "Tu suscripción",
  "deleteAccount.subscriptionBodyApple":
    "Eliminar tu cuenta no cancela tu suscripción. Apple te seguirá cobrando hasta que la canceles en los ajustes de tu tienda, así que cancélala allí primero.",
  "deleteAccount.subscriptionBodyGoogle":
    "Eliminar tu cuenta no cancela tu suscripción. Google te seguirá cobrando hasta que la canceles en los ajustes de tu tienda, así que cancélala allí primero.",
  "deleteAccount.manageApple": "Gestionar la suscripción en la App Store",
  "deleteAccount.manageGoogle": "Gestionar la suscripción en Play Store",
  "deleteAccount.copyHeading": "¿Quieres una copia antes?",
  "deleteAccount.copyBody":
    "Escríbenos antes de eliminarla y te enviaremos una copia de tus datos en el plazo de un mes.",
  "deleteAccount.emailA11y": "Escribir a {address}",
  "deleteAccount.acknowledge":
    "Entiendo que mi cuenta y todos mis datos se borrarán de forma permanente.",
  "deleteAccount.acknowledgeA11y": "Entiendo que esto no se puede deshacer",
  "deleteAccount.submit": "Eliminar mi cuenta",
  "deleteAccount.submitA11y": "Eliminar mi cuenta",
  "deleteAccount.confirmTitle": "¿Eliminar la cuenta?",
  "deleteAccount.confirmBody":
    "Esto borra de forma permanente tu cuenta y todo lo que contiene. No se puede deshacer.",
  "deleteAccount.confirmAction": "Eliminar para siempre",
  "account.title": "Cuenta",
  "account.notSet": "Sin definir",
  "account.subscription.manage": "Gestionar la suscripción",
  "account.subscription.manageHint": "Cambiar de plan o restaurar una compra",
  "account.subscription.viewPlans": "Ver planes",
  "account.subscription.viewPlansHint": "Mira qué incluye cada suscripción",
  "account.subscription.upgrade": "Cambiar plan",
  "account.subscription.upgradeHint": "Desbloquea más minutos de audio y vídeo",
  "account.featureRequests": "Sugerencias",
  "account.reportBug": "Informar de un error",
  "account.signOut": "Cerrar sesión",
  "account.signOutConfirm": "¿Seguro que quieres cerrar sesión?",
  "account.signOutAction": "Sí, cerrar sesión",
  "account.feedbackUnavailable": "Sugerencias no disponibles",
  "account.feedbackUnavailableBody":
    "El espacio de sugerencias aún no está configurado. Inténtalo de nuevo más tarde.",
  "uiLanguage.title": "Idioma de la app",
  "uiLanguage.disclaimer":
    "Este es el idioma de la aplicación en sí. El idioma en el que se escriben tus resúmenes y transcripciones es el idioma de lectura, que se ajusta por separado.",
  "uiLanguage.followDevice": "Seguir mi dispositivo",
  "uiLanguage.selectA11y": "Usar {language} para la app",
  "settings.uiLanguage.restartTitle": "Reinicia para terminar el cambio",
  "settings.uiLanguage.restartBody":
    "Este idioma se lee de derecha a izquierda, así que la app tiene que reiniciarse para que la disposición lo siga. Ciérrala y vuelve a abrirla.",
  "onboarding.language.title": "Elige tu idioma de lectura",
  "onboarding.language.subtitle":
    "El contenido se traducirá a este idioma cuando haga falta.",
  "onboarding.language.continueA11y": "Continuar con el idioma elegido",
  "mediaType.unknownSource": "Desconocida",
  "search.placeholder": "Busca en tu biblioteca…",
  "search.clearA11y": "Borrar la búsqueda",
  "search.collections": "Colecciones",
  "search.allMedia": "Todos los medios",
  "search.noCollections":
    "Aún no hay colecciones. Organiza tus medios en colecciones al guardarlos.",
  "search.openCollectionA11y": "Abrir la colección {name}",
  "search.resultCount.one": "{count} resultado",
  "search.resultCount.other": "{count} resultados",
  "search.endOfResults": "Fin de los resultados",
  "search.noResultsTitle": "Sin resultados",
  "search.noMatches":
    "Sin coincidencias para «{query}». Prueba con otras palabras.",
  "search.emptyLibrary": "Tu biblioteca está vacía",
  "search.emptyLibraryHint":
    "Comparte un enlace desde cualquier app, o importa un archivo desde la bandeja, y aparecerá aquí.",
  "search.failed": "La búsqueda ha fallado",
  "search.collectionsLoadFailed": "No se han podido cargar tus colecciones.",
  "search.libraryLoadFailed": "No se ha podido cargar tu biblioteca.",
  "search.retryLibraryA11y": "Reintentar la carga de tu biblioteca",
  "search.retryCollectionsA11y": "Reintentar la carga de las colecciones",
  "search.retrySearchA11y": "Reintentar la búsqueda",
  "tabs.home": "Inicio",
  "tabs.search": "Buscar",
  "tabs.digest": "Resumen",
  "home.loading": "Cargando tu bandeja…",
  "home.retryA11y": "Reintentar la carga de la bandeja",
  "home.continueLearning": "Seguir aprendiendo",
  "home.recentlyAdded": "Añadido recientemente",
  "home.takePhotoA11y": "Hacer una foto",
  "home.unsortedReview": "Revisión de sin clasificar",
  "home.unsortedReviewA11y": "Revisar tus medios sin clasificar, {count}",
  "home.empty": "Tus medios compartidos aparecerán aquí.",
  "home.emptyHint":
    "Comparte un enlace desde cualquier app, o toca + para importar un archivo o hacer una foto.",
  "home.untitledCollection": "Colección",
  "unsortedReview.title": "Revisión de sin clasificar",
  "unsortedReview.position": "{current} / {total}",
  "unsortedReview.positionA11y": "Fuente {current} de {total}",
  "unsortedReview.closeA11y": "Cerrar la revisión de sin clasificar",
  "unsortedReview.loadFailed":
    "No se han podido cargar tus medios sin clasificar. Inténtalo de nuevo.",
  "unsortedReview.noBlurb": "Todavía no hay resumen breve de este.",
  "unsortedReview.discard": "Descartar",
  "unsortedReview.discardA11y": "Descartar {title}",
  "unsortedReview.discardFailed":
    "No se ha podido descartar esta fuente. Inténtalo de nuevo.",
  "unsortedReview.deepen": "Profundizar",
  "unsortedReview.deepenA11y": "Abrir {title}",
  "unsortedReview.save": "Guardar",
  "unsortedReview.saveA11y": "Guardar {title} en una colección",
  "unsortedReview.doneTitle": "No queda nada por clasificar",
  "unsortedReview.doneBody": "Todo lo que esperaba ya está resuelto.",
  "digest.daily": "Diario",
  "digest.weekly": "Semanal",
  "digest.dailyTitle": "Tu día en revisión",
  "digest.weeklyTitle": "Tu semana en revisión",
  "digest.dailySubtitle.one": "{count} idea de hoy",
  "digest.dailySubtitle.other": "{count} ideas de hoy",
  "digest.weeklySubtitle.one": "{count} idea lista para revisar",
  "digest.weeklySubtitle.other": "{count} ideas listas para revisar",
  "digest.loadFailed": "No se ha podido cargar el resumen",
  "digest.tryAgain": "Reintentar",
  "digest.emptyDaily": "Aún no hay ideas hoy",
  "digest.emptyWeekly": "No hay ideas esta semana",
  "digest.emptyDailyHint":
    "Comparte medios en tu biblioteca y vuelve más tarde para ver tu resumen personalizado.",
  "digest.emptyWeeklyHint":
    "Procesa algunos medios a lo largo de la semana para ver aquí tu síntesis semanal.",
  "digest.readTime.one": "{count} min de lectura",
  "digest.readTime.other": "{count} min de lectura",
  "digest.type.podcast": "Pódcast",
  "digest.type.article": "Artículo",
  "digest.type.youtube": "YouTube",
  "digest.type.video": "Vídeo",
  "digest.type.audio": "Audio",
  "digest.type.text": "Texto",
  "tags.selectedCount.one": "{count} etiqueta",
  "tags.selectedCount.other": "{count} etiquetas",
  "tags.saveA11y": "Guardar las etiquetas",
  "tags.removeA11y": "Quitar {name}",
  "tags.addPlaceholder": "Añadir una etiqueta",
  "tags.createA11y": "Crear la etiqueta «{name}»",
  "tags.otherHeading": "OTRAS",
  "tags.loadFailed": "No se han podido cargar las etiquetas",
  "tags.createFailed": "No se ha podido crear la etiqueta",
  "tags.saveFailed": "No se han podido guardar las etiquetas",
  "collectionPicker.title": "Colección",
  "collectionPicker.saveA11y": "Guardar la selección",
  "collectionPicker.searchPlaceholder": "Buscar",
  "collectionPicker.unsorted": "Sin clasificar",
  "collectionPicker.myCollections": "Mis colecciones",
  "collectionPicker.createA11y": "Crear una colección",
  "collectionPicker.namePlaceholder": "Nombre de la colección",
  "collectionPicker.confirm": "Confirmar",
  "collectionPicker.collapse": "Contraer",
  "collectionPicker.expand": "Expandir",
  "collectionPicker.noMatches": "Ninguna colección coincide con tu búsqueda",
  "collectionPicker.loadFailed": "No se han podido cargar las colecciones",
  "collectionPicker.saveFailed": "No se ha podido guardar la colección",
  "collectionPicker.createFailed": "No se ha podido crear la colección",
  "collections.loading": "Cargando las colecciones…",
  "collections.loadFailed":
    "No se han podido cargar tus colecciones. Inténtalo de nuevo.",
  "collections.empty": "Aún no hay colecciones",
  "collections.emptyHint":
    "Organiza tus medios en colecciones al guardarlos para encontrarlos aquí.",
  "collections.emptyFolder": "Vacía",
  "collections.childCount.one": "{count} colección",
  "collections.childCount.other": "{count} colecciones",
  "media.tab.reader": "Lectura",
  "media.tab.ai": "IA",
  "media.sectionsA11y": "Secciones del medio",
  "media.loadFailed": "No se han podido cargar los detalles del medio.",
  "media.retryA11y": "Reintentar la carga de los detalles del medio",
  "media.processingHint": "Esto suele tardar menos de un minuto.",
  "media.timeoutTitle": "Está tardando más de lo habitual.",
  "media.timeoutHint": "Desliza para actualizar o vuelve más tarde.",
  "media.refresh": "Actualizar",
  "media.refreshA11y": "Actualizar el estado del medio",
  "media.failedTitle": "El procesamiento ha fallado",
  "media.failedFallback": "Se ha producido un error inesperado.",
  "media.processingFailed":
    "El procesamiento ha fallado. Inténtalo de nuevo más tarde.",
  "media.processing.audio": "Transcribiendo el audio…",
  "media.processing.video": "Transcribiendo el vídeo…",
  "media.processing.extracting": "Extrayendo el contenido…",
  "media.processing.generating": "Generando el texto…",
  "media.transcriptLoadFailed":
    "No se ha podido cargar la transcripción ahora mismo.",
  "media.movedToNamed": "Movido a «{name}»",
  "media.movedToCollection": "Movido a una colección",
  "media.removedFromCollection": "Quitado de la colección",
  "media.openFailed": "No se ha podido abrir {host}",
  "media.moveToCollectionA11y": "Mover a una colección",
  "media.shareA11y": "Compartir",
  "collection.tab.sources": "Fuentes",
  "collection.tab.ai": "IA",
  "collection.sectionsA11y": "Secciones de la colección",
  "collection.loadFailed":
    "No se ha podido cargar esta colección. Inténtalo de nuevo.",
  "collection.retryA11y": "Reintentar la carga de la colección",
  "collection.artifactsLoadFailed":
    "No se ha podido cargar el contenido generado. Inténtalo de nuevo.",
  "collection.empty": "Esta colección está vacía",
  "collection.emptyHint":
    "Los medios que guardes en esta colección aparecerán aquí.",
  "bugReport.subject": "Asunto",
  "bugReport.subjectPlaceholder": "Resumen breve del problema",
  "bugReport.subjectA11y": "Asunto del informe de error",
  "bugReport.description": "Descripción",
  "bugReport.descriptionPlaceholder":
    "Pasos para reproducirlo, qué esperabas, qué ocurrió en su lugar…",
  "bugReport.descriptionA11y": "Descripción del informe de error",
  "bugReport.attachment": "Adjunto (opcional)",
  "bugReport.attach": "Adjuntar archivo",
  "bugReport.attachA11y": "Adjuntar un archivo al informe de error",
  "bugReport.attachChoose": "Elige una fuente",
  "bugReport.photoLibrary": "Fototeca",
  "bugReport.files": "Archivos",
  "bugReport.removeFileA11y": "Quitar el archivo adjunto",
  "bugReport.submit": "Enviar",
  "bugReport.submitA11y": "Enviar el informe de error",
  "bugReport.submitting": "Enviando el informe…",
  "bugReport.uploading": "Subiendo el adjunto…",
  "bugReport.submitted": "Informe enviado",
  "bugReport.ticketId": "Número de ticket",
  "bugReport.doneA11y": "Listo, volver a la cuenta",
  "bugReport.closeA11y": "Cerrar el formulario de informe de error",
  "bugReport.submitFailed":
    "No se ha podido enviar el informe de error. Inténtalo de nuevo.",
  "bugReport.pickFileFailed":
    "No se ha podido seleccionar el archivo. Inténtalo de nuevo.",
  "bugReport.pickImageFailed":
    "No se ha podido seleccionar la imagen. Inténtalo de nuevo.",
  "bugReport.fileTypeTitle": "Tipo de archivo no permitido",
  "bugReport.fileTypeAccepted": "Tipos de archivo aceptados: {list}",
  "bugReport.fileTypeRejected":
    "El tipo de archivo seleccionado ({type}) no se acepta.",
  "bugReport.fileTooLargeTitle": "Archivo demasiado grande",
  "bugReport.fileTooLarge":
    "El tamaño máximo es {max}. Tu archivo ocupa {size}.",
  "paywall.title": "Elige tu plan",
  "paywall.plansLoadFailed":
    "No hemos podido cargar los planes. Comprueba tu conexión e inténtalo de nuevo.",
  "paywall.tryAgain": "Reintentar",
  "paywall.pricesUnavailable":
    "Los precios no están disponibles: la {store} no ofrece estas suscripciones ahora mismo.",
  "paywall.selectorLabel": "Elige tu tiempo de transcripción mensual",
  "paywall.selectorLabelReadOnly": "Qué te da cada plan",
  "paywall.priceUnavailableA11y": "precio no disponible",
  "paywall.pricePerMonthA11y": "{price} al mes",
  "paywall.includedHeading": "Incluido en todos los planes",
  "paywall.showDetails": "Ver exactamente qué incluye",
  "paywall.hideDetails": "Ocultar los detalles",
  "paywall.ctaChoose": "Elegir un plan",
  "paywall.ctaStart": "Empezar con {plan} — {price}/mes",
  "paywall.purchaseSuccess": "Compra realizada",
  "paywall.purchaseSuccessBody": "Tu suscripción ya está activa. ¡Disfrútala!",
  "paywall.purchasePending": "Compra pendiente",
  "paywall.purchasePendingBody":
    "Tu compra está pendiente de aprobación. Te avisaremos cuando se complete.",
  "paywall.purchaseFailed": "Error en la compra",
  "paywall.unexpectedError":
    "Se ha producido un error inesperado. Inténtalo de nuevo.",
  "paywall.renewalTerms":
    "El pago se carga en tu cuenta de {store} al confirmar la compra. La suscripción se renueva mensualmente salvo que se cancele al menos 24 horas antes del final del periodo en curso, y tu cuenta se carga por la renovación en las 24 horas previas.",
  "paywall.terms": "Condiciones de uso",
  "paywall.privacy": "Política de privacidad",
  "paywall.cancelAnytime":
    "Cancela cuando quieras en tu cuenta de {store}.",
  "artifact.loadFailed": "No se ha podido cargar este contenido generado.",
  "artifact.failedTitle": "No se ha podido cargar",
  "artifact.retryA11y": "Reintentar la carga del contenido generado",
  "artifact.notReady": "Aún no está listo",
  "artifact.pendingBody":
    "Este contenido se sigue generando. Vuelve en un momento.",
  "artifact.refreshA11y": "Actualizar el contenido generado",
  "artifact.generationFailedTitle": "La generación ha fallado",
  "artifact.generationFailedBody":
    "No se ha podido generar este contenido y ya no hay nada en marcha. Vuelve a generarlo para intentarlo.",
  "artifact.regenerate": "Generar de nuevo",
  "artifact.regenerateA11y": "Volver a generar este contenido",
  "artifact.regenerating": "Iniciando...",
  "artifact.regenerationQueued":
    "Generación reiniciada. Vuelve en un momento.",
  "artifact.anotherLanguage": "otro idioma",
  "artifact.translatedFrom": "Traducido del {language}",
  "artifact.translationFailed":
    "Traducción no disponible: se muestra en {language}",
  "artifact.translationFailedA11y":
    "Traducción no disponible. Este contenido se muestra en su idioma original, {language}.",
  "artifact.section.keyPoints": "Puntos clave",
  "artifact.section.takeaway": "Para recordar",
  "artifact.section.context": "Contexto",
  "artifact.section.mainTopics": "Temas principales",
  "artifact.section.quotes": "Citas destacadas",
  "artifact.section.conclusion": "Conclusión",
  "artifact.section.objectives": "Objetivos",
  "artifact.section.concepts": "Conceptos",
  "artifact.section.actionItems": "Acciones",
  "artifact.section.glossary": "Glosario",
  "artifact.noFlashcards": "No hay tarjetas en este contenido.",
  "artifact.cardCount.one": "{count} tarjeta",
  "artifact.cardCount.other": "{count} tarjetas",
  "artifact.question": "PREGUNTA",
  "artifact.answer": "RESPUESTA",
  "artifact.tapToReveal": "Toca para revelar",
  "artifact.revealAnswerA11y": "Toca para revelar la respuesta",
  "artifact.hideAnswer": "Ocultar la respuesta",
  "artifact.noQuestions": "No hay preguntas en este contenido.",
  "artifact.quizProgress": "Progreso del cuestionario",
  "artifact.questionPosition": "Pregunta {index} de {total}",
  "artifact.quizComplete": "Cuestionario completado",
  "artifact.explanation": "EXPLICACIÓN",
  "artifact.optionA11y": "Opción {label}: {text}{state}",
  "share.title.url": "Guardar el enlace",
  "share.title.text": "Guardar el texto",
  "share.title.audio": "Guardar el audio",
  "share.title.file": "Importar el archivo",
  "share.title.photo": "Guardar la foto",
  "share.processing": "Procesando el contenido compartido…",
  "share.invalid": "No se puede guardar este contenido",
  "share.saved": "¡Guardado!",
  "share.saveFailed": "Error al guardar",
  "share.saving": "Guardando…",
  "share.uploadingAudio": "Subiendo el audio…",
  "share.uploadingFile": "Subiendo el archivo…",
  "share.whatsappText": "Mensaje de texto de WhatsApp",
  "share.tags": "Etiquetas",
  "share.chooseCollection": "Elegir una colección",
  "share.chooseTags": "Elegir etiquetas",
  "share.success.duplicate": "Este contenido ya estaba en tu bandeja.",
  "share.success.audio":
    "Audio guardado. La transcripción empezará en breve.",
  "share.success.text": "Texto guardado en tu bandeja.",
  "share.success.photo":
    "Foto importada. La extracción del texto empezará en breve.",
  "share.success.audioFile":
    "Archivo de audio importado. La transcripción empezará en breve.",
  "share.success.file":
    "Archivo importado. El procesamiento empezará en breve.",
  "share.success.url":
    "Enlace añadido a tu bandeja. El procesamiento empezará en breve.",
  "import.filesUnavailable": "No se han podido abrir tus archivos",
  "import.filesUnavailableBody":
    "No se ha podido abrir el explorador de archivos. Inténtalo de nuevo.",
  "import.formatNotSupported": "Formato no compatible",
  "import.cameraUnavailable": "Cámara no disponible",
  "import.cameraUnavailableBody":
    "No se ha podido iniciar la cámara en este dispositivo.",
  "import.cameraPermission": "Se necesita acceso a la cámara",
  "import.cameraPermissionAsk":
    "Permite el acceso a la cámara para capturar un documento o una página que quieras importar.",
  "import.cameraPermissionSettings":
    "El acceso a la cámara está desactivado. Actívalo para esta app en los ajustes de tu dispositivo para capturar un documento.",
  "import.galleryUnavailable": "Galería no disponible",
  "import.galleryUnavailableBody":
    "No se ha podido abrir tu galería de fotos. Inténtalo de nuevo.",
  "import.photoTooLarge": "Foto demasiado grande",
  "import.photoNotSupported": "Foto no compatible",
  "upload.reject.extension":
    "Los archivos con la extensión .{extension} no se pueden importar. Formatos compatibles: {formats}.",
  "upload.reject.noExtension":
    "Este archivo no tiene una extensión reconocible. Formatos compatibles: {formats}.",
  "upload.reject.empty": "Este archivo está vacío, así que no hay nada que importar.",
  "upload.reject.tooLarge":
    "Este archivo ocupa {size}, por encima del límite de {max} para una sola importación.",
  "home.loadFailed": "No se ha podido cargar tu bandeja. Inténtalo de nuevo.",
  "share.unsupportedFile": "Este tipo de archivo aún no es compatible.",
  "share.signInLinks": "Debes iniciar sesión para guardar enlaces.",
  "share.signInContent": "Debes iniciar sesión para guardar contenido.",
  "share.signInFiles": "Debes iniciar sesión para importar archivos.",
  "transcript.translating": "Traduciendo la transcripción…",
  "transcript.translationFailed":
    "La traducción ha fallado. Se muestra la transcripción original.",
  "paywall.subtitle":
    "Todos los planes lo hacen todo. Solo cambia el tiempo de transcripción mensual.",
};
