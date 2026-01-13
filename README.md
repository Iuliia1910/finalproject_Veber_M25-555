# ValutaTrade

ValutaTrade — это консольное приложение для управления валютным портфелем пользователя. 
Программа позволяет отслеживать курсы фиатных и криптовалют, покупать и продавать валюту, вести учёт портфеля и получать актуальные котировки из внешних API.

## Возможности

- Просмотр портфеля пользователя с конвертацией в базовую валюту
- Поддержка фиатных валют (USD, EUR, GBP, RUB, CNY, JPY, AED)
- Поддержка криптовалют (BTC, ETH, SOL)
- Покупка и продажа валют по актуальному курсу
- Обновление курсов с внешних API (ExchangeRate, CoinGecko)
- Ведение истории портфеля и операций
- Аутентификация пользователей

## Структура проекта

finalproject_Veber_M25-555/
│
├── data/
│ ├── users.json # данные пользователей
│ ├── portfolios.json # портфели пользователей
│ ├── rates.json # локальный кэш курсов (Core Service)
│ └── exchange_rates.json # хранилище исторических данных (Parser Service)
│
├── valutatrade_hub/
│ ├── init.py
│ ├── logging_config.py
│ ├── decorators.py
│ ├── core/
│ │ ├── init.py
│ │ ├── currencies.py # список поддерживаемых валют
│ │ ├── exceptions.py # пользовательские исключения
│ │ ├── models.py # модели портфеля, кошельков и пользователей
│ │ ├── usecases.py # основная логика работы с портфелем и курсами
│ │ └── utils.py # вспомогательные функции
│ ├── infra/
│ │ ├─ init.py
│ │ ├── settings.py # конфигурация проекта
│ │ └── database.py # работа с JSON-базами
│ ├── parser_service/
│ │ ├── init.py
│ │ ├── config.py # параметры API и обновления курсов
│ │ ├── api_clients.py # запросы к внешним API
│ │ ├── updater.py # обновление курсов и кэширование
│ │ ├── storage.py # чтение/запись exchange_rates.json
│ │ └── scheduler.py # планировщик периодического обновления
│ └── cli/
│ ├─ init.py
│ └─ interface.py # консольный интерфейс пользователя
│
├── main.py # точка входа приложения
├── Makefile # команды для запуска, тестов и линтинга
├── poetry.lock
├── pyproject.toml
├── README.md
└── .gitignore

bash
Копировать код

## Установка

Клонируйте репозиторий и установите зависимости через Poetry:

```
git clone https://github.com/Iuliia1910/finalproject_Veber_M25-555
cd finalproject_veber_m25_555
poetry install
```

Запуск приложения
``` 
poetry run project
```
После запуска появится консольный интерфейс:


valutatrade>
Команды
login <username> — вход пользователя

logout — выход из системы

portfolio — показать текущий портфель

update_rates — обновить курсы валют

buy <currency> <amount> — купить валюту

sell <currency> <amount> — продать валюту

help — показать список команд

exit — выйти из программы

Примеры использования

valutatrade(alice)> portfolio 
valutatrade(alice)> update_rates
valutatrade(alice)> buy EUR 100
valutatrade(alice)> sell BTC 1
valutatrade(alice)> logout
