# Languages and Translations

[← Back to README](../README.md)

OdoDash is available in the following languages:

| Language | Code | Language | Code |
|----------|------|----------|------|
| English | `en` | Swedish (Svenska) | `sv` |
| German (Deutsch) | `de` | Danish (Dansk) | `da` |
| Spanish (Español) | `es` | Norwegian (Norsk) | `no` |
| French (Français) | `fr` | Finnish (Suomi) | `fi` |
| Italian (Italiano) | `it` | Japanese (日本語) | `ja` |
| Dutch (Nederlands) | `nl` | Chinese (中文) | `zh` |
| Portuguese (Português) | `pt` | Korean (한국어) | `ko` |
| Polish (Polski) | `pl` | Czech (Čeština) | `cs` |
| Russian (Русский) | `ru` | Turkish (Türkçe) | `tr` |
| Arabic (العربية) | `ar` | Hungarian (Magyar) | `hu` |

You can change your language in **Settings > Units & Values > Language**.

## Improving Translations

Translations were generated with AI assistance and may contain inaccuracies. If you spot an incorrect translation, contributions are very welcome:

1. Translation files are located in `app/translations/<lang>/LC_MESSAGES/messages.po`
2. Edit the `msgstr` value for any incorrect entry
3. Recompile with `pybabel compile -d app/translations` — the app reads the
   compiled `messages.mo`, so a `.po` edit on its own changes nothing until it
   is rebuilt
4. Submit a pull request with the `.po` only. The compiled `messages.mo` is a
   build artefact: it is not tracked, the container image builds it, and a
   local run rebuilds it whenever it is older than its `.po`. Git cannot merge
   a binary, so tracking it meant two people editing the same language
   collided with a conflict neither could resolve

## Adding a Language

A new catalogue is not offered until the language is registered:

1. Create `app/translations/<lang>/LC_MESSAGES/messages.po` from
   `app/translations/messages.pot` and translate it
2. Compile it with `pybabel compile -d app/translations` to check it builds —
   the resulting `messages.mo` is a build artefact and stays out of the commit
3. Add the code and its native name to `LANGUAGES` in `app/__init__.py` — this
   is what the settings picker and the browser language negotiation read, so a
   catalogue that is not listed there can never be selected
4. Add the language to the table above
