from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file
from food_price_tracker import FoodPriceTracker
from werkzeug.utils import secure_filename
import os
import pandas as pd
from io import BytesIO
import xlsxwriter

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 用于flash消息

# 配置上传文件的存储路径
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

tracker = FoodPriceTracker()

@app.route('/')
def index():
    try:
        # 获取最新价格数据
        latest_prices = tracker.get_latest_prices()
        
        # 获取所有可用日期
        dates = tracker.get_available_dates()
        
        return render_template('index.html', 
                             latest_prices=latest_prices,
                             dates=dates)
    except Exception as e:
        flash(f'读取数据时出错：{str(e)}')
        return render_template('index.html', 
                             latest_prices=None,
                             dates=[])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('没有选择文件')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('没有选择文件')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 导入数据
        try:
            success, message = tracker.import_from_excel(filepath)  # 获取返回的状态和消息
            if success:
                flash('数据导入成功！')
            else:
                flash(f'导入数据失败：{message}')
        except Exception as e:
            flash(f'导入数据时出错：{str(e)}')
        finally:
            # 删除上传的文件
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return redirect(url_for('index'))

@app.route('/history/<food_item>')
def price_history(food_item):
    history = tracker.get_price_history(food_item)
    if isinstance(history, str):
        flash(history)
        return redirect(url_for('index'))
    
    return render_template('history.html', 
                         food_item=food_item,
                         history=history)

@app.route('/compare')
def compare_prices():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        flash('请选择起始日期')
        return redirect(url_for('index'))
    
    comparison = tracker.get_price_comparison(start_date, end_date)
    dates = tracker.get_available_dates()
    
    return render_template('comparison.html',
                         comparison=comparison,
                         start_date=start_date,
                         end_date=end_date or dates[0],
                         dates=dates)

@app.route('/trend/<food_item>')
def price_trend(food_item):
    trend_data = tracker.get_item_price_trend(food_item)
    if trend_data is None:
        flash('未找到该食材的价格记录')
        return redirect(url_for('index'))
    
    return render_template('trend.html', data=trend_data)

@app.route('/clear_data', methods=['POST'])
def clear_data():
    try:
        success, message = tracker.clear_price_data()
        if success:
            flash('数据已成功清空')
        else:
            flash(f'清空数据失败：{message}')
    except Exception as e:
        flash(f'清空数据时出错：{str(e)}')
    return redirect(url_for('index'))

@app.route('/order', methods=['GET', 'POST'])
def order_calculator():
    # 获取最新价格数据
    items = tracker.get_latest_prices()
    if items is None:
        flash('没有可用的价格数据')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        total = 0
        order_items = []
        
        for key, value in request.form.items():
            if key.startswith('quantity_'):
                food_name = key.replace('quantity_', '')
                try:
                    quantity = float(value)
                    # 检查是否是自定义价格
                    custom_price_key = f'custom_price_{food_name}'
                    if custom_price_key in request.form:
                        price = float(request.form[custom_price_key])
                        # 从表单中获取自定义单位
                        custom_unit_key = f'custom_unit_{food_name}'
                        unit = request.form.get(custom_unit_key, '未知')
                    else:
                        price_series = items.loc[items['品种'] == food_name, '康瑞达价']
                        if price_series.empty:
                            flash(f'未找到商品 {food_name} 的价格信息')
                            continue
                        price = float(price_series.iloc[0])
                        unit = items.loc[items['品种'] == food_name, '单位'].iloc[0]
                    
                    subtotal = quantity * price
                    total += subtotal
                    
                    order_items.append({
                        '品种': food_name,
                        '数量': quantity,
                        '单位': unit,
                        '单价': price,
                        '小计': subtotal
                    })
                except (ValueError, TypeError) as e:
                    flash(f'计算错误：{food_name} 的数量或价格格式不正确')
                    return redirect(url_for('order_calculator'))
        
        # 保存订单信息到 session
        session['last_order'] = order_items
        
        # 渲染结果页面，显示订单细和总价
        return render_template('order.html', 
                             items=items, 
                             total=total, 
                             order_items=order_items,
                             last_order=session.get('last_order'))
    
    # GET 请求时渲染订单页面
    return render_template('order.html', 
                         items=items,
                         last_order=session.get('last_order'),
                         order_items=[])  # 添加空的 order_items 列表

@app.route('/export_order')
def export_order():
    # 从 session 获取订单数据
    order_items = session.get('last_order', [])
    # 获取价格日期
    latest_prices = tracker.get_latest_prices()
    price_date = latest_prices.iloc[0]['日期'] if not latest_prices.empty else '未知'
    
    if not order_items:
        flash('没有可导出的订单数据')
        return redirect(url_for('order_calculator'))
    
    # 创建一个内存中的 Excel 文件
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('订单明细')
    
    # 添加日期信息
    date_format = workbook.add_format({'bold': True, 'align': 'left'})
    worksheet.write(0, 0, f'价格日期：{price_date}', date_format)
    worksheet.write(1, 0, '')  # 空行
    
    # 添加标题样式
    header_format = workbook.add_format({
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#D9EAD3'
    })
    
    # 写入表头
    headers = ['品种', '数量', '单位', '单价', '小计']
    for col, header in enumerate(headers):
        worksheet.write(2, col, header, header_format)
    
    # 写入数据
    for row, item in enumerate(order_items, start=1):
        worksheet.write(row + 2, 0, item['品种'])
        worksheet.write(row + 2, 1, item['数量'])
        worksheet.write(row + 2, 2, item['单位'])
        worksheet.write(row + 2, 3, item['单价'])
        worksheet.write(row + 2, 4, item['小计'])
    
    # 计算总计
    total = sum(item['小计'] for item in order_items)
    total_row = len(order_items) + 1
    
    # 添加总计行
    bold_format = workbook.add_format({'bold': True})
    worksheet.write(total_row, 3, '总计：', bold_format)
    worksheet.write(total_row, 4, total, bold_format)
    
    # 设置列宽
    worksheet.set_column('A:A', 20)  # 品种列宽
    worksheet.set_column('B:B', 10)  # 数量列宽
    worksheet.set_column('C:C', 8)   # 单位列宽
    worksheet.set_column('D:E', 12)  # 单价和小计列宽
    
    # 设置数字格式
    number_format = workbook.add_format({'num_format': '#,##0.00'})
    worksheet.set_column('B:B', 10, number_format)  # 数量列使用数字格式
    worksheet.set_column('D:E', 12, number_format)  # 单价和小计列使用数字格式
    
    workbook.close()
    
    # 将指针移到文件开头
    output.seek(0)
    
    # 生成下载文件名（使用当前时间）
    from datetime import datetime
    filename = f"订单明细_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/presets', methods=['GET', 'POST'])
def manage_presets():
    """管理常用套餐/组合"""
    if request.method == 'POST':
        name = request.form.get('name')
        items = request.form.getlist('items[]')
        quantities = request.form.getlist('quantities[]')
        # 保存套餐信息到数据库

@app.route('/inventory')
def inventory():
    """库存管理"""
    # 显示当前库存
    # 设置库存预警
    # 自动生成采购建议

@app.route('/cost_analysis')
def cost_analysis():
    """成本分析"""
    # 计算平均采购成本
    # 显示价格趋势图
    # 提供成本优化建议

@app.route('/suppliers')
def manage_suppliers():
    """供应商管理"""
    # 记录多个供应商的价格
    # 供应商评价和备注
    # 联系方式管理

@app.route('/order_history')
def order_history():
    """订单历史"""
    # 查看历史订单
    # 分析采购规律
    # 导出报表

def check_price_alerts():
    """检查价格波动"""
    # 设置价格波动阈值
    # 发送通知（短信/邮件）

def suggest_purchase_cycle():
    """采购建议"""
    # 分析历史数据
    # 建议最佳采购时间和数量

@app.route('/reports')
def generate_reports():
    """生成报表"""
    # 月度采购报表
    # 成本分析报表
    # 价格趋势报表

def analyze_data():
    """数据分析"""
    # 季节性价格变化
    # 采购量与价格关系
    # 支出预测

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 