# OAuth 2.0 paso a paso (YouTube Data API)

Este documento explica cómo crear credenciales OAuth, obtener tokens y usar un **redirect URI en localhost**.

---

## 1) Crear proyecto y habilitar YouTube Data API

1. Entra a Google Cloud Console: `https://console.cloud.google.com/`.
2. Crea un proyecto nuevo (o usa uno existente).
3. Ve a **APIs & Services → Library** (directo: `https://console.cloud.google.com/apis/library`) y habilita **YouTube Data API v3**.

---

## 2) Configurar pantalla de consentimiento

1. Ve a **APIs & Services → OAuth consent screen**.
2. Selecciona **External** (si no es GSuite).
3. Completa nombre de app, email de soporte y dominios si aplica.
4. En **Scopes**, agrega al menos:
   - `https://www.googleapis.com/auth/youtube.force-ssl`
5. Agrega tu usuario como **Test user** (si la app está en modo testing).

---

## 3) Crear credenciales OAuth (Client ID / Secret)

1. Ve a **APIs & Services → Credentials**.
2. Click **Create Credentials → OAuth client ID**.
3. Tipo de aplicación:
   - **Web application** (recomendado para usar redirect en localhost)
4. Agrega **Authorized redirect URIs**:
   - `http://localhost:9000/callback` (si usas el puerto default)
   - (opcional) `http://localhost:3333/callback` o el puerto que uses
5. Guarda y copia:
   - `Client ID`
   - `Client Secret`

---

## 4) Configurar tu `.env`

```bash
YOUTUBE_CLIENT_ID=TU_CLIENT_ID
YOUTUBE_CLIENT_SECRET=TU_CLIENT_SECRET
YOUTUBE_REDIRECT_URI=http://localhost:9000/callback
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.force-ssl
```

---

## 5) Generar URL de consentimiento

Usa el tool MCP:
- `youtube_oauth_authorization_url`

Ejemplo de respuesta:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

Abre esa URL en el navegador y autoriza.

---

## 6) Obtener el authorization code

Después del consentimiento, Google redirige a tu `YOUTUBE_REDIRECT_URI`:

```
http://localhost:9000/callback?code=4/0Ab...&scope=...
```

Copia el valor de `code`.

---

## 7) Intercambio automático y guardado

El server expone `/callback`. Cuando Google redirige ahí con el `code`, **se intercambia automáticamente** y se guardan los tokens en `.tokens.json` (o en la ruta indicada por `TOKEN_STORE_PATH`).

Si necesitas hacerlo manual, usa el tool `youtube_oauth_exchange_code`, pero en el flujo normal no hace falta.

Formato del archivo (lista de dicts):
```json
[
  {
    "user_id": "UCxxxx",
    "user_name": "mi-canal",
    "channel_title": "Mi Canal",
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "Bearer",
    "expires_in": 3599,
    "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
    "created_at": "2026-01-31T22:30:00+00:00",
    "updated_at": "2026-01-31T22:30:00+00:00"
  }
]
```

---

## 8) Renovar el access token (manual)

Cuando expire el `access_token`, usa:
- `youtube_oauth_refresh_token`

Entrada:
```json
{ "refresh_token": "TU_REFRESH_TOKEN" }
```

---

## 9) ¿Necesito exportar una URL localhost?

**Sí, para desarrollo local**:
- Debes registrar **localhost** como redirect URI en Google Cloud.
- Puedes usar `http://localhost` o `http://localhost:PORT`.

Si más adelante tienes un backend público, reemplaza el redirect URI por el dominio real.

---

## 10) Errores comunes

- **redirect_uri_mismatch**: El URI no coincide exactamente con el registrado en Google Cloud.
- **insufficient_scope**: Faltan scopes en la pantalla de consentimiento o en el request.
- **invalid_client**: Client ID/Secret incorrectos.

---

## Checklist rápido

- [ ] API habilitada
- [ ] Consent screen configurado
- [ ] OAuth client creado
- [ ] Redirect URI agregado (`http://localhost`)
- [ ] `.env` con client_id/client_secret
- [ ] URL de consentimiento generada y aprobada
- [ ] Code intercambiado por tokens
