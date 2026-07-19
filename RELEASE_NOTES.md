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
