# Как опубликовать подготовленный final release

Код и локальный тег готовы. GitHub не изменён. Репозиторий назначения:
https://github.com/despi4/RMT_Assignment4

На 16 ноября 2026 удалённая main была
`8b1f9b43c8953b4963146833d3cd0da44d7c07dc`, тег `final` отсутствовал.
До публикации участники должны проверить материалы и согласовать сведения.
Не включайте частные письма преподавателя, отчёт сходства или адреса в код.

## 1. Получить рабочую копию

Распакуйте GitHub_Ready.zip в новую папку. Откройте в ней PowerShell.
Нужны Git и Python 3.10+; вход в GitHub понадобится только при push.
Если `git` не найден, укажите полный путь к установленному git.exe.

```powershell
git clone .inal.bundle RMT_Final
cd RMT_Final
git switch main
git remote set-url origin https://github.com/despi4/RMT_Assignment4.git
python final_tools/analyze_public.py
python -m unittest discover -s final_tools -p "test_public.py" -v
git diff --exit-code -- results/final_paper
```

Каждая команда должна завершиться без ошибки. Остановитесь при любой ошибке.
`source/` в архиве — копия тех же файлов для просмотра, не второй проект.
Bundle сохраняет историю и локальный тег. Не создавайте новый README через
веб-интерфейс поверх уже существующей ветки.

## 2. Обновить только фактически завершённые пункты

После реальных подтверждений исправьте `final_tools/final_readiness.csv`,
`RELEASE_NOTES.md` и статус в README, а также Appendix B и Declarations
в документах. Сохраните приватные подтверждения отдельно от репозитория.
Пустую `AUTHOR_CONFIRMATIONS.txt` скопируйте вне проекта перед заполнением.

Если менялись файлы кода/результатов, добавляйте явно только проверенные пути:

```powershell
git add final_tools/final_readiness.csv README.md RELEASE_NOTES.md
git commit -m "Record completed final submission checks"
```

Не выполняйте commit, если изменений нет. Для новых реальных review/reproduction
файлов сначала проверьте содержимое, затем добавьте их явно по пути.

## 3. Проверить удалённую ветку и тег

```powershell
git fetch origin main
git merge-base --is-ancestor origin/main HEAD
```

Сразу проверьте `$LASTEXITCODE`: должно быть 0. Иное значение означает,
что на GitHub есть несогласованные изменения: остановитесь, не используйте force.

```powershell
git ls-remote --tags origin refs/tags/final
```

Вывод должен быть пустым. Если тег уже есть, остановитесь и сравните версии;
не перезаписывайте опубликованный тег. После последнего локального изменения
и только при отсутствии remote final обновите свой ещё не опубликованный тег:

```powershell
git tag -f -a final -m "Final course reproducibility package; see readiness checklist"
git status --short
git show --stat --oneline final
```

Рабочая папка должна быть чистой. Здесь `-f` меняет только локальный тег;
force push не нужен и в инструкции отсутствует.

## 4. Опубликовать согласованную версию

После проверки файлов владелец репозитория выполняет:

```powershell
git push --atomic origin main refs/tags/final
```

Войдите своим аккаунтом при запросе GitHub. При отказе не используйте force.
Откройте Actions и дождитесь успешного `Verify final paper results` на Python
3.10 и 3.12. Workflow проверяет архивные ответы, а не повторяет запуск модели.
Локальная проверка выполнена на Python 3.12; запуск GitHub Actions пока не заявлен.

## 5. Создать GitHub Release

Откройте https://github.com/despi4/RMT_Assignment4/releases/new
Выберите УЖЕ опубликованный тег `final`. Название: `Final project`.
Вставьте текст `RELEASE_NOTES.md`, обновив только реально закрытые пункты.
Нажмите Publish release после просмотра. Прикрепление учебных DOCX/PDF
не требуется для воспроизводимости: код, CSV/SVG, данные и логи уже в source.
Полный учебный архив сдайте в Moodle; не публикуйте его без согласия авторов.

Проверьте ссылку https://github.com/despi4/RMT_Assignment4/releases/tag/final
и передайте её преподавателю. Если позже меняете результаты или документ,
не утверждайте, что прежний тег содержит новую версию: согласуйте новый релиз.
