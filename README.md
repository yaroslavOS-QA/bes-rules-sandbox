# bes-rules-sandbox

Пісочниця для перевірки правил гілок і PR-перевірок перед увімкненням їх у робочому
репозиторії. Коду плагіна тут немає: лише скрипт правил, workflow і два фіктивні файли.

| Файл | Навіщо |
|---|---|
| `tools/CheckRules/check_rules.py`, `baseline.json` | та сама перевірка правил, що в робочому репозиторії |
| `.github/workflows/pr-checks.yml` | `Code rules` і `Branch and PR title` — як у робочому; `Build (Debug R26) and smoke tests` — заглушка з тією ж назвою |
| `source/Sample/LegacyTool.cs` | «старий» код із порушеннями, дозволеними baseline |
| `source/Sample/Calculator.cs` | чистий файл для тестових змін |
| `.github/CODEOWNERS` | обов'язковий рев'юер — `@vitdevdotnet` (Vitalii Barantsov) |

## Налаштування

1. Гілки `master` і `dev`, default branch — `dev`.
2. Settings → Collaborators: запросити `vitdevdotnet` (Vitalii Barantsov) з роллю Write; він має прийняти запрошення.
3. Відкрити й закрити один PR, щоб перевірки з'явилися у списку required checks.
4. Settings → Rules → Rulesets → New branch ruleset `protect-dev-master`, Active, цілі `dev` і `master`:
   - Restrict deletions, Block force pushes;
   - Require a pull request: 1 approval, dismiss stale approvals, require review from Code Owners,
     require conversation resolution;
   - Require status checks: `Code rules`, `Branch and PR title`, `Build (Debug R26) and smoke tests`.

## Сценарії перевірки

| # | Дія | Очікування | Факт |
|---|---|---|---|
| 1 | `git push origin dev` напряму | відмова | |
| 2 | PR з гілки `test/foo`, заголовок `Add stuff` | `Branch and PR title` червоний, Merge заблоковано | |
| 3 | PR `feature/cyrillic`, `chore: test`; у `Calculator.cs` додати коментар кирилицею | `Code rules` червоний | |
| 4 | PR `feature/lookup`, `chore: test`; у `LegacyTool.cs` додати ще один `LookupParameter(` | `Code rules` червоний (baseline дозволяє лише 1) | |
| 5 | PR `feature/clean-change`, `feat(sample): add subtract`; чиста зміна в `Calculator.cs` | усі перевірки зелені, Merge заблоковано до схвалення | |
| 6 | Схвалення PR із п. 5 від `vitdevdotnet` | Merge доступний | |
| 7 | Після схвалення додати ще один коміт у PR | схвалення знято, Merge знову заблоковано | |
| 8 | PR `dev` → `master`, заголовок `CHANGE ASSEMBLY VERSION TO 1.0.0.0` | назва прийнята; потрібне схвалення | |
| 9 | Спробувати видалити гілку `dev` | відмова | |

<!-- scenario 2 -->
