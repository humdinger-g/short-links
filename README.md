# Short Links

API-сервис сокращения ссылок на `FastAPI` с `PostgreSQL` и `Redis`.
Дополнительно в проекте есть простой интерфейс на `Streamlit`.

## Реализованный функционал

- регистрация и логин пользователей
- создание короткой ссылки через `POST /links/shorten`
- поддержка кастомного `custom_alias`
- поддержка `expires_at` с точностью до минуты
- редирект по `GET /links/{short_code}`
- статистика по ссылке через `GET /links/{short_code}/stats`
- поиск по оригинальному URL через `GET /links/search`
- обновление ссылки через `PUT /links/{short_code}`
- удаление ссылки через `DELETE /links/{short_code}`
- доступ к изменению и удалению только для владельца ссылки
- Redis-кэш для `GET /links/search` и `GET /links/{short_code}/stats`
- очистка кэша при обновлении, удалении, переходе по ссылке и автоудалении истекших ссылок
- фоновое автоудаление ссылок после наступления `expires_at`
- история истекших ссылок через `GET /links/history/expired`
- удаление неиспользуемых ссылок через `N` дней без переходов

## Стек

- `FastAPI`
- `SQLAlchemy 2`
- `Alembic`
- `PostgreSQL`
- `Redis`
- `Docker Compose`
- `Streamlit`

## Запуск

1. Создайте `.env` из шаблона:

```bash
cp .env.example .env
```

2. Запустите сервисы:

```bash
docker compose up --build
```

3. Приложение будет доступно по адресу:

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Streamlit UI: `http://localhost:8501`

`docker compose` автоматически применяет миграции `alembic upgrade head` перед запуском приложения.

## Streamlit UI

В интерфейсе на `http://localhost:8501` можно:

- зарегистрироваться и войти
- создать короткую ссылку
- искать ссылки по `original_url`
- смотреть статистику
- обновлять и удалять свои ссылки
- просматривать историю истекших ссылок

## Переменные окружения

- `APP_NAME` — имя приложения
- `DEBUG` — режим отладки
- `DATABASE_URL` — строка подключения к PostgreSQL
- `REDIS_URL` — строка подключения к Redis
- `PUBLIC_BASE_URL` — публичный адрес API, который Streamlit использует при показе коротких ссылок
- `AUTH_SECRET` — секрет для access token
- `ACCESS_TOKEN_TTL_MINUTES` — время жизни токена
- `CACHE_TTL_SECONDS` — базовый TTL для Redis-кэша
- `EXPIRED_LINKS_CLEANUP_INTERVAL_SECONDS` — интервал фоновой очистки истекших ссылок
- `UNUSED_LINK_DAYS` — через сколько дней удалять неиспользуемые ссылки

## API

### Auth

#### `POST /auth/register`

Создает пользователя.

Пример запроса:

```json
{
  "email": "user@example.com",
  "password": "strongpass123"
}
```

#### `POST /auth/login`

Возвращает bearer token.

Пример запроса:

```json
{
  "email": "user@example.com",
  "password": "strongpass123"
}
```

Пример ответа:

```json
{
  "access_token": "token",
  "token_type": "bearer"
}
```

### Links

#### `POST /links/shorten`

Создает короткую ссылку. Доступно и анонимному, и авторизованному пользователю.

Пример запроса:

```json
{
  "original_url": "https://example.com/very/long/path",
  "custom_alias": "my-link",
  "expires_at": "2026-03-20T12:30:00+00:00"
}
```

Поля:

- `custom_alias` — необязательный кастомный алаяс
- `expires_at` — необязательное время истечения с точностью до минуты

#### `GET /links/{short_code}`

Перенаправляет на оригинальный URL и увеличивает счетчик переходов.

#### `GET /links/{short_code}/stats`

Возвращает статистику:

```json
{
  "short_code": "my-link",
  "original_url": "https://example.com/very/long/path",
  "created_at": "2026-03-13T11:00:00Z",
  "expires_at": "2026-03-20T12:30:00Z",
  "last_used_at": "2026-03-13T11:15:00Z",
  "click_count": 5
}
```

#### `GET /links/history/expired`

Возвращает историю ссылок, которые были автоматически удалены после наступления `expires_at`.

Пример ответа:

```json
[
  {
    "short_code": "my-link",
    "original_url": "https://example.com/very/long/path",
    "created_at": "2026-03-13T11:00:00Z",
    "expires_at": "2026-03-20T12:30:00Z",
    "last_used_at": "2026-03-13T11:15:00Z",
    "click_count": 5,
    "deleted_at": "2026-03-20T12:30:04Z",
    "deletion_reason": "expired"
  }
]
```

#### `GET /links/search?original_url=...`

Ищет все активные короткие ссылки для заданного `original_url`.

Пример:

```text
GET /links/search?original_url=https://example.com/very/long/path
```

#### `PUT /links/{short_code}`

Обновляет `original_url` у ссылки.

Требует авторизацию владельца.

Пример запроса:

```json
{
  "original_url": "https://example.com/new-path"
}
```

#### `DELETE /links/{short_code}`

Удаляет ссылку.

Требует авторизацию владельца.

## Кэширование

В Redis кэшируются:

- `GET /links/search`
- `GET /links/{short_code}/stats`

Кэш инвалидируется при:

- `POST /links/shorten`
- `GET /links/{short_code}`
- `PUT /links/{short_code}`
- `DELETE /links/{short_code}`
- автоудалении истекших ссылок

TTL кэша ограничивается не только `CACHE_TTL_SECONDS`, но и `expires_at` самой ссылки, чтобы истекшая ссылка не могла продолжать возвращаться из Redis.

## Автоудаление истекших ссылок

Приложение запускает фоновую задачу, которая периодически удаляет ссылки с наступившим `expires_at`.
До фактической очистки такие ссылки все равно считаются неактивными и не возвращаются из API.

## Удаление неиспользуемых ссылок

Если по ссылке не было переходов в течение `UNUSED_LINK_DAYS`, она автоматически удаляется.
Если переходов не было вообще, отсчет ведется от `created_at`.

## Структура БД

### Таблица `users`

- `id` — UUID пользователя
- `email` — уникальный email
- `password_hash` — хэш пароля
- `created_at` — время создания пользователя

### Таблица `links`

- `id` — числовой идентификатор
- `short_code` — уникальный короткий код
- `original_url` — исходная ссылка
- `owner_id` — владелец ссылки, может быть `NULL` для анонимной ссылки
- `created_at` — время создания
- `expires_at` — срок жизни ссылки
- `last_used_at` — время последнего перехода
- `click_count` — число переходов

### Таблица `archived_links`

- `short_code` — короткий код удаленной ссылки
- `original_url` — исходная ссылка
- `owner_id` — владелец, если он был
- `created_at` — время создания ссылки
- `expires_at` — срок жизни ссылки
- `last_used_at` — время последнего перехода
- `click_count` — число переходов на момент удаления
- `deletion_reason` — причина удаления (`expired` или `unused`)
- `deleted_at` — время архивирования
