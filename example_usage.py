from food_price_tracker import FoodPriceTracker
from datetime import datetime

# 创建跟踪器实例
tracker = FoodPriceTracker()

# 设置价格波动提醒阈值（比如设置为15%）
tracker.set_price_threshold(0.15)

# 导入新的价格数据
excel_file = "供应商价格表.xlsx"
tracker.import_from_excel(excel_file)

# 查看最新价格
print("\n最新价格列表：")
print(tracker.get_latest_prices())

# 查看特定食材的价格历史
food_item = "大白菜"  # 替换成你想查看的食材名称
print(f"\n{food_item}的价格历史：")
print(tracker.get_price_history(food_item)) 