# bes-rules-sandbox

Пісочниця для перевірки правил гілок і PR-перевірок перед увімкненням їх у робочому
репозиторії. Коду плагіна тут немає: лише скрипт правил, workflow і два фіктивні файли.

| Файл | Навіщо |
|---|---|
| `tools/CheckRules/check_rules.py`, `baseline.json` | та сама перевірка правил, що в робочому репозиторії |
| `.github/workflows/pr-checks.yml` | `Code rules` і `Branch and PR title` — як у робочому; `Build (Debug R26) and smoke tests` — заглушка з тією ж назвою |
| `source/Sample/LegacyTool.cs` | «старий» код із порушеннями, дозволеними baseline |
| `source/Sample/Calculator.cs` | чистий файл для тестових змін |
| `.github/CODEOWNERS` | обов'язкові рев'юери — `@vitdevdotnet` і `@vitaliibarantsov` (Vitalii Barantsov), достатньо одного |

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

| # | Дія | Очікування | Факт (2026-11-04) |
|---|---|---|---|
| 1 | `git push origin dev` напряму | відмова | ✅ відмова: `GH013: Repository rule violations found for refs/heads/dev` |
| 2 | PR з гілки `test/foo`, заголовок `Add stuff` | `Branch and PR title` червоний, Merge заблоковано | ✅ PR #3: `Branch and PR title` fail — «Branch 'test/foo' must be feature/<name>…» і «PR title 'Add stuff' must follow Conventional Commits…»; Merge заблоковано |
| 3 | PR `feature/cyrillic`, `chore: test`; у `Calculator.cs` додати коментар кирилицею | `Code rules` червоний | ✅ PR #4: `Code rules` fail — «[cyrillic] … 1 found, baseline allows 0; lines 3» |
| 4 | PR `feature/lookup`, `chore: test`; у `LegacyTool.cs` додати ще один `LookupParameter(` | `Code rules` червоний (baseline дозволяє лише 1) | ✅ PR #5: `Code rules` fail — «[lookup-parameter] … 2 found, baseline allows 1; lines 10, 11» |
| 5 | PR `feature/clean-change`, `feat(sample): add subtract`; чиста зміна в `Calculator.cs` | усі перевірки зелені, Merge заблоковано до схвалення | ✅ PR #1: три перевірки pass, стан `BLOCKED` / `REVIEW_REQUIRED` |
| 6 | Схвалення PR із п. 5 від `vitdevdotnet` | Merge доступний | ✅ після Approve стан `CLEAN`, Merge доступний |
| 7 | Після схвалення додати ще один коміт у PR | схвалення знято, Merge знову заблоковано | ✅ коміт `feat(sample): add multiply` → обидва схвалення `DISMISSED`, стан `BLOCKED` |
| 8 | PR `dev` → `master`, заголовок `CHANGE ASSEMBLY VERSION TO 1.0.0.0` | назва прийнята; потрібне схвалення | ✅ PR #6 з `release/1.0.0.0` → `master` (у `dev` і `master` був один коміт, PR без різниці неможливий): назва прийнята, перевірки pass, Merge заблоковано до схвалення |
| 9 | Спробувати видалити гілку `dev` | відмова | ✅ `master`: «GH013 … Cannot delete this branch» (ruleset); `dev`: «Cannot delete the default branch» (вбудований захист GitHub) |

## Додаткові спостереження

- Required check «Require branches to be up to date» працює: перед злиттям PR #1 у його гілку довелося підтягнути свіжий `dev`.
- `CODEOWNERS` береться з базової гілки: `@vitaliibarantsov` став code owner лише після злиття PR #7, після чого його схвалення розблокувало PR #1.
- Гілки після злиття видаляються автоматично.
- Перший PR GitHub Actions пропустив (workflow не зареєструвався, push інколи повертав 500); допоміг новий PR зі зміною в самому workflow.
- У приватному репозиторії організації на GitHub Free rulesets недоступні (HTTP 403) — потрібен GitHub Team.
