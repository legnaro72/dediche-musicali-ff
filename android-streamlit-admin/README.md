# Admin Dediche FF Android

Mini app Android WebView per aprire l'amministrazione Streamlit:

`https://dediche-musicali-ff.streamlit.app/`

## Come aprirla in Android Studio

1. Apri Android Studio.
2. Seleziona `Open`.
3. Scegli la cartella `D:\dediche-musicali_FF\android-streamlit-admin`.
4. Attendi il Gradle Sync.
5. Premi `Run` per provarla su telefono/emulatore.

## APK

Da Android Studio:

`Build > Build Bundle(s) / APK(s) > Build APK(s)`

L'app non contiene il motore Streamlit: apre solo Streamlit Cloud con icona e nome personalizzati.

La WebView ha JavaScript, cookie, storage locale e selettore file abilitati, quindi i campi upload di Streamlit possono aprire il picker Android.

In questa workspace non e' presente `gradle` nel PATH: la build va lanciata da Android Studio dopo il Gradle Sync.
