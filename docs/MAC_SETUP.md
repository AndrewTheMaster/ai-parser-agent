# Mac: запуск и DMG

## Где лежит список слов (авто-поиск)

Рядом с `.dmg` на диске (рекомендуется для DMG), в порядке приоритета:

`terms.txt` → `words.txt` → `sample_terms.txt` → `my_terms.txt`

Иначе: `data/sample_terms.txt` внутри проекта, или `../terms.txt` рядом с папкой проекта.

Запуск без аргументов: `bash ./run_simple.sh` — подставит термины и словари сам, если файлы лежат по правилам выше.

## Где лежат словари (авто-поиск)

Скрипт `run_simple.sh` ищет PDF в таком порядке:

1. `<проект>/dictionaries/`
2. `<родитель проекта>/dictionaries/` — удобно, если папку проекта положили на Рабочий стол рядом с `dictionaries`.
3. **Только macOS:** если проект открыт с **смонтированного DMG**, берётся путь к файлу `.dmg` и проверяется папка  
   `<та же папка, что и .dmg>/dictionaries/`  
   Пример: `Desktop/LegalTermsAgent-0.1.0.dmg` и `Desktop/dictionaries/*.pdf`.

## Куда пишется результат

- Если папка проекта **доступна для записи** → по умолчанию  
  `<проект>/output_simple/results_human.xlsx`  
  (или путь из третьего аргумента `run_simple.sh`).
- Если том **только чтение** (частый случай с DMG) →  
  `~/Library/Application Support/LegalTermsAgent/output_simple/results_human.xlsx`  
  Туда же уходят `.venv` и кэш индекса.

## Команда с нуля

```bash
git clone https://github.com/AndrewTheMaster/ai-parser-agent.git
cd ai-parser-agent
bash ./run_simple.sh
```

Рядом положите `terms.txt` и папку `dictionaries/` (или используйте варианты из разделов выше).

## DMG

Собирается **только на macOS**: `bash scripts/macos/build_dmg.sh`  
(на Linux утилиты `hdiutil` нет.)
