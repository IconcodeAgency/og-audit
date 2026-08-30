# OG Audit

[English version](README.md)

Проверяет SEO-метаданные, Open Graph, robots, JSON-LD и sitemap из терминала или CI.

OG Audit получает HTML, который сервер отдаёт без выполнения JavaScript, проверяет основанные на спецификациях метаданные и связанные crawler-ресурсы, затем формирует console, JSON или автономный HTML-отчёт. Требования протоколов отделены от эвристик длины title и description.

## Что проверяется

- HTTP-статус, HTTPS, цепочка редиректов, размер ответа и HTML Content-Type.
- Title, description, язык документа, viewport, H1 и canonical.
- Директивы `robots` meta и `X-Robots-Tag`.
- Обязательные поля Open Graph: `og:title`, `og:type`, `og:image`, `og:url`.
- OG description, абсолютные URL, соответствие конечному URL, доступность и Content-Type изображения.
- Наличие Twitter Card.
- Синтаксис JSON-LD, обнаруженные типы и Schema.org context.
- `/robots.txt`, разрешение на обход страницы и объявленные sitemap.
- Валидность sitemap XML и наличие canonical-страницы.

Правила основаны на [Open Graph protocol](https://ogp.me/), [Google Search Central](https://developers.google.com/search/docs), [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) и [Sitemaps protocol](https://www.sitemaps.org/protocol.html). Длина title и description помечается как эвристика отображения, а не требование поисковой системы.

## Быстрый запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
og-audit https://example.com
```

Через Docker:

```bash
docker build -t og-audit .
docker run --rm og-audit https://example.com
```

## Форматы отчёта

```bash
# Удобная таблица в терминале
og-audit https://example.com

# JSON для CI и интеграций
og-audit https://example.com --format json --output reports/example.json

# Автономный HTML-файл
og-audit https://example.com --format html --output reports/example.html
```

Без `--output` JSON и HTML выводятся в stdout.

## Exit codes

```bash
og-audit https://example.com --fail-on error
og-audit https://example.com --fail-on warning
og-audit https://example.com --fail-on never
```

| Код | Значение |
| --- | --- |
| `0` | Аудит завершён, выбранный порог не превышен. |
| `1` | Обнаружены findings уровня `--fail-on` или выше. |
| `2` | Аудит не удалось выполнить. |

## Локальные адреса

По умолчанию блокируются private, loopback, link-local, reserved адреса и URL с логином или паролем. Для доверенного локального сайта:

```bash
og-audit http://127.0.0.1:3000 --allow-private
```

Перед созданием публичного веб-интерфейса прочитайте [SECURITY.md](SECURITY.md).

## Границы v0.1.0

Проверяется одна страница, связанное OG-изображение, robots и sitemap. Инструмент не обходит сайт целиком, не выполняет JavaScript, не загружает дочерние файлы sitemap index, не предсказывает позиции и не подтверждает право на конкретный rich result Google.

Это осознанная граница: Telegram и многие социальные crawlers должны получать метаданные уже в исходном HTML. В будущем browser adapter можно добавить без изменения формата отчёта.

## Разработка

```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

## Лицензия

[MIT](LICENSE) · Разработка [IconCode](https://iconcode.ru) · [@iconcode_support](https://t.me/iconcode_support)
