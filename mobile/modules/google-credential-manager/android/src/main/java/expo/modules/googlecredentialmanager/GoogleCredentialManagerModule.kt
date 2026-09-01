package expo.modules.googlecredentialmanager

import android.os.Handler
import android.os.Looper
import androidx.credentials.CredentialManager
import androidx.credentials.CredentialManagerCallback
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetCredentialResponse
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import expo.modules.kotlin.Promise
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.functions.Queues
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.util.concurrent.Executor

/**
 * The three outcomes the JavaScript side distinguishes. Two of them are *not*
 * errors and are resolved, not rejected:
 *
 * - `cancelled`: the user dismissed the account sheet. Same meaning as the
 *   `cancel` / `dismiss` results of the browser flow — nothing to show.
 * - `noGoogleAccount`: the device has no Google account at all, so there is
 *   nothing to pick. Actionable by the user, but not a failure of the app, and
 *   it needs its own sentence rather than a generic "sign-in failed".
 */
private const val OUTCOME_SUCCESS = "success"
private const val OUTCOME_CANCELLED = "cancelled"
private const val OUTCOME_NO_GOOGLE_ACCOUNT = "noGoogleAccount"

/** Any other `GetCredentialException`: a real failure, rejected to JavaScript. */
internal class GoogleSignInFailedException(cause: GetCredentialException) :
  CodedException(
    // `GetCredentialException.type` is @RestrictTo(LIBRARY_GROUP), so the class
    // name is what identifies the kind of failure here.
    "Google sign-in failed (${cause.javaClass.simpleName}): ${cause.message}",
    cause
  )

/** The picked credential carried no Google ID token — nothing to post to the API. */
internal class MissingGoogleIdTokenException(cause: Throwable? = null) :
  CodedException("Credential Manager returned no Google ID token", cause)

/**
 * Sign in with Google on Android through Credential Manager.
 *
 * This exists because the browser-based flow is closed on Android: Google
 * refuses a custom URI scheme `redirect_uri` for an Android OAuth client
 * (`Error 400: invalid_request`, "Custom URI scheme is not enabled for your
 * Android client"), and its own documentation states custom URI schemes are no
 * longer supported for Android apps. There is no toggle to turn back on.
 *
 * `GetSignInWithGoogleOption` is the option Google documents for an explicit
 * "Sign in with Google" button press (as opposed to `GetGoogleIdOption`, meant
 * for a bottom-sheet offered on screen load).
 *
 * The `serverClientId` passed from JavaScript is the **Web** OAuth client ID:
 * that is what Google's own docs call for, and it becomes the `aud` of the
 * returned id_token — which the API already accepts on `/auth/google/native`.
 *
 * No nonce is requested: the backend does not verify one, so sending it would be
 * decoration. Adding one here means checking it in `auth_social.py` too.
 */
class GoogleCredentialManagerModule : Module() {
  /**
   * Delivers the Credential Manager callback on the main thread. Posting through
   * a `Handler` rather than `Context.getMainExecutor()`, which is API 28+ while
   * the app's `minSdk` is 24.
   */
  private val mainExecutor = Executor { command -> Handler(Looper.getMainLooper()).post(command) }

  override fun definition() = ModuleDefinition {
    Name("GoogleCredentialManager")

    AsyncFunction("signInAsync") { serverClientId: String, promise: Promise ->
      // Credential Manager needs an Activity: it shows system UI. Missing one is
      // already a coded exception in expo-modules-core.
      val activity = appContext.throwingActivity

      val request = GetCredentialRequest.Builder()
        .addCredentialOption(GetSignInWithGoogleOption.Builder(serverClientId).build())
        .build()

      CredentialManager.create(activity).getCredentialAsync(
        activity,
        request,
        null,
        mainExecutor,
        object : CredentialManagerCallback<GetCredentialResponse, GetCredentialException> {
          override fun onResult(result: GetCredentialResponse) {
            val credential = result.credential
            if (credential !is CustomCredential) {
              promise.reject(MissingGoogleIdTokenException())
              return
            }

            // The credential's `type` string is deliberately not compared:
            // googleid 1.2.0 ships two of them
            // (`TYPE_GOOGLE_ID_TOKEN_CREDENTIAL` and
            // `TYPE_GOOGLE_ID_TOKEN_SIWG_CREDENTIAL`) and which one comes back
            // depends on the provider version. The request carries a single
            // option, so parsing the bundle is both sufficient and version-proof:
            // it fails loudly if the payload is not a Google ID token.
            val idToken = try {
              GoogleIdTokenCredential.createFrom(credential.data).idToken
            } catch (error: Throwable) {
              promise.reject(MissingGoogleIdTokenException(error))
              return
            }

            promise.resolve(
              mapOf<String, Any?>(
                "type" to OUTCOME_SUCCESS,
                "idToken" to idToken
              )
            )
          }

          override fun onError(error: GetCredentialException) {
            when (error) {
              is GetCredentialCancellationException ->
                promise.resolve(mapOf<String, Any?>("type" to OUTCOME_CANCELLED))
              is NoCredentialException ->
                promise.resolve(mapOf<String, Any?>("type" to OUTCOME_NO_GOOGLE_ACCOUNT))
              else -> promise.reject(GoogleSignInFailedException(error))
            }
          }
        }
      )
    }.runOnQueue(Queues.MAIN)
  }
}
