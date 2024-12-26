import pandas as pd
from datetime import datetime
import os

class FoodPriceTracker:
    def __init__(self):
        self.filename = 'food_prices.csv'
        self.price_threshold = 0.1  # 价格波动阈值，默认10%
        
    def import_from_excel(self, excel_path, date=None):
        """从Excel文件导入价格数据"""
        try:
            # 读取Excel文件
            df = pd.read_excel(excel_path)
            print("读取到的数据：", df.head())
            
            # 确保必要的列存在
            required_columns = ['品种', '单位', '菜篮子价', '康瑞达价', '日期']
            if not all(col in df.columns for col in required_columns):
                return False, f"Excel文件必须包含这些列：{', '.join(required_columns)}"
            
            # 确保日期格式正确
            try:
                df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
            except Exception as e:
                return False, f"日期格式转换错误：{str(e)}"
            
            # 添加版本时间戳
            df['上传时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 如果存在历史数据，则合并
            try:
                history_df = pd.read_csv(self.filename, encoding='utf-8')
                final_df = pd.concat([history_df, df], ignore_index=True)
                # 按日期和上传时间排序，而不是删除重复记录
                final_df = final_df.sort_values(['日期', '上传时间'], ascending=[False, False])
            except (FileNotFoundError, pd.errors.EmptyDataError):
                final_df = df
            
            # 保存数据
            final_df.to_csv(self.filename, index=False, encoding='utf-8')
            print("保存的数据行数：", len(final_df))
            
            return True, "数据导入成功"
            
        except Exception as e:
            return False, f"导入数据时发生错误: {str(e)}"

    def _check_price_changes(self, new_data):
        """检查价格波动并返回波动信息"""
        price_alerts = []
        try:
            history_df = pd.read_csv(self.filename)
            if len(history_df) <= 1:  # 如果只有一条记录，无法比较
                return price_alerts
            
            # 获取上一次的价格记录
            last_date = history_df[history_df['日期'] != new_data['日期'].iloc[0]]['日期'].max()
            last_prices = history_df[history_df['日期'] == last_date]
            
            # 检查每个品种的价格变化
            for _, new_row in new_data.iterrows():
                old_price_row = last_prices[last_prices['品种'] == new_row['品种']]
                
                if not old_price_row.empty:
                    # 检查菜篮子价格变化
                    old_price = old_price_row['菜篮子价'].iloc[0]
                    new_price = new_row['菜篮子价']
                    change_pct = (new_price - old_price) / old_price
                    
                    if abs(change_pct) >= self.price_threshold:
                        price_alerts.append({
                            '品种': new_row['品种'],
                            '供应商': '菜篮子',
                            '原价': old_price,
                            '新价': new_price,
                            '变化比例': f"{change_pct:.1%}",
                            '变化日期': f"从 {last_date} 到 {new_row['日期']}"
                        })
                    
                    # 检查康瑞达价格变化
                    old_price = old_price_row['康瑞达价'].iloc[0]
                    new_price = new_row['康瑞达价']
                    change_pct = (new_price - old_price) / old_price
                    
                    if abs(change_pct) >= self.price_threshold:
                        price_alerts.append({
                            '品种': new_row['品种'],
                            '供应商': '康瑞达',
                            '原价': old_price,
                            '新价': new_price,
                            '变化比例': f"{change_pct:.1%}",
                            '变化日期': f"从 {last_date} 到 {new_row['日期']}"
                        })
            
        except FileNotFoundError:
            pass  # 如果是第一次导入数据，就不需要检查价格变化
        
        return price_alerts

    def get_price_history(self, food_item):
        """获取特定食材的价格历史"""
        try:
            df = pd.read_csv(self.filename, encoding='utf-8')
            if food_item not in df['品种'].values:
                return None
            
            # 获取所有记录并按日期和上传时间排序
            result = df[df['品种'] == food_item].sort_values(['日期', '上传时间'], ascending=[False, False])
            return result
            
        except FileNotFoundError:
            return None

    def get_latest_prices(self):
        """获取最新一期的所有价格"""
        try:
            df = pd.read_csv(self.filename, encoding='utf-8')
            if df.empty:
                return None
            
            # 获取最新日期（从Excel表中的日期）
            latest_date = df['日期'].max()
            latest_records = df[df['日期'] == latest_date]
            
            # 如果同一天有多条记录，保留所有记录
            return latest_records.sort_values('品种')
            
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return None

    def get_price_comparison(self, start_date, end_date=None):
        """获取两个日期之间的价格比较"""
        try:
            df = pd.read_csv(self.filename, encoding='utf-8')
            
            # 转换价格为数值类型
            def clean_price(price):
                try:
                    if isinstance(price, str):
                        price = ''.join(c for c in price if c.isdigit() or c == '.')
                        parts = price.split('.')
                        if len(parts) > 2:
                            price = parts[0] + '.' + ''.join(parts[1:])
                    return float(price)
                except (ValueError, TypeError):
                    return 0.0

            df['菜篮子价'] = df['菜篮子价'].apply(clean_price)
            df['康瑞达价'] = df['康瑞达价'].apply(clean_price)
            
            if end_date is None:
                end_date = df['日期'].max()
            
            start_prices = df[df['日期'] == start_date]
            end_prices = df[df['日期'] == end_date]
            
            comparison = []
            for _, start_row in start_prices.iterrows():
                end_row = end_prices[end_prices['品种'] == start_row['品种']]
                if not end_row.empty:
                    end_row = end_row.iloc[0]
                    comparison.append({
                        '品种': start_row['品种'],
                        '单位': start_row['单位'],
                        '菜篮子价_起': start_row['菜篮子价'],
                        '菜篮子价_终': end_row['菜篮子价'],
                        '菜篮子价_变化': f"{((end_row['菜篮子价'] - start_row['菜篮子价']) / start_row['菜篮子价']):.1%}" if start_row['菜篮子价'] != 0 else "0%",
                        '康瑞达价_起': start_row['康瑞达价'],
                        '康瑞达价_终': end_row['康瑞达价'],
                        '康瑞达价_变化': f"{((end_row['康瑞达价'] - start_row['康瑞达价']) / start_row['康瑞达价']):.1%}" if start_row['康瑞达价'] != 0 else "0%"
                    })
            
            return comparison
            
        except Exception as e:
            print(f"Error in price comparison: {str(e)}")
            return None

    def get_available_dates(self):
        """获取所有可用的日期列表"""
        try:
            df = pd.read_csv(self.filename, encoding='utf-8')
            if df.empty:  # 检查是否为空
                return []
            return sorted(df['日期'].unique(), reverse=True)
        except (FileNotFoundError, pd.errors.EmptyDataError):  # 处理文件不存在或为空的情况
            return []

    def get_item_price_trend(self, food_item):
        """获取特定食材的价格趋势数据"""
        try:
            print(f"Reading CSV file: {self.filename}")
            df = pd.read_csv(self.filename, encoding='utf-8')
            print(f"CSV columns: {df.columns.tolist()}")
            
            if '品种' not in df.columns:
                print("Error: '品种' column not found")
                return None
            
            if food_item not in df['品种'].values:
                print(f"Error: '{food_item}' not found in data")
                return None
            
            # 获取该食材的所有记录并按日期排序
            item_df = df[df['品种'] == food_item].sort_values('日期', ascending=False)
            
            # 转换价格为数值类型
            def clean_price(price):
                try:
                    if isinstance(price, str):
                        # 移除所有非数字和小数点的字符
                        price = ''.join(c for c in price if c.isdigit() or c == '.')
                        # 如果有多个小数点，只保留第一个
                        parts = price.split('.')
                        if len(parts) > 2:
                            price = parts[0] + '.' + ''.join(parts[1:])
                    return float(price)
                except (ValueError, TypeError):
                    print(f"Warning: Invalid price value: {price}")
                    return 0.0

            item_df['菜篮子价'] = item_df['菜篮子价'].apply(clean_price)
            item_df['康瑞达价'] = item_df['康瑞达价'].apply(clean_price)
            
            # 计算价格变化
            result = {
                '品种': food_item,
                '单位': item_df['单位'].iloc[0],
                '历史记录': []
            }
            
            # 添加每个日期的价格记录
            for _, row in item_df.iterrows():
                record = {
                    '日期': row['日���'],
                    '菜篮子价': row['菜篮子价'],
                    '康瑞达价': row['康瑞达价']
                }
                result['历史记录'].append(record)
            
            # 计算价格统计信息
            result.update({
                '最高菜篮子价': item_df['菜篮子价'].max(),
                '最低菜篮子价': item_df['菜篮子价'].min(),
                '平均菜篮子价': round(item_df['菜篮子价'].mean(), 2),
                '最高康瑞达价': item_df['康瑞达价'].max(),
                '最低康瑞达价': item_df['康瑞达价'].min(),
                '平均康瑞达价': round(item_df['康瑞达价'].mean(), 2)
            })
            
            return result
            
        except Exception as e:
            print(f"Error in get_item_price_trend: {str(e)}")
            return None

    def clear_price_data(self):
        """清空价格数据"""
        try:
            # 创建一个空的 DataFrame，只包含列名
            columns = ['品种', '单位', '菜篮子价', '康瑞达价', '日期']
            df = pd.DataFrame(columns=columns)
            # 保存为 CSV，确保使用 UTF-8 编码
            df.to_csv(self.filename, index=False, encoding='utf-8')
            return True, "数据已清空"
        except Exception as e:
            return False, f"清空数据时出错：{str(e)}"

    def save_order(self, order_items, total_price):
        """保存订单到历史记录"""
        try:
            order_file = 'order_history.csv'
            order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 准备订单数据
            order_data = []
            for item in order_items:
                order_data.append({
                    '订单日期': order_date,
                    '品种': item['品种'],
                    '单位': item['单位'],
                    '数量': item['数量'],
                    '单价': item['单价'],
                    '小计': item['小计']
                })
            
            # 创建或追加到CSV文件
            df = pd.DataFrame(order_data)
            if os.path.exists(order_file):
                df.to_csv(order_file, mode='a', header=False, index=False, encoding='utf-8')
            else:
                df.to_csv(order_file, index=False, encoding='utf-8')
            
            return True, "订单已保存"
        except Exception as e:
            return False, f"保存订单失败：{str(e)}"

    def get_last_order(self):
        """获取最近一次订单"""
        try:
            order_file = 'order_history.csv'
            if not os.path.exists(order_file):
                return None
            
            df = pd.read_csv(order_file, encoding='utf-8')
            if df.empty:
                return None
            
            # 获取最新订单日期
            latest_date = df['订单日期'].max()
            latest_order = df[df['订单日期'] == latest_date]
            
            # 转换为字典格式
            order_items = []
            for _, row in latest_order.iterrows():
                order_items.append({
                    '品种': row['品种'],
                    '数量': row['数量']
                })
            
            return order_items
        except Exception as e:
            print(f"获取最近订单失败：{str(e)}")
            return None 