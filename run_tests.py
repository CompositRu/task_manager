#!/usr/bin/env python3
"""
Скрипт для запуска тестов Task Manager Bot

Использование:
    python run_tests.py              # Все тесты
    python run_tests.py unit         # Только unit тесты
    python run_tests.py integration  # Только integration тесты
    python run_tests.py -v           # Verbose режим
    python run_tests.py --coverage   # С coverage отчётом
    python run_tests.py --html       # HTML отчёт coverage
"""

import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description='Run Task Manager Bot tests')

    parser.add_argument(
        'test_type',
        nargs='?',
        choices=['unit', 'integration', 'all'],
        default='all',
        help='Type of tests to run (default: all)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage report'
    )

    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate HTML coverage report'
    )

    parser.add_argument(
        '-k',
        metavar='EXPRESSION',
        help='Only run tests matching the given expression'
    )

    parser.add_argument(
        '--failed',
        action='store_true',
        help='Rerun only failed tests from last run'
    )

    args = parser.parse_args()

    # Базовая команда pytest
    cmd = ['pytest']

    # Выбор типа тестов
    if args.test_type == 'unit':
        cmd.append('tests/unit')
    elif args.test_type == 'integration':
        cmd.append('tests/integration')
    else:
        cmd.append('tests/')

    # Verbose режим
    if args.verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')

    # Coverage
    if args.coverage or args.html:
        cmd.extend([
            '--cov=src',
            '--cov-report=term-missing'
        ])

        if args.html:
            cmd.append('--cov-report=html')
            print("\n📊 HTML coverage report will be generated in htmlcov/")

    # Фильтр по выражению
    if args.k:
        cmd.extend(['-k', args.k])

    # Перезапуск failed тестов
    if args.failed:
        cmd.append('--lf')

    # Добавляем цветной вывод
    cmd.append('--color=yes')

    print(f"\n🧪 Running tests: {' '.join(cmd)}\n")
    print("=" * 70)

    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
