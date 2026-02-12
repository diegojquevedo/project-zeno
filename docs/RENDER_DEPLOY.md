# Despliegue en Render (plan gratuito)

Guía para desplegar **project-zeno** en Render usando el plan gratuito.

## Requisitos previos

- Cuenta en [Render](https://render.com)
- Repositorio en GitHub conectado a Render
- API keys: **ANTHROPIC_API_KEY**, **OPENAI_API_KEY**, **GOOGLE_API_KEY** (al menos una para el modelo)

## Opción A: Blueprint automático (recomendado)

1. Ve a [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
2. Conecta tu repositorio de GitHub
3. Render detectará `render.yaml` y creará los servicios
4. **Añade las variables de entorno secretas** en el Dashboard:
   - `zeno-api` → Environment → Add: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
5. La base de datos `zeno-db` se creará automáticamente (Render Postgres free)

### PostGIS (base de datos)

Las migraciones usan **PostGIS**. El plan free de Render Postgres puede no incluir PostGIS.

- **Si fallan las migraciones**: usa [Supabase](https://supabase.com) (gratis, PostGIS incluido):
  1. Crea un proyecto en Supabase
  2. En Settings → Database copia la connection string
  3. Cámbiala de `postgresql://` a `postgresql+asyncpg://` para la API (o déjala igual, el código la convierte)
  4. En `zeno-api` → Environment → añade/sobrescribe `DATABASE_URL` con esa URL
  5. Elimina `zeno-db` del Blueprint si no la usas

## Opción B: Crear servicios manualmente

### 1. Base de datos

- **Render Postgres**: New → PostgreSQL → plan free
- O **Supabase**: proyecto gratis con PostGIS

### 2. API (zeno-api)

- New → Web Service
- Conecta el repo, branch `main`
- **Runtime**: Docker
- **Build Command**: (vacío, usa Dockerfile)
- **Start Command**: `uv run uvicorn src.api.app:app --host 0.0.0.0 --port 10000`
- **Instance Type**: Free

**Variables de entorno**:
| Key | Value |
|-----|-------|
| DATABASE_URL | (interno si usas Render Postgres, o Supabase URL) |
| LANGFUSE_TRACING_ENABLED | `false` |
| STAGE | `production` |
| COOKIE_SIGNER_SECRET_KEY | (generar aleatorio) |
| NEXTJS_API_KEY | (generar aleatorio) |
| ANTHROPIC_API_KEY | (tu clave) |
| OPENAI_API_KEY | (tu clave) |
| GOOGLE_API_KEY | (tu clave) |
| ALLOW_ANONYMOUS_CHAT | `false` |
| ALLOW_PUBLIC_SIGNUPS | `true` |
| EMAILS_ALLOWLIST | `*` |

### 3. Frontend (zeno-web)

- New → Web Service
- Mismo repo, branch `main`
- **Runtime**: Docker
- **Start Command**: `uv run streamlit run frontend/app.py --server.port=10000 --server.address=0.0.0.0`
- **Instance Type**: Free

**Variables de entorno**:
| Key | Value |
|-----|-------|
| API_BASE_URL | `https://zeno-api-xxx.onrender.com` (URL de zeno-api) |
| STREAMLIT_URL | `https://zeno-web-xxx.onrender.com` (URL de zeno-web) |

## Limitaciones del plan gratuito

- **Sleep**: los servicios se duermen tras ~15 min sin uso
- **Cold start**: 30 s – 2 min al despertar
- **Horas**: ~750 h/mes en total (suele bastar para pruebas)
- **PostgreSQL**: 1 GB, 90 días si no hay actividad (Render free)

## URLs después del deploy

- **Frontend**: `https://zeno-web-xxx.onrender.com`
- **API**: `https://zeno-api-xxx.onrender.com`
- **Health check**: `https://zeno-api-xxx.onrender.com/api/health`

## Login

Por defecto `ALLOW_ANONYMOUS_CHAT=false`: los usuarios deben iniciar sesión con **Global Forest Watch** (Resource Watch). Usa el botón "Login with Global Forest Watch" en la app.
