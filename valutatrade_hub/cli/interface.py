#!/usr/bin/env python3

import argparse
import sys
import cmd


from valutatrade_hub.core.usecases import AuthManager, PortfolioManager, RateManager
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError
)

class ValutaTradeCLI:

    def __init__(self):
        self.auth_manager = AuthManager()
        self.portfolio_manager = PortfolioManager()
        self.rate_manager = RateManager()

    def register(self, args):
        try:
            if not args.username or not args.username.strip():
                print("Ошибка: имя пользователя не может быть пустым")
                return 1

            if len(args.password) < 4:
                print("Ошибка: пароль должен быть не короче 4 символов")
                return 1

            user = self.auth_manager.register(args.username, args.password)
            print(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}).")
            print(f"Войдите: login --username {user.username} --password ****")
            return 0

        except ValueError as e:
            print(f"Ошибка: {e}")
            return 1

    def login(self, args):
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
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 1

        from valutatrade_hub.parser_service.config import ParserConfig
        from valutatrade_hub.parser_service.updater import RatesUpdater

        config = ParserConfig()
        updater = RatesUpdater(config)
        # Загрузим актуальные курсы из кэша
        try:
            updater.load_rates()
        except Exception as e:
            print(f"Предупреждение: не удалось получить актуальные курсы ({e})")
            print("Будут использованы старые курсы из RateManager")

        base_currency = (args.base or "USD").upper()

        user = self.auth_manager.get_current_user()
        portfolio = self.portfolio_manager.get_portfolio(user.user_id)
        wallets = portfolio.wallets
        print(f"\nПортфель пользователя '{user.username}' (база: {base_currency}):")

        if not wallets:
            print("  Ваш портфель пуст")
            return 0

        total_value = 0

        for currency, wallet in wallets.items():
            balance = wallet.balance

            if currency == base_currency:
                value = balance
                rate_info = "1.0000"
            else:
                try:
                    rate = self.rate_manager.get_rate(currency, base_currency)
                    if rate is None:
                        raise ValueError(f"Курс для {currency}→{base_currency} не найден")
                    value = balance * rate
                    rate_info = f"{rate:.4f}"
                except Exception as e:
                    print(f" Предупреждение: не удалось получить курс для {currency}→{base_currency} ({e})")
                    print(f"  - {currency}: {balance:.4f} (курс недоступен)")
                    continue

            total_value += value

            if currency in ["BTC", "ETH"]:
                print(f"  - {currency}: {balance:.4f}  → {value:.2f} {base_currency} (курс: {rate_info})")
            else:
                print(f"  - {currency}: {balance:.2f}  → {value:.2f} {base_currency} (курс: {rate_info})")

        print(f"  ИТОГО: {total_value:,.2f} {base_currency}")
        return 0

    def buy(self, args):
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 0

        currency = args.currency.upper()
        amount = args.amount

        if amount <= 0:
            print("Ошибка: 'amount' должен быть положительным числом")
            return 0

        if not currency:
            print("Ошибка: код валюты не может быть пустым")
            return 0

        try:
            user = self.auth_manager.get_current_user()
            # Покупаем валюту
            result = self.portfolio_manager.buy_currency(
                user.user_id,
                currency,
                amount
            )

            # Берём актуальный курс для вывода
            try:
                rate = self.rate_manager.get_rate(currency, "RUB")  # или ваша база
            except Exception:
                rate = 0

            print("ПОКУПКА УСПЕШНО ВЫПОЛНЕНА")
            print(f"Операция: Куплено {amount:.4f} {currency}")
            print(f"Курс покупки: {rate:.4f} RUB/{currency}")
            print(f"Общая стоимость: {amount * rate:,.2f} RUB")
            print("\nИзменения баланса:")
            print(f"  - {currency}: +{amount:.4f} → {result['new_balance']:.4f}")

            # Показать остаток RUB
            portfolio = self.portfolio_manager.get_portfolio(user.user_id)
            rub_wallet = portfolio.get_wallet("RUB")
            if rub_wallet:
                print(f"  - RUB: -{amount * rate:,.2f} → {rub_wallet.balance:,.2f}")

            return 0

        except InsufficientFundsError:
            print("\nОшибка: Недостаточно средств для покупки")
            return 0
        except Exception as e:
            print(f"\nНеожиданная ошибка: {e}")
            return 0

    def sell(self, args):
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 0

        currency = args.currency.upper()
        amount = args.amount

        if amount <= 0:
            print("Ошибка: 'amount' должен быть положительным числом")
            return 0

        if not currency:
            print("Ошибка: код валюты не может быть пустым")
            return 0

        try:
            user = self.auth_manager.get_current_user()
            # Продаём валюту
            result = self.portfolio_manager.sell_currency(
                user.user_id,
                currency,
                amount
            )

            # Берём актуальный курс для вывода
            try:
                rate = self.rate_manager.get_rate(currency, "RUB")  # или ваша база
            except Exception:
                rate = 0

            print("ПРОДАЖА УСПЕШНО ВЫПОЛНЕНА")
            print(f"Операция: Продано {amount:.4f} {currency}")
            print(f"Курс продажи: {rate:.4f} RUB/{currency}")
            print("\nИзменения баланса:")
            print(f"  - {currency}: -{amount:.4f} → {result['new_balance']:.4f}")

            # Показать RUB, которые поступили
            portfolio = self.portfolio_manager.get_portfolio(user.user_id)
            rub_wallet = portfolio.get_wallet("RUB")
            if rub_wallet:
                print(f"  - RUB: +{amount * rate:,.2f} → {rub_wallet.balance:,.2f}")

            return 0

        except InsufficientFundsError:
            print("\nОшибка: Недостаточно средств для продажи")
            return 0
        except Exception as e:
            print(f"\nНеожиданная ошибка: {e}")
            return 0

    def get_rate(self, args):
        from_currency = args.from_currency.upper()
        to_currency = args.to_currency.upper()

        if not from_currency or not to_currency:
            print("Ошибка: коды валют не могут быть пустыми")
            return 1

        if from_currency == to_currency:
            print(f"Курс {from_currency}→{to_currency}: 1.000000")
            return 0

        try:
            rate = self.rate_manager.get_rate(from_currency, to_currency)

            try:
                if hasattr(self.rate_manager, 'get_rate_with_info'):
                    rate_info = self.rate_manager.get_rate_with_info(from_currency, to_currency)
                    updated_at = rate_info.get('updated_at', 'Неизвестно')
                else:
                    from datetime import datetime
                    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                from datetime import datetime
                updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print("\n💱 КУРС ВАЛЮТ")
            print(f"{from_currency} → {to_currency}")
            print(f"Курс: 1 {from_currency} = {rate:.8f} {to_currency}")

            if rate != 0:
                print(f"Обратный: 1 {to_currency} = {1 / rate:.8f} {from_currency}")

            print(f"Обновлено: {updated_at}")
            return 0

        except CurrencyNotFoundError:
            print("\nОшибка: Валюта не найдена")
            print("Проверьте правильность кодов валют:")
            print(f"  Исходная валюта: '{from_currency}'")
            print(f"  Целевая валюта: '{to_currency}'")
            print("\nПоддерживаемые валюты: USD, EUR, BTC, ETH, RUB, CNY, GBP")
            return 0
        except ApiRequestError:
            print("\nОшибка: Не удалось получить курс из-за ошибки API")
            print("Повторите попытку позже")
            return 0
        except Exception as e:
            print(f"\nОшибка: Курс {from_currency}→{to_currency} недоступен")
            print(f"Детали: {str(e)}")
            return 0

    def update_rates(self, args=None):
        print("Обновление курсов валют...")

        try:
            from valutatrade_hub.parser_service.config import ParserConfig
            from valutatrade_hub.parser_service.updater import RatesUpdater

            config = ParserConfig()
            updater = RatesUpdater(config)

            result = updater.run_update()

            if result.get("status") == "success":
                print(f"Курсы успешно обновлены: {result.get('rates_count', 0)} пар")

                if "source_counts" in result:
                    print("По источникам:")
                    for source, count in result["source_counts"].items():
                        print(f"  - {source}: {count}")

                # ФИКС: После обновления парсером, перезагружаем курсы в RateManager
                self.rate_manager._rates_cache = None  # Сбрасываем кеш
                print("Курсы обновлены в RateManager")

                return 0
            else:
                print(f"Не удалось обновить курсы: {result.get('error', 'неизвестная ошибка')}")
                return 0

        except ImportError as e:
            print(f"Сервис обновления курсов недоступен: {e}")
            return 0
        except Exception as e:
            print(f"Ошибка при обновлении курсов: {e}")
            return 0

    def run(self):
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
      project update_rates
              """
        )

        subparsers = parser.add_subparsers(
            dest="command",
            help="Доступные команды"
        )

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

        update_parser = subparsers.add_parser(
            "update_rates",
            help="Обновить курсы валют из внешних API"
        )
        update_parser.set_defaults(func=self.update_rates)

        if hasattr(self, 'deposit'):
            deposit_parser = subparsers.add_parser(
                "deposit",
                help="Пополнение счета"
            )
            deposit_parser.add_argument(
                "--currency",
                default="USD",
                help="Валюта пополнения (по умолчанию: USD)"
            )
            deposit_parser.add_argument(
                "--amount",
                type=float,
                required=True,
                help="Сумма пополнения"
            )
            deposit_parser.set_defaults(func=self.deposit)

        if hasattr(self, 'logout'):
            logout_parser = subparsers.add_parser(
                "logout",
                help="Выйти из системы"
            )
            logout_parser.set_defaults(func=self.logout)

        if hasattr(self, 'whoami'):
            whoami_parser = subparsers.add_parser(
                "whoami",
                help="Показать текущего пользователя"
            )
            whoami_parser.set_defaults(func=self.whoami)

        if len(sys.argv) == 1:
            parser.print_help()
            return 0

        args = parser.parse_args()

        if hasattr(args, 'func'):
            return args.func(args)
        else:
            parser.print_help()
            return 0

    def deposit(self, args):
        if not self.auth_manager.is_logged_in():
            print("Ошибка: сначала выполните login")
            return 0

        try:
            user = self.auth_manager.get_current_user()
            result = self.portfolio_manager.deposit_currency(
                user.user_id,
                args.currency,
                args.amount
            )

            print("\nПОПОЛНЕНИЕ ВЫПОЛНЕНО УСПЕШНО")
            print(f"Валюта: {args.currency}")
            print(f"Сумма: {args.amount:.8f if args.currency in ['BTC', 'ETH'] else args.amount:.2f}")
            print(
                f"Новый баланс: {result['new_balance']:.8f if args.currency in ['BTC', 'ETH'] else result['new_balance']:.2f} {args.currency}")


            return 0

        except Exception as e:
            error_msg = str(e)
            print(f"Ошибка при пополнении: {error_msg}")
            return 1

class InteractiveCLI(cmd.Cmd):

    intro = """
Добро пожаловать в ValutaTrade Hub!
Введите команду или 'help' для справки
Введите 'exit' для выхода
"""
    prompt = "valutatrade> "

    def __init__(self, cli):
        super().__init__()
        self.cli = cli
        self.current_user = None

    def do_register(self, arg):
        print("РЕГИСТРАЦИЯ НОВОГО ПОЛЬЗОВАТЕЛЯ".center(40))

        username = input("\nИмя пользователя: ").strip()
        if not username:
            print("Имя пользователя не может быть пустым")
            return 0

        password = input("Пароль (минимум 4 символа): ")
        if len(password) < 4:
            print("Пароль должен быть не короче 4 символов")
            return 0

        try:
            from types import SimpleNamespace
            args = SimpleNamespace(username=username, password=password)
            args.func = self.cli.register

            result = self.cli.register(args)

            if result == 0:
                print(f"\nПользователь '{username}' успешно зарегистрирован!")
                print("Теперь вы можете войти в систему: команда 'login'")
            else:
                print(f"\nНе удалось зарегистрироваться. Код ошибки: {result}")

            return result

        except Exception as e:
            error_msg = str(e).lower()
            if "username already taken" in error_msg or "usernametakenerror" in error_msg:
                print(f"\n Пользователь '{username}' уже существует!")
                print("Попробуйте другое имя пользователя или войдите под существующим.")
                print("Команды:")
                print("  login - войти под существующим пользователем")
                print("  register - попробовать зарегистрироваться с другим именем")
            else:
                print(f"\nОшибка при регистрации: {e}")

            return 0

    def do_login(self, arg):
        print("ВХОД В СИСТЕМУ".center(40))

        username = input("\nИмя пользователя: ").strip()
        if not username:
            print("Имя пользователя не может быть пустым")
            return 0

        password = input("Пароль: ")

        try:
            from types import SimpleNamespace
            args = SimpleNamespace(username=username, password=password)
            args.func = self.cli.login

            result = self.cli.login(args)

            if result == 0:
                if self.cli.auth_manager.is_logged_in():
                    user = self.cli.auth_manager.get_current_user()
                    self.current_user = user.username
                    self.prompt = f"valutatrade({self.current_user})> "
                    print(f"\nВы вошли как {user.username}!")
                    print("Добро пожаловать!")
            else:
                print(f"\nНе удалось войти. Код ошибки: {result}")

            return result

        except Exception as e:
            error_msg = str(e).lower()
            if "user not found" in error_msg or "usernotfounderror" in error_msg:
                print(f"\nПользователь '{username}' не найден!")
                print("Варианты:")
                print("  1. Проверьте правильность имени пользователя")
                print("  2. Зарегистрируйтесь: команда 'register'")
            elif "invalid password" in error_msg or "invalidpassworderror" in error_msg:
                print(f"\nНеверный пароль для пользователя '{username}'!")
                print("Попробуйте снова.")
            else:
                print(f"\nОшибка при входе: {e}")

            return 0

    def do_logout(self, arg):
        if self.cli.auth_manager.is_logged_in():
            self.cli.auth_manager.logout()
            self.current_user = None
            self.prompt = "valutatrade> "
            print("Вы вышли из системы.")
        else:
            print("Вы не вошли в систему")
        return 0

    def do_whoami(self, arg):
        if self.cli.auth_manager.is_logged_in():
            user = self.cli.auth_manager.get_current_user()
            print(f"Текущий пользователь: {user.username} (id: {user.user_id})")
        else:
            print("Вы не вошли в систему")
        return 0

    def do_portfolio(self, arg):
        from types import SimpleNamespace
        args = SimpleNamespace(base="USD", show_info=False)

        if arg:
            parts = arg.split()
            i = 0
            while i < len(parts):
                if parts[i] == "--base" and i + 1 < len(parts):
                    args.base = parts[i + 1]
                    i += 2
                elif parts[i] == "--show-info":
                    args.show_info = True
                    i += 1
                else:
                    i += 1

        args.func = self.cli.show_portfolio
        return self.cli.show_portfolio(args)

    def do_buy(self, arg):
        if not arg:
            print("Использование: buy <currency> <amount>")
            print("Пример: buy BTC 0.01")
            return 0

        parts = arg.split()
        if len(parts) != 2:
            print("Неправильный формат команды")
            print("Использование: buy <currency> <amount>")
            return 0

        try:
            currency = parts[0].upper()
            amount = float(parts[1])

            from types import SimpleNamespace
            args = SimpleNamespace(currency=currency, amount=amount)
            args.func = self.cli.buy

            return self.cli.buy(args)

        except ValueError:
            print("Количество должно быть числом")
            return 0
        except Exception as e:
            print(f"Ошибка: {e}")
            return 0

    def do_sell(self, arg):
        if not arg:
            print("Использование: sell <currency> <amount>")
            print("Пример: sell BTC 0.01")
            return 0

        parts = arg.split()
        if len(parts) != 2:
            print("Неправильный формат команды")
            print("Использование: sell <currency> <amount>")
            return 0

        try:
            currency = parts[0].upper()
            amount = float(parts[1])

            from types import SimpleNamespace
            args = SimpleNamespace(currency=currency, amount=amount)
            args.func = self.cli.sell

            return self.cli.sell(args)

        except ValueError:
            print("Количество должно быть числом")
            return 0
        except Exception as e:
            print(f"Ошибка: {e}")
            return 0

    def do_rate(self, arg):
        if not arg:
            print("Использование: rate <from_currency> <to_currency>")
            print("Пример: rate USD BTC")
            return 0

        parts = arg.split()
        if len(parts) != 2:
            print("Неправильный формат команды")
            print("Использование: rate <from_currency> <to_currency>")
            return 0

        try:
            from_currency = parts[0].upper()
            to_currency = parts[1].upper()

            from types import SimpleNamespace
            args = SimpleNamespace(from_currency=from_currency, to_currency=to_currency)
            args.func = self.cli.get_rate

            return self.cli.get_rate(args)

        except Exception as e:
            print(f"Ошибка: {e}")
            return 0

    def do_deposit(self, arg):
        if not arg:
            print("Использование: deposit <currency> <amount>")
            print("Пример: deposit USD 1000")
            return 0

        parts = arg.split()
        if len(parts) != 2:
            print("Неправильный формат команды")
            print("Использование: deposit <currency> <amount>")
            return 0

        try:
            currency = parts[0].upper()
            amount = float(parts[1])

            from types import SimpleNamespace
            args = SimpleNamespace(currency=currency, amount=amount)
            args.func = self.cli.deposit

            return self.cli.deposit(args)

        except ValueError:
            print("Сумма должна быть числом")
            return 0
        except Exception as e:
            print(f"Ошибка: {e}")
            return 0

    def do_clear(self, arg):
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_update_rates(self, arg):

        try:
            from types import SimpleNamespace
            args = SimpleNamespace()

            if hasattr(self.cli, 'update_rates'):
                args.func = self.cli.update_rates
                result = self.cli.update_rates(args)

                if result == 0:
                    print("Курсы успешно обновлены!")
                else:
                    print("Не удалось обновить курсы")
                return result
            else:
                print("Команда update_rates не поддерживается")
                print("Проверьте наличие метода update_rates в ValutaTradeCLI")
                return 0

        except Exception as e:
            print(f"Ошибка: {e}")
            return 0

    def do_help(self, arg):
        print("СПРАВКА ПО КОМАНДАМ VALUTATRADE HUB")
        print("\n Регистрация и вход:")
        print("  register              - Зарегистрироваться")
        print("  login                 - Войти в систему")
        print("  logout                - Выйти из системы")
        print("  whoami                - Показать текущего пользователя")

        print("\n Управление портфелем:")
        print("  portfolio             - Показать портфель")
        print("  buy <currency> <amount>   - Купить валюту")
        print("  sell <currency> <amount>  - Продать валюту")
        print("  deposit <currency> <amount> - Пополнить валюту")

        print("\n Курсы валют:")
        print("  rate <from> <to>      - Получить курс валют")

        print("\n Системные команды:")
        print("  clear                 - Очистить экран")
        print("  help                  - Показать эту справку")
        print("  exit                  - Выйти из приложения")

        print("  deposit USD 1000      (пополнить USD на 1000)")
        print("\n Обновление данных:")
        print("  update_rates         - Обновить курсы валют из API")

    def do_exit(self, arg):
        print("\n До свидания!")
        return True


    def default(self, line):
        print(f" Неизвестная команда: {line}")
        print("   Введите 'help' для списка команд")

    def emptyline(self):
        pass

def main():
    cli = ValutaTradeCLI()

    if len(sys.argv) == 1:
        try:
            interactive = InteractiveCLI(cli)
            interactive.cmdloop()
            return 0
        except KeyboardInterrupt:
            print("\n До свидания!")
            return 0
        except Exception as e:
            print(f"\n Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
            return 0
    else:
        return cli.run()


if __name__ == "__main__":
    sys.exit(main())