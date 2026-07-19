## zapret-web-panel v1.8.0

Исправлена пустая панель с ошибкой "forbidden" у части пользователей.

### Что нового
- На некоторых машинах (другая версия WebView2 Runtime) окно панели вместо интерфейса показывало `{"error": "forbidden"}` — сервер панели проверял заголовок `Host` слишком строго (только `127.0.0.1:8756`), а WebView2 у части пользователей обращался как `localhost:8756`. Теперь принимаются оба варианта. Заодно это объясняет, почему у таких пользователей не срабатывал фикс случайной печати из v1.6.0 — сама страница просто не успевала загрузиться.

---

## zapret-web-panel v1.8.0 (English)

Fixed a blank "forbidden" panel some users hit.

### What's new
- On some machines (a different WebView2 Runtime build) the panel window showed a raw `{"error": "forbidden"}` instead of the UI — the panel's server checked the `Host` header too strictly (only `127.0.0.1:8756`), while WebView2 sent `localhost:8756` for some users. Both are now accepted. This also explains why the accidental-printing fix from v1.6.0 didn't seem to help those users — the page itself was never actually loading.

---

## zapret-web-panel v1.7.0

Автоустановка WebView2 Runtime на Windows 10.

### Что нового
- На Windows 11 WebView2 Runtime встроен в систему, а на Windows 10 — нет, из-за чего панель без этого компонента тихо открывалась как вкладка браузера вместо отдельного окна. Теперь при первом запуске панель сама проверяет наличие компонента и, если его нет, автоматически скачивает и устанавливает официальный WebView2 Runtime от Microsoft (нужен интернет, разово может занять до минуты) — с предупреждением, чтобы пауза не выглядела зависанием.

---

## zapret-web-panel v1.7.0 (English)

Auto-install WebView2 Runtime on Windows 10.

### What's new
- Windows 11 ships WebView2 Runtime built in; Windows 10 doesn't, so without it the panel silently opened as a browser tab instead of its own window. Now, on first launch, the panel checks for the component and, if missing, automatically downloads and installs Microsoft's official WebView2 Runtime (needs internet, may take up to a minute the first time) — with a heads-up message so the pause doesn't look like a hang.

---

## zapret-web-panel v1.6.0

Исправлена случайная печать поверх окна панели.

### Что нового
- Заблокированы браузерные горячие клавиши (Ctrl+P/F/R, F5, F12), которые не нужны в оконном приложении — у одного из тестировщиков случайное нажатие Ctrl+P открывало сломанную панель предпросмотра печати WebView2 поверх интерфейса.

---

## zapret-web-panel v1.6.0 (English)

Fixed accidental printing appearing over the panel window.

### What's new
- Blocked browser keyboard shortcuts (Ctrl+P/F/R, F5, F12) that serve no purpose in a windowed app — a tester hit Ctrl+P by accident and got WebView2's own (broken-rendering) print-preview toolbar over the interface.

---

## zapret-web-panel v1.5.0

Необязательная ссылка на поддержку проекта.

### Что нового
- В настройках панели и в README появилась скромная ссылка «Поддержать проект» (DonationAlerts) — полностью необязательная.

---

## zapret-web-panel v1.5.0 (English)

An optional link to support the project.

### What's new
- A low-key "Support the project" link (DonationAlerts) in the panel's settings footer and in the README — entirely optional.

---

## zapret-web-panel v1.4.0

Редактор списков доменов и IP прямо в панели.

### Что нового
- **Домены и IP** — новый раздел: редактирование `list-general-user.txt` (домены, которые zapret точно будет обходить), `list-exclude-user.txt` (домены, которые zapret не будет трогать вообще) и `ipset-exclude-user.txt` (то же самое по IP/подсетям) для выбранной версии — без похода в проводник и блокнот. Эти списки применяют все стратегии `general*.bat` одинаково.

Подробности — в [README](https://github.com/e24x5-Fox/zapret-web-panel#readme).

**Неофициальный, независимый компаньон-инструмент — не аффилирован с zapret-discord-youtube.**

---

## zapret-web-panel v1.4.0 (English)

An in-panel editor for the domain/IP user lists.

### What's new
- **Domains & IP** — a new section: edit `list-general-user.txt` (domains zapret will always bypass), `list-exclude-user.txt` (domains zapret leaves alone entirely), and `ipset-exclude-user.txt` (the same, by IP/subnet) for the selected version — no more Notepad/Explorer round-trip. Every `general*.bat` strategy of a version reads these the same way.

See the [README](https://github.com/e24x5-Fox/zapret-web-panel#readme) for details.

**Unofficial, independent companion tool — not affiliated with zapret-discord-youtube.**

---

## zapret-web-panel v1.3.0

Скачивание оригинальных релизов zapret прямо из панели, плюс пояснение по антивирусам.

### Что нового
- **Скачивание релизов внутри панели** — новый раздел "Скачать релизы": можно выбрать и скачать любой релиз [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) (с проверкой контрольной суммы sha256 против официального GitHub) или последнюю сборку [zapret-win-bundle](https://github.com/bol-van/zapret-win-bundle) для Zapret2 — без ручного скачивания и распаковки zip-архивов. Файлы попадают в папку `zapret/zapret1` и `zapret/zapret2` рядом с панелью и сразу появляются в списке версий.
- **Пояснение по антивирусам** — в README и в самой панели добавлено объяснение, почему антивирусы иногда помечают `zapret-web-panel.exe` или файлы WinDivert/winws: это задокументированный ложноположительный паттерн для неподписанных PyInstaller-сборок и низкоуровневых сетевых драйверов, а не признак заражения.

Подробности — в [README](https://github.com/e24x5-Fox/zapret-web-panel#readme).

**Неофициальный, независимый компаньон-инструмент — не аффилирован с zapret-discord-youtube.**

---

## zapret-web-panel v1.3.0 (English)

Download original zapret releases right from the panel, plus antivirus context.

### What's new
- **In-app release downloader** — a new "Download releases" section: pick and download any [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) release (verified against GitHub's own sha256 checksum) or the latest [zapret-win-bundle](https://github.com/bol-van/zapret-win-bundle) build for Zapret2 — no manual zip download/extraction needed. Files land in `zapret/zapret1` and `zapret/zapret2` next to the panel and show up in the version list immediately.
- **Antivirus context** — the README and the panel itself now explain why antivirus software sometimes flags `zapret-web-panel.exe` or the WinDivert/winws files: a documented false-positive pattern for unsigned PyInstaller builds and low-level network drivers, not a sign of infection.

See the [README](https://github.com/e24x5-Fox/zapret-web-panel#readme) for details.

**Unofficial, independent companion tool — not affiliated with zapret-discord-youtube.**

---

## zapret-web-panel v1.2.0

Новый альтернативный движок и более честный тест на реальную блокировку DPI.

### Что нового
- **Zapret2 как альтернативный движок** — поддержка [bol-van/zapret2](https://github.com/bol-van/zapret2) (`winws2.exe`) прямо в панели, полностью отдельно от обычного zapret: переключатель Zapret/Zapret2 на главном экране, поиск версий по всему компьютеру, запуск/остановка профилей, свой генератор стратегий (перебор комбинаций lua-desync методов). Экспериментальная, необязательная функция — основной обход по-прежнему работает через обычный zapret.
- **Более честная проверка "работает/не работает"** — тест теперь реально загружает ~64КБ данных и проверяет, не обрывается ли соединение на полпути (типичное поведение DPI, которое пропускает первые ~16-20КБ трафика, а потом рвёт соединение). Старая проверка (простой HEAD-запрос) могла показывать "всё работает", даже когда реальная блокировка активна.

Подробности — в [README](https://github.com/e24x5-Fox/zapret-web-panel#readme).

**Неофициальный, независимый компаньон-инструмент — не аффилирован с zapret-discord-youtube.**

---

## zapret-web-panel v1.2.0 (English)

A new alternative engine, plus a more honest real-world DPI block test.

### What's new
- **Zapret2 as an alternative engine** — support for [bol-van/zapret2](https://github.com/bol-van/zapret2) (`winws2.exe`) right in the panel, fully separate from the regular zapret flow: a Zapret/Zapret2 toggle on the home screen, whole-computer version scan, profile launch/stop, and its own strategy generator (searches combinations of lua-desync methods). Experimental, opt-in — the regular zapret path is still the primary bypass method.
- **A more honest working/not-working check** — the test now actually uploads ~64KB of data and checks whether the connection gets cut mid-stream (the typical behavior of DPI that lets the first ~16-20KB of traffic through, then kills the connection). The old check (a plain HEAD request) could report "everything works" even while real blocking was active.

See the [README](https://github.com/e24x5-Fox/zapret-web-panel#readme) for details.

**Unofficial, independent companion tool — not affiliated with zapret-discord-youtube.**

---

## zapret-web-panel v1.1.1

Исправления после v1.1.0:

- Убрано мелькание чёрного окна консоли, которое проскакивало каждые 1-2 секунды во время работы панели (побочный эффект перехода на оконное приложение без консоли — вспомогательные команды вроде проверки статуса winws запускали каждая своё консольное окно).
- Добавлена нормальная иконка приложения вместо стандартной иконки PyInstaller.

---

## zapret-web-panel v1.1.1 (English)

Fixes after v1.1.0:

- Removed the black console window that flashed every 1-2 seconds while the panel was running (a side effect of moving to a console-less app window — helper commands like the winws status check were each popping their own console window).
- Added a proper app icon instead of PyInstaller's generic default one.

---

## zapret-web-panel v1.1.0

Панель теперь запускается как обычное Windows-приложение — без консольного окна и без вкладки в браузере. Плюс новый интерфейс и два новых инструмента.

### Что нового
- **Полноценное окно приложения** — никакого чёрного окна консоли и открытия ссылки в браузере: интерфейс рендерится в собственном окне через системный WebView2.
- **Новый интерфейс в стиле VPN-клиента** — большой кругляшок «подключиться/отключиться» на главном экране запускает/останавливает выбранную стратегию. Всё остальное (служба, диагностика, тест, генератор стратегий, поиск версий) переехало за иконку настроек.
- **Автоматический подбор стратегии** — если ни одна из готовых стратегий не пробивает блокировку, панель может перебрать комбинации методов dpi-desync и протестировать каждую (как в «Тест»), а рабочий вариант — сохранить как обычную стратегию.
- **Поиск версий по всему компьютеру** — не только рядом с панелью: можно просканировать все диски или указать конкретную папку, посмотреть найденные пути, открыть или удалить папку версии прямо из панели.

Подробности — в [README](https://github.com/e24x5-Fox/zapret-web-panel#readme).

**Неофициальный, независимый компаньон-инструмент — не аффилирован с zapret-discord-youtube.**

---

## zapret-web-panel v1.1.0 (English)

The panel now launches as a regular Windows application — no console window, no browser tab. Plus a new interface and two new tools.

### What's new
- **A real app window** — no more black console window or a browser tab to find: the UI renders in its own window via the system WebView2 runtime.
- **New VPN-client-style interface** — a big connect/disconnect circle on the home screen starts/stops the selected strategy. Everything else (service, diagnostics, test, strategy generator, version scan) moved behind a settings icon.
- **Automatic strategy generator** — if none of the built-in strategies get through, the panel can try combinations of dpi-desync methods and test each one (like "Test"), then save a working candidate as a regular strategy.
- **Whole-computer version scan** — not just next to the panel anymore: scan every drive or point at a specific folder, see the found paths, open or delete a version folder right from the panel.

See the [README](https://github.com/e24x5-Fox/zapret-web-panel#readme) for details.

**Unofficial, independent companion tool — not affiliated with zapret-discord-youtube.**

---

## zapret-web-panel v1.0.0

Локальная веб-панель управления для [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) — замена консольного меню `service.bat` и `test zapret.ps1` одной панелью в браузере. Доступна на русском и английском (переключатель языка в интерфейсе).

**Скачать:** `zapret-web-panel.exe` ниже — не требует Python, просто положите рядом с папками версий zapret (или укажите путь через `ZAPRET_BASE_DIR`) и запустите.

### Возможности
- **Тест** — прогон стратегий по настраиваемому набору сервисов (Discord, YouTube, Cloudflare, Telegram, Twitter/X, Instagram, Facebook, TikTok, Steam, Spotify, Twitch, Reddit), включение победителя в один клик
- **Ручной запуск** любой стратегии без теста
- **Служба** — install/remove автозапуска, игровой фильтр, ipset, обновление hosts/списков — без консоли
- **Диагностика** — конфликты и здоровье системы, с исправлениями в один клик (остановка VPN-служб, чистка WinDivert, конфликтующие bypass-службы, кэш Discord)
- Localhost-защита: разовый токен на каждый запуск + проверка Host — от CSRF и DNS-rebinding

Подробности — в [README](https://github.com/e24x5-Fox/zapret-web-panel#readme).

**Неофициальный, независимый компаньон-инструмент — не аффилирован с zapret-discord-youtube.**

---

## zapret-web-panel v1.0.0 (English)

A local web control panel for [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) — replaces `service.bat`'s console menu and `test zapret.ps1` with one browser dashboard. Available in Russian and English (language switcher in the UI).

**Download:** `zapret-web-panel.exe` below — no Python required, just place it next to your zapret version folders (or point it there via `ZAPRET_BASE_DIR`) and run.

See the [README](https://github.com/e24x5-Fox/zapret-web-panel#readme) for details.

**Unofficial, independent companion tool — not affiliated with zapret-discord-youtube.**
