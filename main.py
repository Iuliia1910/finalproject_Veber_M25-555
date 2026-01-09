import sys
import os

# Добавляем текущую директорию в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from valutatrade_hub.cli.interface import main
    sys.exit(main())
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print(f"Текущая директория: {current_dir}")
    print(f"Python path: {sys.path}")
    sys.exit(1)