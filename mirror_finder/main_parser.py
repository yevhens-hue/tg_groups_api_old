# main_parser.py

import argparse
from provider_parser import ProviderParser
from database import Database
from merchants_config import MERCHANTS


def main():
    parser = argparse.ArgumentParser(description="Парсер провайдеров гемблинговых сайтов")
    parser.add_argument("--merchant", type=str, help="ID мерчанта (например, 1xbet, dafabet)")
    parser.add_argument("--url", type=str, help="URL сайта мерчанта")
    parser.add_argument("--headless", action="store_true", help="Запуск в headless режиме")
    parser.add_argument("--list-merchants", action="store_true", help="Показать список доступных мерчантов")
    parser.add_argument("--show-results", action="store_true", help="Показать результаты из БД")
    
    args = parser.parse_args()
    
    if args.list_merchants:
        print("\nДоступные мерчанты:")
        for merchant_id, config in MERCHANTS.items():
            print(f"  - {merchant_id}: {config['brand']}")
            print(f"    Домены: {', '.join(config['official_domains'])}")
        return
    
    if args.show_results:
        db = Database()
        results = db.get_all_providers(args.merchant if args.merchant else None)
        
        if not results:
            print("В БД нет записей")
            return
        
        print(f"\nНайдено записей: {len(results)}\n")
        print(f"{'Мерчант':<15} {'Домен мерчанта':<30} {'Домен провайдера':<30} {'Тип аккаунта':<15}")
        print("-" * 100)
        
        for row in results:
            print(f"{row['merchant_id']:<15} {row['merchant_domain']:<30} {row['provider_domain']:<30} {row['account_type'] or 'N/A':<15}")
            if row['screenshot_path']:
                print(f"  Скриншот: {row['screenshot_path']}")
        
        return
    
    if not args.merchant or not args.url:
        print("❌ Необходимо указать --merchant и --url")
        print("Используйте --help для справки")
        return
    
    if args.merchant not in MERCHANTS:
        print(f"❌ Мерчант {args.merchant} не найден")
        print("Используйте --list-merchants для просмотра доступных мерчантов")
        return
    
    print(f"\n🚀 Запуск парсера для мерчанта: {args.merchant}")
    print(f"📍 URL: {args.url}")
    print(f"👁️  Headless режим: {'Да' if args.headless else 'Нет'}\n")
    
    parser_instance = ProviderParser(headless=args.headless)
    results = parser_instance.parse_merchant(args.merchant, args.url, args.headless)
    
    if results:
        print(f"\n✅ Успешно обработано провайдеров: {len(results)}")
        for result in results:
            print(f"  - {result['provider_domain']}")
    else:
        print("\n⚠️  Провайдеры не найдены или не удалось их обработать")


if __name__ == "__main__":
    main()



