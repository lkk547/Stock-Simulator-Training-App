"""
手机炒股模拟器 - Kivy 完整版
修复中文显示 + 完整界面跳转
运行前请确保: pip install kivy
"""

import kivy
kivy.require('2.1.0')

# ==================== 修复中文显示 ====================
from kivy.core.text import LabelBase
# 注册一个支持中文的字体（使用系统自带字体）
try:
    # Windows
    LabelBase.register(name='ChineseFont', fn_regular='C:/Windows/Fonts/msyh.ttc')
except:
    try:
        # macOS
        LabelBase.register(name='ChineseFont', fn_regular='/System/Library/Fonts/PingFang.ttc')
    except:
        try:
            # Linux
            LabelBase.register(name='ChineseFont', fn_regular='/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf')
        except:
            # 如果都没有，使用默认字体
            pass


def apply_chinese_font(widget):
    if hasattr(widget, 'font_name'):
        widget.font_name = 'ChineseFont'
    for child in getattr(widget, 'children', []):
        apply_chinese_font(child)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line
from kivy.core.window import Window
from kivy.utils import platform
from datetime import datetime, timedelta
import random

# 设置窗口：移动端全屏，桌面使用 360x800 预览
if platform in ('android', 'ios'):
    Window.fullscreen = True
else:
    Window.size = (360, 800)
Window.clearcolor = (0.07, 0.09, 0.12, 1)


# ==================== 辅助函数 ====================
def generate_trading_dates(start_date, end_date):
    """生成模拟交易日列表（跳过周末）"""
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    if not dates:
        dates.append(start_date)
    return dates

def generate_random_kline(dates):
    """生成随机K线数据 (OHLC)"""
    data = []
    price = 100.0
    for dt in dates:
        change = random.uniform(-0.05, 0.06)
        close = round(price * (1 + change), 2)
        close = max(close, 10.0)
        open_price = round(price, 2)
        high = round(max(open_price, close) * (1 + random.uniform(0, 0.03)), 2)
        low = round(min(open_price, close) * (1 - random.uniform(0, 0.03)), 2)
        data.append({
            'date': dt,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': random.randint(8000, 50000),
            'turnover': round(random.uniform(0.6, 8.8), 2)
        })
        price = close
    return data


def calculate_macd_series(kline_data):
    """给K线数据补充一个简化版 MACD 柱状值。"""
    ema_short = None
    ema_long = None
    dea = 0.0
    for item in kline_data:
        close = item['close']
        if ema_short is None:
            ema_short = close
            ema_long = close
        else:
            ema_short = ema_short * 11 / 13 + close * 2 / 13
            ema_long = ema_long * 25 / 27 + close * 2 / 27
        dif = ema_short - ema_long
        dea = dea * 8 / 10 + dif * 2 / 10
        item['macd'] = round((dif - dea) * 2, 2)


def show_popup(title, message, size_hint=(0.8, 0.3)):
    content = Label(text=message)
    apply_chinese_font(content)
    popup = Popup(title=title, content=content, size_hint=size_hint)
    popup.open()
    return popup


def create_metric_card(title_text):
    card = BoxLayout(orientation='vertical', padding=8, spacing=6)
    # card 背景
    from kivy.graphics import Color, Rectangle
    with card.canvas.before:
        Color(0.11, 0.14, 0.18, 1)
        rect = Rectangle(pos=card.pos, size=card.size)
    def _update_rect(instance, value):
        rect.pos = instance.pos
        rect.size = instance.size
    card.bind(pos=_update_rect, size=_update_rect)

    card.add_widget(Label(text=title_text, font_size='11sp', color=(0.72, 0.78, 0.86, 1), size_hint_y=0.4))
    value_label = Label(text='--', font_size='16sp', bold=True, size_hint_y=0.6, color=(0.94,0.97,1,1))
    card.add_widget(value_label)
    return card, value_label

def adjust_to_trading_dates(start_str, end_str):
    """将用户输入的字符串日期调整为交易日"""
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except:
        return None, None
    if start > end:
        return None, None
    all_dates = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            all_dates.append(cur)
        cur += timedelta(days=1)
    if not all_dates:
        return None, None
    return all_dates[0], all_dates[-1]


# ==================== K线绘图控件 ====================
class KLineCanvas(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.kline_data = []
        self.current_index = -1
        self.bind(size=self.draw, pos=self.draw)
    
    def set_data(self, data, index):
        self.kline_data = data
        self.current_index = index
        self.draw()
    
    def draw(self, *args):
        self.canvas.clear()
        if not self.kline_data or self.current_index < 0:
            return
        
        w = self.width
        h = self.height
        if w < 20 or h < 20:
            return
        
        left = 40
        right = 20
        top = 20
        bottom = 30
        chart_w = w - left - right
        chart_h = h - top - bottom
        
        all_prices = []
        for d in self.kline_data:
            all_prices.append(d['high'])
            all_prices.append(d['low'])
        min_p = min(all_prices) * 0.98
        max_p = max(all_prices) * 1.02
        p_range = max_p - min_p
        
        with self.canvas:
            Color(0.08, 0.10, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)
            
            Color(0.2, 0.23, 0.3, 0.8)
            for i in range(5):
                y = top + (i / 4) * chart_h
                Line(points=[left, y, left + chart_w, y], width=0.8)
            
            bar_width = max(3, chart_w / len(self.kline_data) * 0.6)
            for i in range(self.current_index + 1):
                d = self.kline_data[i]
                x = left + (i / len(self.kline_data)) * chart_w
                y_open = top + chart_h * (1 - (d['open'] - min_p) / p_range)
                y_close = top + chart_h * (1 - (d['close'] - min_p) / p_range)
                y_high = top + chart_h * (1 - (d['high'] - min_p) / p_range)
                y_low = top + chart_h * (1 - (d['low'] - min_p) / p_range)
                
                if d['close'] >= d['open']:
                    Color(0.9, 0.2, 0.2, 1)
                else:
                    Color(0.2, 0.8, 0.2, 1)
                
                Line(points=[x, y_high, x, y_low], width=1.2)
                rect_h = abs(y_close - y_open)
                rect_y = min(y_open, y_close)
                Rectangle(pos=(x - bar_width/2, rect_y), size=(bar_width, rect_h))
            
class IndicatorCanvas(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.kline_data = []
        self.current_index = -1
        self.bind(size=self.draw, pos=self.draw)

    def set_data(self, data, index):
        self.kline_data = data
        self.current_index = index
        self.draw()

    def draw(self, *args):
        self.canvas.clear()
        if not self.kline_data or self.current_index < 0:
            return

        w = self.width
        h = self.height
        if w < 20 or h < 20:
            return

        left = 12
        right = 12
        top = 10
        bottom = 10
        gap = 8
        mid_h = (h - top - bottom - gap) / 2
        panel_w = w - left - right

        current_data = self.kline_data[:self.current_index + 1]
        volumes = [item.get('volume', 0) for item in current_data]
        macd_values = [item.get('macd', 0) for item in current_data]
        max_volume = max(volumes) if volumes else 1
        max_macd = max([abs(value) for value in macd_values] + [1])

        with self.canvas:
            Color(0.08, 0.10, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)

            # 成交量面板
            vol_top = h - top
            vol_bottom = top + mid_h
            Color(0.18, 0.21, 0.28, 1)
            Line(points=[left, vol_bottom, left + panel_w, vol_bottom], width=0.8)
            Line(points=[left, vol_top, left + panel_w, vol_top], width=0.8)

            vol_bar_width = max(3, panel_w / len(self.kline_data) * 0.65)
            for i in range(self.current_index + 1):
                item = self.kline_data[i]
                bar_x = left + (i / len(self.kline_data)) * panel_w
                bar_h = (item.get('volume', 0) / max_volume) * (mid_h - 10)
                if item['close'] >= item['open']:
                    Color(0.9, 0.3, 0.3, 1)
                else:
                    Color(0.3, 0.85, 0.35, 1)
                Rectangle(pos=(bar_x - vol_bar_width / 2, vol_bottom + 3), size=(vol_bar_width, bar_h))

            # MACD 面板
            macd_bottom = bottom
            macd_top = bottom + mid_h
            mid_line_y = macd_bottom + mid_h / 2
            Color(0.18, 0.21, 0.28, 1)
            Line(points=[left, macd_bottom, left + panel_w, macd_bottom], width=0.8)
            Line(points=[left, macd_top, left + panel_w, macd_top], width=0.8)
            Line(points=[left, mid_line_y, left + panel_w, mid_line_y], width=1.0)

            macd_bar_width = max(3, panel_w / len(self.kline_data) * 0.35)
            for i in range(self.current_index + 1):
                item = self.kline_data[i]
                hist = item.get('macd', 0)
                bar_x = left + (i / len(self.kline_data)) * panel_w
                bar_h = abs(hist) / max_macd * (mid_h / 2 - 6)
                if hist >= 0:
                    Color(1.0, 0.45, 0.25, 1)
                    Rectangle(pos=(bar_x - macd_bar_width / 2, mid_line_y), size=(macd_bar_width, bar_h))
                else:
                    Color(0.3, 0.75, 1.0, 1)
                    Rectangle(pos=(bar_x - macd_bar_width / 2, mid_line_y - bar_h), size=(macd_bar_width, bar_h))


# ==================== 开始页面 ====================
class StartScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=15)
        self.app = app
        
        self.add_widget(Label(text='📈 炒股模拟器', size_hint_y=0.15, font_size='24sp', bold=True))
        
        mode_box = BoxLayout(orientation='vertical', size_hint_y=0.2, spacing=5)
        mode_box.add_widget(Label(text='选择模式', size_hint_y=0.3, bold=True))
        self.mode_random = Button(text='🌟 纯随机股票模式', size_hint_y=0.35)
        self.mode_custom = Button(text='🔍 用户指定股票模式', size_hint_y=0.35)
        mode_box.add_widget(self.mode_random)
        mode_box.add_widget(self.mode_custom)
        self.add_widget(mode_box)
        
        self.code_input = TextInput(hint_text='输入股票代码 (如 600036)', size_hint_y=0.08, disabled=True)
        self.add_widget(self.code_input)
        
        date_box = BoxLayout(orientation='vertical', size_hint_y=0.25, spacing=5)
        date_box.add_widget(Label(text='日期范围', size_hint_y=0.3, bold=True))
        date_row1 = BoxLayout(size_hint_y=0.35)
        date_row1.add_widget(Label(text='起始:', size_hint_x=0.2))
        self.start_input = TextInput(text='2020-01-01', size_hint_x=0.8)
        date_row1.add_widget(self.start_input)
        date_row2 = BoxLayout(size_hint_y=0.35)
        date_row2.add_widget(Label(text='结束:', size_hint_x=0.2))
        self.end_input = TextInput(text='2025-12-25', size_hint_x=0.8)
        date_row2.add_widget(self.end_input)
        date_box.add_widget(date_row1)
        date_box.add_widget(date_row2)
        self.add_widget(date_box)
        
        tip = Label(text='提示: 非交易日将自动调整为最近交易日', size_hint_y=0.08, color=(0.7,0.7,0.7,1), font_size='12sp')
        self.add_widget(tip)
        
        self.start_btn = Button(text='🚀 开始模拟', size_hint_y=0.12, background_color=(0.2,0.6,0.9,1))
        self.add_widget(self.start_btn)
        
        self.mode_random.bind(on_press=self.set_random_mode)
        self.mode_custom.bind(on_press=self.set_custom_mode)
        self.start_btn.bind(on_press=self.start_simulation)
        
        # 默认选中随机模式
        self.set_random_mode(None)
        apply_chinese_font(self)
    
    def set_random_mode(self, instance):
        self.mode_random.background_color = (0.3,0.7,1,1)
        self.mode_custom.background_color = (0.2,0.2,0.2,1)
        self.code_input.disabled = True
        self.code_input.text = ''
        self.app.selected_mode = 'random'
    
    def set_custom_mode(self, instance):
        self.mode_custom.background_color = (0.3,0.7,1,1)
        self.mode_random.background_color = (0.2,0.2,0.2,1)
        self.code_input.disabled = False
        self.app.selected_mode = 'custom'
    
    def start_simulation(self, instance):
        start_str = self.start_input.text.strip()
        end_str = self.end_input.text.strip()
        start_date, end_date = adjust_to_trading_dates(start_str, end_str)
        if start_date is None:
            show_popup('错误', '日期无效或范围无交易日')
            return
        
        self.app.start_date = start_date
        self.app.end_date = end_date
        self.app.stock_code = self.code_input.text if self.app.selected_mode == 'custom' else None
        
        self.app.show_main_screen()


# ==================== 主界面 ====================
class MainScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.app = app
        
        # 模拟数据
        self.kline_data = []
        self.current_index = 0
        self.cash = 100000.0
        self.position = 0
        self.avg_cost = 0.0
        
        self.build_ui()
        self.generate_market_data()
        self.update_kline()
        self.update_account_info()
    
    def build_ui(self):
        self.summary_box = BoxLayout(orientation='vertical', size_hint_y=0.2, padding=[8, 8], spacing=6)

        header_row = BoxLayout(size_hint_y=0.3, spacing=8)
        self.prev_btn = Button(text='前一天', size_hint_x=0.23)
        self.date_label = Label(text='交易日: --', bold=True, font_size='15sp')
        self.next_btn = Button(text='后一天', size_hint_x=0.23)
        header_row.add_widget(self.prev_btn)
        header_row.add_widget(self.date_label)
        header_row.add_widget(self.next_btn)
        self.summary_box.add_widget(header_row)

        metrics_grid = GridLayout(cols=3, spacing=6, size_hint_y=0.7)
        card1, self.price_label = create_metric_card('当日价格')
        card2, self.change_label = create_metric_card('涨幅')
        card3, self.high_label = create_metric_card('最高')
        card4, self.low_label = create_metric_card('最低')
        card5, self.open_label = create_metric_card('开盘价')
        card6, self.turnover_label = create_metric_card('换手率')
        metrics_grid.add_widget(card1)
        metrics_grid.add_widget(card2)
        metrics_grid.add_widget(card3)
        metrics_grid.add_widget(card4)
        metrics_grid.add_widget(card5)
        metrics_grid.add_widget(card6)
        self.summary_box.add_widget(metrics_grid)
        self.add_widget(self.summary_box)

        self.kcanvas = KLineCanvas(size_hint_y=0.32)
        self.add_widget(self.kcanvas)

        indicator_box = BoxLayout(orientation='vertical', size_hint_y=0.30, padding=[8, 4], spacing=4)
        indicator_title = Label(text='成交量 / MACD', size_hint_y=0.12, bold=True, font_size='13sp')
        self.indicator_canvas = IndicatorCanvas(size_hint_y=0.88)
        indicator_box.add_widget(indicator_title)
        indicator_box.add_widget(self.indicator_canvas)
        self.add_widget(indicator_box)

        trade_box = BoxLayout(orientation='vertical', size_hint_y=0.18, padding=[8, 6], spacing=6)
        self.status_label = Label(text='点击买入或卖出进行操作', size_hint_y=0.22, font_size='12sp', color=(0.72, 0.78, 0.86, 1))
        trade_box.add_widget(self.status_label)

        btn_row = BoxLayout(size_hint_y=0.50, spacing=8)
        self.buy_btn = Button(text='买入', background_color=(0.2, 0.8, 0.2, 1))
        self.sell_btn = Button(text='卖出', background_color=(0.9, 0.2, 0.2, 1))
        self.hold_btn = Button(text='查看持仓', background_color=(0.25, 0.45, 0.85, 1))
        btn_row.add_widget(self.buy_btn)
        btn_row.add_widget(self.sell_btn)
        btn_row.add_widget(self.hold_btn)
        trade_box.add_widget(btn_row)
        self.add_widget(trade_box)

        self.prev_btn.bind(on_press=self.prev_day)
        self.next_btn.bind(on_press=self.next_day)
        self.buy_btn.bind(on_press=self.buy)
        self.sell_btn.bind(on_press=self.sell)
        self.hold_btn.bind(on_press=self.show_holdings)
        apply_chinese_font(self)
    
    def generate_market_data(self):
        dates = generate_trading_dates(self.app.start_date, self.app.end_date)
        self.kline_data = generate_random_kline(dates)
        calculate_macd_series(self.kline_data)
        self.current_index = 0
    
    def update_kline(self):
        if not self.kline_data:
            return
        self.kcanvas.set_data(self.kline_data, self.current_index)
        self.indicator_canvas.set_data(self.kline_data, self.current_index)
        cur = self.kline_data[self.current_index]
        prev_close = self.kline_data[self.current_index - 1]['close'] if self.current_index > 0 else cur['open']
        change_pct = ((cur['close'] - prev_close) / prev_close * 100) if prev_close else 0
        self.date_label.text = f'交易日: {cur["date"].strftime("%Y-%m-%d")}'
        self.price_label.text = f'{cur["close"]:.2f}'
        self.change_label.text = f'{change_pct:+.2f}%'
        self.high_label.text = f'{cur["high"]:.2f}'
        self.low_label.text = f'{cur["low"]:.2f}'
        self.open_label.text = f'{cur["open"]:.2f}'
        self.turnover_label.text = f'{cur["turnover"]:.2f}%'
        self.status_label.text = f'当前价格 {cur["close"]:.2f}，涨幅 {change_pct:+.2f}%'
    
    def update_account_info(self):
        if not self.kline_data:
            return
        cur_price = self.kline_data[self.current_index]['close']
        market_value = self.position * cur_price
        total = self.cash + market_value
        profit = market_value - (self.position * self.avg_cost) if self.position > 0 else 0
        self.status_label.text = (
            f'资金 {self.cash:,.2f} | 持仓 {self.position}股 | '
            f'总资产 {total:,.2f} | 浮盈亏 {profit:+,.2f}'
        )
    
    def add_log(self, action, shares, price, amount):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_label.text = f'[{timestamp}] {action} {shares}股 @ {price:.2f}，金额 {amount:,.2f}'

    def max_buy_shares(self):
        if not self.kline_data:
            return 0
        current_price = self.kline_data[self.current_index]['close']
        if current_price <= 0:
            return 0
        return int(self.cash // current_price)

    def open_trade_popup(self, action):
        if not self.kline_data:
            return

        current_price = self.kline_data[self.current_index]['close']
        if action == 'buy':
            max_shares = self.max_buy_shares()
            title = '买入'
            subtitle = f'默认按当日收盘价 {current_price:.2f} 计算，最多可买 {max_shares} 股'
            confirm_text = '确认买入'
        else:
            max_shares = self.position
            title = '卖出'
            subtitle = f'默认按当日收盘价 {current_price:.2f} 计算，最多可卖 {max_shares} 股'
            confirm_text = '确认卖出'

        if max_shares <= 0:
            if action == 'buy':
                show_popup('提示', '当前资金不足，无法买入')
            else:
                show_popup('提示', '当前没有持仓，无法卖出')
            return

        popup_root = BoxLayout(orientation='vertical', padding=12, spacing=10)
        info_label = Label(text=subtitle, size_hint_y=0.22, font_size='12sp', color=(0.78, 0.84, 0.92, 1))
        share_input = TextInput(text=str(max(1, max_shares // 2)), input_filter='int', multiline=False, size_hint_y=0.18)

        ratio_row = BoxLayout(size_hint_y=0.22, spacing=6)

        def fill_ratio(ratio):
            if action == 'buy':
                share_input.text = str(max(1, int(max_shares * ratio)))
            else:
                share_input.text = str(max(1, int(max_shares * ratio)))

        for label, ratio in [('1/4', 0.25), ('1/3', 1 / 3), ('1/2', 0.5), ('全仓', 1.0)]:
            button = Button(text=label)
            button.bind(on_press=lambda instance, r=ratio: fill_ratio(r))
            ratio_row.add_widget(button)

        action_row = BoxLayout(size_hint_y=0.22, spacing=8)
        confirm_btn = Button(text=confirm_text, background_color=(0.2, 0.65, 0.3, 1))
        cancel_btn = Button(text='取消', background_color=(0.35, 0.35, 0.35, 1))
        action_row.add_widget(confirm_btn)
        action_row.add_widget(cancel_btn)

        popup_root.add_widget(Label(text=title, size_hint_y=0.16, bold=True, font_size='16sp'))
        popup_root.add_widget(info_label)
        popup_root.add_widget(share_input)
        popup_root.add_widget(ratio_row)
        popup_root.add_widget(action_row)

        popup = Popup(title=title, content=popup_root, size_hint=(0.9, 0.52))

        def confirm_trade(instance):
            try:
                shares = int(share_input.text)
            except:
                show_popup('错误', '请输入有效股数')
                return

            if shares <= 0:
                show_popup('错误', '股数必须大于 0')
                return

            if action == 'buy':
                if shares > max_shares:
                    show_popup('资金不足', f'最多可买 {max_shares} 股')
                    return
                self.execute_buy(shares)
            else:
                if shares > max_shares:
                    show_popup('错误', f'最多可卖 {max_shares} 股')
                    return
                self.execute_sell(shares)

            popup.dismiss()

        confirm_btn.bind(on_press=confirm_trade)
        cancel_btn.bind(on_press=lambda instance: popup.dismiss())
        apply_chinese_font(popup_root)
        popup.open()

    def execute_buy(self, shares):
        cur_price = self.kline_data[self.current_index]['close']
        cost = shares * cur_price
        if cost > self.cash:
            show_popup('资金不足', f'需要 {cost:,.2f}')
            return

        new_shares = self.position + shares
        new_cost = (self.position * self.avg_cost) + cost
        self.avg_cost = new_cost / new_shares if new_shares > 0 else 0
        self.position = new_shares
        self.cash -= cost

        self.add_log('买入', shares, cur_price, cost)
        self.update_kline()
        self.update_account_info()

    def execute_sell(self, shares):
        cur_price = self.kline_data[self.current_index]['close']
        amount = shares * cur_price
        self.position -= shares
        if self.position == 0:
            self.avg_cost = 0.0
        self.cash += amount

        self.add_log('卖出', shares, cur_price, amount)
        self.update_kline()
        self.update_account_info()

    def show_holdings(self, instance):
        cur_price = self.kline_data[self.current_index]['close'] if self.kline_data else 0
        market_value = self.position * cur_price
        total = self.cash + market_value
        profit = market_value - (self.position * self.avg_cost) if self.position > 0 else 0
        message = (
            f'现金: {self.cash:,.2f}\n'
            f'持仓: {self.position}股\n'
            f'均价: {self.avg_cost:.2f}\n'
            f'市值: {market_value:,.2f}\n'
            f'浮盈亏: {profit:+,.2f}\n'
            f'总资产: {total:,.2f}'
        )
        show_popup('当前持仓', message, size_hint=(0.7, 0.38))
    
    def buy(self, instance):
        self.open_trade_popup('buy')
    
    def sell(self, instance):
        self.open_trade_popup('sell')
    
    def prev_day(self, instance):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_kline()
            self.update_account_info()
        else:
            show_popup('提示', '已经是第一天', size_hint=(0.6, 0.25))
    
    def next_day(self, instance):
        if self.current_index < len(self.kline_data) - 1:
            self.current_index += 1
            self.update_kline()
            self.update_account_info()
        else:
            show_popup('提示', '已经是最后一天', size_hint=(0.6, 0.25))


# ==================== 主App ====================
class StockSimulatorApp(App):
    def build(self):
        self.selected_mode = 'random'
        self.start_date = None
        self.end_date = None
        self.stock_code = None
        
        self.root_layout = BoxLayout()
        self.start_screen = StartScreen(self)
        self.root_layout.add_widget(self.start_screen)
        return self.root_layout
    
    def show_main_screen(self):
        self.root_layout.clear_widgets()
        self.main_screen = MainScreen(self)
        self.root_layout.add_widget(self.main_screen)


if __name__ == '__main__':
    StockSimulatorApp().run()