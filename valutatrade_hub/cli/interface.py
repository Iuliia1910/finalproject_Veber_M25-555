import argparse
import sys
import cmd
import json
import os
from valutatrade_hub.core.usecases import AuthManager, PortfolioManager, RateManager


class ValutaTradeCLI:
    """CLI интерфейс для ValutaTrade Hub."""

    def __init__(self):
        self.auth_manager = AuthManager()
        self.portfolio_manager = PortfolioManager()
        self.rate_manager = RateManager()

    def register(self, args):
        """Команда register: создать нового пользователя."""
        try:
            # Валидация
            if not args.username or not args.username.strip():
                print("Ошибка: имя пользователя не может быть пустым")
                return 1

            if len(args.password) < 4:
                print("Ошибка: пароль должен быть не короче 4 символов")
                return 1

            # Регистрация через AuthManager
            user = self.auth_manager.register(args.username, args.password)
            print(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}).")
            print(f"Войдите: login --username {user.username} --password ****")
            return 0

        except ValueError as e:
            print(f"Ошибка: {e}")
            return 1

    def login(self, args):
        """Команда login: войти в систему."""
        try:
            if not args.username or not args.username.strip():
                print("Ошибка: имя пользователя не может быть пустым")
                return 1

            user = self.auth_manager.login(args.username, args.password)
            print(f"Вы вошли как '{user.username}'")
            return 0

        except ValueError as e:
            print(f"Ошибка: {e}")
            return 1

    def show_portfolio(self, args):
        """Команда show-portfolio: показать портфель."""
        # Проверка авторизации
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 1

        # Валидация базовой валюты
        base_currency = (args.base or "USD").upper()

        # Получение данных
        user = self.auth_manager.get_current_user()
        portfolio = self.portfolio_manager.get_portfolio(user.user_id)
        wallets = portfolio.wallets

        print(f"\nПортфель пользователя '{user.username}' (база: {base_currency}):")
        print("-" * 60)

        # Если портфель пустой
        if not wallets:
            print("  Ваш портфель пуст")
            return 0

        # Расчет общей стоимости
        total_value = 0

        for currency, wallet in wallets.items():
            balance = wallet.balance

            # Расчет стоимости в базовой валюте
            if currency == base_currency:
                value = balance
                rate_info = "1.0000"
            else:
                try:
                    rate = self.rate_manager.get_rate(currency, base_currency)
                    value = balance * rate
                    rate_info = f"{rate:.4f}"
                except Exception:
                    print(f"Ошибка: неизвестная базовая валюта '{base_currency}'")
                    return 1

            total_value += value

            # Форматированный вывод
            if currency in ["BTC", "ETH"]:
                print(f"  - {currency}: {balance:.4f}  → {value:.2f} {base_currency}")
            else:
                print(f"  - {currency}: {balance:.2f}  → {value:.2f} {base_currency}")

        print("-" * 60)
        print(f"  ИТОГО: {total_value:,.2f} {base_currency}")
        return 0

    def buy(self, args):
        """Команда buy: купить валюту."""
        # Проверка авторизации
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 1

        # Валидация
        currency = args.currency.upper()
        amount = args.amount

        if amount <= 0:
            print("Ошибка: 'amount' должен быть положительным числом")
            return 1

        if not currency:
            print("Ошибка: код валюты не может быть пустым")
            return 1

        try:
            user = self.auth_manager.get_current_user()
            result = self.portfolio_manager.buy_currency(
                user.user_id,
                currency,
                amount
            )

            print(f"\nПокупка выполнена: {amount:.4f} {currency} "
                  f"по курсу {result['rate']:.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"  - {currency}: было 0.0000 → стало {result['new_balance']:.4f}")
            print(f"  Оценочная стоимость покупки: {result['cost_usd']:,.2f} USD")

            return 0

        except ValueError as e:
            print(f"Ошибка: {e}")
            return 1
        except Exception as e:
            print(f"Ошибка: не удалось получить курс для {currency}→USD")
            return 1

    def sell(self, args):
        """Команда sell: продать валюту."""
        # Проверка авторизации
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 1

        # Валидация
        currency = args.currency.upper()
        amount = args.amount

        if amount <= 0:
            print("Ошибка: 'amount' должен быть положительным числом")
            return 1

        if not currency:
            print("Ошибка: код валюты не может быть пустым")
            return 1

        try:
            user = self.auth_manager.get_current_user()
            result = self.portfolio_manager.sell_currency(
                user.user_id,
                currency,
                amount
            )

            print(f"\nПродажа выполнена: {amount:.4f} {currency} "
                  f"по курсу {result['rate']:.2f} USD/{currency}")
            print("Изменения в портфеле:")
            print(f"  - {currency}: было {result['new_balance'] + amount:.4f} → "
                  f"стало {result['new_balance']:.4f}")
            print(f"  Оценочная выручка: {result['revenue_usd']:,.2f} USD")

            return 0

        except ValueError as e:
            if "нет кошелька" in str(e).lower():
                print(f"Ошибка: у вас нет кошелька '{currency}'. "
                      f"Добавьте валюту: она создаётся автоматически при первой покупке.")
            elif "недостаточно средств" in str(e).lower():
                print(f"Ошибка: недостаточно средств")
            else:
                print(f"Ошибка: {e}")
            return 1
        except Exception as e:
            print(f"Ошибка: не удалось получить курс для {currency}→USD")
            return 1

    def get_rate(self, args):
        """Команда get-rate: получить курс валюты."""
        # Валидация
        from_currency = args.from_currency.upper()
        to_currency = args.to_currency.upper()

        if not from_currency or not to_currency:
            print("Ошибка: коды валют не могут быть пустыми")
            return 1

        if from_currency == to_currency:
            print(f"Курс {from_currency}→{to_currency}: 1.000000")
            return 0

        try:
            # Получение курса
            rate = self.rate_manager.get_rate(from_currency, to_currency)

            # Получение времени обновления
            rates_data = self.rate_manager._load_rates()
            last_refresh = rates_data.get("last_refresh", "Неизвестно")

            # Форматирование времени
            if last_refresh != "Неизвестно":
                from datetime import datetime
                dt = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
                last_refresh = dt.strftime("%Y-%m-%d %H:%M:%S")

            print(f"Курс {from_currency}→{to_currency}: {rate:.8f} (обновлено: {last_refresh})")
            print(f"Обратный курс {to_currency}→{from_currency}: {1 / rate:.8f}")

            return 0

        except Exception as e:
            print(f"Ошибка: курс {from_currency}→{to_currency} недоступен. Повторите попытку позже.")
            return 1

    def run(self):
        """Запуск CLI из командной строки."""
        parser = argparse.ArgumentParser(
            description="ValutaTrade Hub - управление валютными портфелями",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Примеры использования:
  project register --username alice --password 1234
  project login --username alice --password 1234
  project show-portfolio --base EUR
  project buy --currency BTC --amount 0.01
  project sell --currency BTC --amount 0.005
  project get-rate --from USD --to BTC

Поддерживаемые валюты: USD, EUR, BTC, ETH, RUB, CNY, GBP
            """
        )

        subparsers = parser.add_subparsers(
            dest="command",
            help="Доступные команды"
        )

        # Команда register
        register_parser = subparsers.add_parser(
            "register",
            help="Создать нового пользователя"
        )
        register_parser.add_argument(
            "--username",
            required=True,
            help="Имя пользователя (уникальное)"
        )
        register_parser.add_argument(
            "--password",
            required=True,
            help="Пароль (минимум 4 символа)"
        )
        register_parser.set_defaults(func=self.register)

        # Команда login
        login_parser = subparsers.add_parser(
            "login",
            help="Войти в систему"
        )
        login_parser.add_argument(
            "--username",
            required=True,
            help="Имя пользователя"
        )
        login_parser.add_argument(
            "--password",
            required=True,
            help="Пароль"
        )
        login_parser.set_defaults(func=self.login)

        # Команда show-portfolio
        portfolio_parser = subparsers.add_parser(
            "show-portfolio",
            help="Показать портфель"
        )
        portfolio_parser.add_argument(
            "--base",
            default="USD",
            help="Базовая валюта для конвертации (по умолчанию: USD)"
        )
        portfolio_parser.set_defaults(func=self.show_portfolio)

        # Команда buy
        buy_parser = subparsers.add_parser(
            "buy",
            help="Купить валюту"
        )
        buy_parser.add_argument(
            "--currency",
            required=True,
            help="Код покупаемой валюты (например, BTC)"
        )
        buy_parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="Количество покупаемой валюты"
        )
        buy_parser.set_defaults(func=self.buy)

        # Команда sell
        sell_parser = subparsers.add_parser(
            "sell",
            help="Продать валюту"
        )
        sell_parser.add_argument(
            "--currency",
            required=True,
            help="Код продаваемой валюты"
        )
        sell_parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="Количество продаваемой валюты"
        )
        sell_parser.set_defaults(func=self.sell)

        # Команда get-rate
        rate_parser = subparsers.add_parser(
            "get-rate",
            help="Получить курс валюты"
        )
        rate_parser.add_argument(
            "--from",
            dest="from_currency",
            required=True,
            help="Исходная валюта"
        )
        rate_parser.add_argument(
            "--to",
            dest="to_currency",
            required=True,
            help="Целевая валюта"
        )
        rate_parser.set_defaults(func=self.get_rate)

        # Парсинг аргументов
        if len(sys.argv) == 1:
            parser.print_help()
            return 0

        args = parser.parse_args()

        if hasattr(args, 'func'):
            return args.func(args)
        else:
            parser.print_help()
            return 0


class InteractiveCLI(cmd.Cmd):
    """Интерактивная оболочка ValutaTrade Hub."""

    intro = """
╔══════════════════════════════════════════╗
║    Добро пожаловать в ValutaTrade Hub!   ║
║  Введите команду или 'help' для справки  ║
║  Введите 'exit' для выхода               ║
╚══════════════════════════════════════════╝
"""
    prompt = "valutatrade> "

    def __init__(self, cli):
        super().__init__()
        self.cli = cli
        self.current_user = None

    def do_register(self, arg):
        """register - создать нового пользователя"""
        if not arg:
            # Интерактивная регистрация
            print("\n" + "=" * 50)
            print("РЕГИСТРАЦИЯ НОВОГО ПОЛЬЗОВАТЕЛЯ".center(50))
            print("=" * 50)

            # Логин с проверкой уникальности
            while True:
                username = input("\nИмя пользователя: ").strip()
                if not username:
                    print("❌ Имя пользователя не может быть пустым")
                    continue

                if not self._is_username_available(username):
                    print(f"❌ Имя пользователя '{username}' уже занято")
                    return  # Выходим, не запрашивая пароль

                break

            # Пароль с проверкой длины
            while True:
                password = input("Пароль (минимум 4 символа): ")
                if len(password) < 4:
                    print("❌ Пароль должен быть не короче 4 символов")
                    continue
                break

            arg = f"--username {username} --password {password}"
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: register username password")
                print("Пример: register alice 1234")
                return

            username, password = parts

            # Проверка уникальности логина
            if not self._is_username_available(username):
                print(f"❌ Имя пользователя '{username}' уже занято")
                return

        # Выполнение регистрации
        class Args:
            pass

        args_obj = Args()

        # Парсим аргументы
        if arg.startswith("--username"):
            # Формат с флагами
            import shlex
            parsed = shlex.split(arg)
            for i in range(0, len(parsed), 2):
                if parsed[i] == "--username":
                    args_obj.username = parsed[i + 1]
                elif parsed[i] == "--password":
                    args_obj.password = parsed[i + 1]
        else:
            # Простой формат
            parts = arg.split()
            if len(parts) >= 2:
                args_obj.username = parts[0]
                args_obj.password = parts[1]

        args_obj.func = self.cli.register
        self.cli.register(args_obj)

    def do_login(self, arg):
        """login - войти в систему"""
        if not arg:
            # Интерактивный вход
            print("\n" + "=" * 50)
            print("ВХОД В СИСТЕМУ".center(50))
            print("=" * 50)

            username = input("\nИмя пользователя: ").strip()
            if not username:
                print("❌ Имя пользователя не может быть пустым")
                return

            password = input("Пароль: ")

            arg = f"--username {username} --password {password}"
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: login username password")
                print("Пример: login alice 1234")
                return

        # Выполнение входа
        class Args:
            pass

        args_obj = Args()

        # Парсим аргументы
        if arg.startswith("--username"):
            import shlex
            parsed = shlex.split(arg)
            for i in range(0, len(parsed), 2):
                if parsed[i] == "--username":
                    args_obj.username = parsed[i + 1]
                elif parsed[i] == "--password":
                    args_obj.password = parsed[i + 1]
        else:
            parts = arg.split()
            if len(parts) >= 2:
                args_obj.username = parts[0]
                args_obj.password = parts[1]

        args_obj.func = self.cli.login
        result = self.cli.login(args_obj)

        if result == 0:
            # Обновляем prompt с именем пользователя
            if hasattr(args_obj, 'username'):
                self.current_user = args_obj.username
                self.prompt = f"valutatrade({self.current_user})> "

    def do_logout(self, arg):
        """logout - выйти из системы"""
        self.cli.auth_manager.logout()
        self.current_user = None
        self.prompt = "valutatrade> "
        print("✅ Вы вышли из системы.")

    def do_portfolio(self, arg):
        """show-portfolio - показать портфель"""

        class Args:
            pass

        args_obj = Args()

        # Парсим опциональный аргумент --base
        if arg and arg.startswith("--base"):
            parts = arg.split()
            if len(parts) == 2:
                args_obj.base = parts[1]
        else:
            args_obj.base = "USD"

        args_obj.func = self.cli.show_portfolio
        self.cli.show_portfolio(args_obj)

    def do_buy(self, arg):
        """buy - купить валюту"""
        if not arg:
            # Интерактивная покупка
            print("\n" + "=" * 50)
            print("ПОКУПКА ВАЛЮТЫ".center(50))
            print("=" * 50)

            currency = input("\nКод валюты (например, BTC, EUR): ").upper()
            if not currency:
                print("❌ Код валюты не может быть пустым")
                return

            while True:
                try:
                    amount = float(input(f"Количество {currency} для покупки: "))
                    if amount <= 0:
                        print("❌ Количество должно быть положительным числом")
                        continue
                    break
                except ValueError:
                    print("❌ Введите корректное число")

            arg = f"--currency {currency} --amount {amount}"
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: buy currency amount")
                print("Пример: buy BTC 0.01")
                return

        # Выполнение покупки
        class Args:
            pass

        args_obj = Args()

        # Парсим аргументы
        if arg.startswith("--currency"):
            import shlex
            parsed = shlex.split(arg)
            for i in range(0, len(parsed), 2):
                if parsed[i] == "--currency":
                    args_obj.currency = parsed[i + 1]
                elif parsed[i] == "--amount":
                    args_obj.amount = float(parsed[i + 1])
        else:
            parts = arg.split()
            if len(parts) >= 2:
                args_obj.currency = parts[0]
                try:
                    args_obj.amount = float(parts[1])
                except ValueError:
                    print("❌ Количество должно быть числом")
                    return

        args_obj.func = self.cli.buy
        self.cli.buy(args_obj)

    def do_sell(self, arg):
        """sell - продать валюту"""
        if not arg:
            # Интерактивная продажа
            print("\n" + "=" * 50)
            print("ПРОДАЖА ВАЛЮТЫ".center(50))
            print("=" * 50)

            currency = input("\nКод валюты (например, BTC, EUR): ").upper()
            if not currency:
                print("❌ Код валюты не может быть пустым")
                return

            while True:
                try:
                    amount = float(input(f"Количество {currency} для продажи: "))
                    if amount <= 0:
                        print("❌ Количество должно быть положительным числом")
                        continue
                    break
                except ValueError:
                    print("❌ Введите корректное число")

            arg = f"--currency {currency} --amount {amount}"
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: sell currency amount")
                print("Пример: sell BTC 0.01")
                return

        # Выполнение продажи
        class Args:
            pass

        args_obj = Args()

        # Парсим аргументы
        if arg.startswith("--currency"):
            import shlex
            parsed = shlex.split(arg)
            for i in range(0, len(parsed), 2):
                if parsed[i] == "--currency":
                    args_obj.currency = parsed[i + 1]
                elif parsed[i] == "--amount":
                    args_obj.amount = float(parsed[i + 1])
        else:
            parts = arg.split()
            if len(parts) >= 2:
                args_obj.currency = parts[0]
                try:
                    args_obj.amount = float(parts[1])
                except ValueError:
                    print("❌ Количество должно быть числом")
                    return

        args_obj.func = self.cli.sell
        self.cli.sell(args_obj)

    def do_rate(self, arg):
        """get-rate - получить курс валюты"""
        if not arg:
            # Интерактивный запрос курса
            print("\n" + "=" * 50)
            print("ПОЛУЧЕНИЕ КУРСА ВАЛЮТ".center(50))
            print("=" * 50)

            from_currency = input("\nИсходная валюта (например, USD): ").upper()
            if not from_currency:
                print("❌ Исходная валюта не может быть пустой")
                return

            to_currency = input("Целевая валюта (например, BTC): ").upper()
            if not to_currency:
                print("❌ Целевая валюта не может быть пустой")
                return

            arg = f"--from {from_currency} --to {to_currency}"
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: rate from to")
                print("Пример: rate USD BTC")
                return

        # Выполнение запроса курса
        class Args:
            pass

        args_obj = Args()

        # Парсим аргументы
        if arg.startswith("--from"):
            import shlex
            parsed = shlex.split(arg)
            for i in range(0, len(parsed), 2):
                if parsed[i] == "--from":
                    args_obj.from_currency = parsed[i + 1]
                elif parsed[i] == "--to":
                    args_obj.to_currency = parsed[i + 1]
        else:
            parts = arg.split()
            if len(parts) >= 2:
                args_obj.from_currency = parts[0]
                args_obj.to_currency = parts[1]

        args_obj.func = self.cli.get_rate
        self.cli.get_rate(args_obj)

    def do_deposit(self, arg):
        """deposit - пополнить валюту (дополнительная команда)"""
        if not arg:
            # Интерактивное пополнение
            print("\n" + "=" * 50)
            print("ПОПОЛНЕНИЕ СЧЕТА".center(50))
            print("=" * 50)

            currency = input("\nКод валюты (например, USD, BTC): ").upper()
            if not currency:
                print("❌ Код валюты не может быть пустым")
                return

            while True:
                try:
                    amount = float(input(f"Сумма пополнения {currency}: "))
                    if amount <= 0:
                        print("❌ Сумма должна быть положительной")
                        continue
                    break
                except ValueError:
                    print("❌ Введите корректное число")
        else:
            # Проверка аргументов
            parts = arg.split()
            if len(parts) != 2:
                print("Использование: deposit currency amount")
                print("Пример: deposit USD 1000")
                return

            currency = parts[0].upper()
            try:
                amount = float(parts[1])
            except ValueError:
                print("❌ Сумма должна быть числом")
                return

        # Выполнение пополнения
        if not self.cli.auth_manager.is_logged_in():
            print("❌ Сначала выполните login")
            return

        user = self.cli.auth_manager.get_current_user()
        portfolio = self.cli.portfolio_manager.get_portfolio(user.user_id)

        wallet = portfolio.get_wallet(currency)
        if not wallet:
            wallet = portfolio.add_currency(currency)
            print(f"✅ Создан новый кошелек для {currency}")

        wallet.deposit(amount)
        self.cli.portfolio_manager.save_portfolio(portfolio)

        if currency in ["BTC", "ETH"]:
            print(f"✅ Пополнено {amount:.8f} {currency}. Новый баланс: {wallet.balance:.8f} {currency}")
        else:
            print(f"✅ Пополнено {amount:.2f} {currency}. Новый баланс: {wallet.balance:.2f} {currency}")

    def do_whoami(self, arg):
        """whoami - показать текущего пользователя"""
        if self.cli.auth_manager.is_logged_in():
            user = self.cli.auth_manager.get_current_user()
            print(f"Вы вошли как: {user.username} (id: {user.user_id})")
        else:
            print("Вы не вошли в систему")

    def do_help(self, arg):
        """help - показать справку по командам"""
        print("\n" + "=" * 50)
        print("СПРАВКА ПО КОМАНДАМ VALUTATRADE HUB")
        print("=" * 50)
        print("\n📝 Регистрация и вход:")
        print("  register              - Зарегистрироваться")
        print("  login                 - Войти в систему")
        print("  logout                - Выйти из системы")
        print("  whoami                - Показать текущего пользователя")

        print("\n💰 Управление портфелем:")
        print("  portfolio [--base X]  - Показать портфель")
        print("  buy currency amount   - Купить валюту")
        print("  sell currency amount  - Продать валюту")
        print("  deposit currency amount - Пополнить валюту (дополнительно)")

        print("\n💱 Курсы валют:")
        print("  rate from to          - Получить курс валют")

        print("\n⚙️ Системные команды:")
        print("  clear                 - Очистить экран")
        print("  help                  - Показать эту справку")
        print("  exit                  - Выйти из приложения")

        print("\n💡 Примеры:")
        print("  register              (запросит данные)")
        print("  login                 (запросит данные)")
        print("  portfolio --base EUR  (портфель в евро)")
        print("  buy BTC 0.01          (купить 0.01 BTC)")
        print("  sell EUR 100          (продать 100 EUR)")
        print("  rate USD BTC          (курс USD к BTC)")
        print("  deposit USD 1000      (пополнить USD на 1000)")
        print("=" * 50)

    def do_clear(self, arg):
        """clear - очистить экран"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_exit(self, arg):
        """exit - выйти из приложения"""
        print("\nДо свидания!")
        return True

    def default(self, line):
        """Обработка неизвестных команд."""
        print(f"Неизвестная команда: {line}")
        print("Введите 'help' для списка команд")

    def emptyline(self):
        """При нажатии Enter без команды ничего не делать."""
        pass

    def _is_username_available(self, username):
        """Проверяет, доступно ли имя пользователя."""
        users_file = os.path.join("data", "users.json")

        if not os.path.exists(users_file):
            return True

        try:
            with open(users_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return True

                users = json.loads(content)

                for user in users:
                    if isinstance(user, dict) and user.get("username") == username:
                        return False

                return True

        except (json.JSONDecodeError, FileNotFoundError):
            return True


def main():
    """Точка входа CLI."""
    cli = ValutaTradeCLI()

    # Если аргументов нет, запускаем интерактивный режим
    if len(sys.argv) == 1:
        interactive = InteractiveCLI(cli)
        interactive.cmdloop()
        return 0

    # Иначе обрабатываем аргументы командной строки
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())