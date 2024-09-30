import datetime as dt
import backtrader as bt
from backtrader_bybit import BybitStore
from ConfigBybit.Config import Config  # Файл конфигурации


# видео по созданию этой стратегии
# RuTube: https://rutube.ru/video/417e306e6b5d6351d74bd9cd4d6af051/
# YouTube: https://youtube.com/live/k82vabGva7s

class UnderOver(bt.Indicator):
    lines = ('underover',)
    params = dict(data2=20)
    plotinfo = dict(plot=True)

    def __init__(self):
        self.l.underover = self.data < self.p.data2             # данные под data2 == 1


# Торговая система
class RSIStrategy(bt.Strategy):
    """
    Демонстрация live стратегии с индикаторами SMA, RSI
    """
    params = (  # Параметры торговой системы
        ('coin_target', ''),
        ('timeframe', ''),
    )

    def __init__(self):
        """Инициализация, добавление индикаторов для каждого тикера"""
        self.highest_price = 0
        self.need_drop = False
        self.order = None  # Организовываем заявки в виде справочника, конкретно для этой стратегии один тикер - одна активная заявка
        # создаем индикаторы для каждого тикера
        self.rsi = {}
        self.underover_rsi = {}
        for i in range(len(self.datas)):
            ticker = list(self.dnames.keys())[i]    # key name is ticker name
            self.rsi[ticker] = bt.indicators.RSI(self.datas[i], period=14)  # RSI indicator
            # signal 3 - когда RSI находится ниже 30
            self.underover_rsi[ticker] = UnderOver(self.rsi[ticker].lines.rsi, data2=30)

    def next(self):
        """Приход нового бара тикера"""
        for data in self.datas:  # Пробегаемся по всем запрошенным барам всех тикеров
            ticker = data._name
            status = data._state  # 0 - Live data, 1 - History data, 2 - None
            _interval = self.p.timeframe

            if status in [0, 1]:
                if status: _state = "False - History data"
                else: _state = "True - Live data"

                print('{} / {} [{}] - Open: {}, High: {}, Low: {}, Close: {}, Volume: {} - Live: {}'.format(
                    bt.num2date(data.datetime[0]),
                    data._name,
                    _interval,  # таймфрейм тикера
                    data.open[0],
                    data.high[0],
                    data.low[0],
                    data.close[0],
                    data.volume[0],
                    _state,
                ))
                print(f'\t - RSI =', self.rsi[ticker][0])

                coin_target = self.p.coin_target
                print(f"\t - Free balance: {self.broker.getcash()} {coin_target}")

                # сигналы на выход
                signal = self.underover_rsi[ticker]  # signal 3 - когда RSI находится ниже 30

                if self.need_drop:
                    self.order = None
                    self.highest_price = 0
                    self.need_drop = False

                if not self.order:  # Если позиции нет
                    if signal == 1:
                        free_money = self.broker.getcash()
                        price = data.close[0]  # по цене закрытия
                        size = (free_money / price) * 0.3  # 5% от доступных средств
                        print("-" * 50)
                        print(f"\t - buy {ticker} size = {size} at price = {price}")
                        self.order = self.buy(data=data, exectype=bt.Order.Market, size=size)
                        self.highest_price = price
                        print(f"\t - Выставлена заявка {self.order.p.tradeid} на покупку {data._name}")
                        print("-" * 50)

                else:  # Если позиция есть
                    current_price = data.close[0]
                    if current_price > self.highest_price:
                        self.highest_price = current_price

                        # Рассчитываем уровень стоп-лосса (5% от наивысшей цены)
                    trailing_stop_price = self.highest_price * 0.98
                    if current_price < trailing_stop_price:
                        # sell
                        print("-" * 50)
                        print(f"\t - Продаем по рынку {data._name}...")
                        self.sell(data=data, exectype=bt.Order.Market)
                        self.need_drop = True
                        # self.order = self.close()  # Заявка на закрытие позиции по рыночной цене
                        print("-" * 50)

    def notify_order(self, order):
        """Изменение статуса заявки"""
        order_data_name = order.data._name  # Имя тикера из заявки
        print("*"*50)
        self.log(f'Заявка номер {order.ref} {order.info["order_number"]} {order.getstatusname()} {"Покупка" if order.isbuy() else "Продажа"} {order_data_name} {order.size} @ {order.price}')
        if order.status == bt.Order.Completed:  # Если заявка полностью исполнена
            if order.isbuy():  # Заявка на покупку
                self.log(f'Покупка {order_data_name} Цена: {order.executed.price:.2f}, Объём: {order.executed.value:.2f}, Комиссия: {order.executed.comm:.2f}')
            else:  # Заявка на продажу
                self.log(f'Продажа {order_data_name} Цена: {order.executed.price:.2f}, Объём: {order.executed.value:.2f}, Комиссия: {order.executed.comm:.2f}')
                self.order = None
                self.highest_price = 0
                # Сбрасываем заявку на вход в позицию
        print("*" * 50)

    def notify_trade(self, trade):
        """Изменение статуса позиции"""
        if trade.isclosed:  # Если позиция закрыта
            self.log(f'Прибыль по закрытой позиции {trade.getdataname()} Общая={trade.pnl:.2f}, Без комиссии={trade.pnlcomm:.2f}')

    def log(self, txt, dt=None):
        """Вывод строки с датой на консоль"""
        dt = bt.num2date(self.datas[0].datetime[0]) if not dt else dt  # Заданная дата или дата текущего бара
        print(f'{dt.strftime("%d.%m.%Y %H:%M")}, {txt}')  # Выводим дату и время с заданным текстом на консоль


if __name__ == '__main__':
    cerebro = bt.Cerebro(quicknotify=True)

    cerebro.broker.setcash(100)  # Устанавливаем сколько денег
    cerebro.broker.setcommission(commission=0.0015)  # Установить комиссию- 0.15% ... разделите на 100, чтобы удалить %

    coin_target = 'USDT'  # базовый тикер, в котором будут осуществляться расчеты
    symbol = 'CTT' + coin_target  # тикер, по которому будем получать данные в формате <КодТикераБазовыйТикер>
    # symbol2 = 'ETH' + coin_target  # тикер, по которому будем получать данные в формате <КодТикераБазовыйТикер>

    accountType = Config.BYBIT_ACCOUNT_TYPE
    store = BybitStore(
        api_key=Config.BYBIT_API_KEY,
        api_secret=Config.BYBIT_API_SECRET,
        coin_target=coin_target,
        testnet=False,
        accountType=accountType,
    )  # Хранилище Bybit

    # # live подключение к Bybit - для Offline закомментировать эти две строки
    # broker = store.getbroker()
    # cerebro.setbroker(broker)

    # -----------------------------------------------------------
    # Внимание! - Теперь это Offline для тестирования стратегий #
    # -----------------------------------------------------------

    # # Исторические 1-минутные бары за 10 часов + новые live бары / таймфрейм M1
    # timeframe = "M1"
    # from_date = dt.datetime.now() - dt.timedelta(minutes=60*10)
    # data = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=symbol, start_date=from_date, LiveBars=False)  # поставьте здесь True - если нужно получать live бары
    # # data2 = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=symbol2, start_date=from_date, LiveBars=False)  # поставьте здесь True - если нужно получать live бары

    timeframe = "M1"
    from_date = dt.datetime.now() - dt.timedelta(minutes=5000)
    data = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=symbol, start_date=from_date, LiveBars=False)  # поставьте здесь True - если нужно получать live бары
    # data = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=symbol, start_date=from_date, LiveBars=True)  # поставьте здесь True - если нужно получать live бары
    # data2 = store.getdata(timeframe=bt.TimeFrame.Days, compression=1, dataname=symbol2, start_date=from_date, LiveBars=False)  # поставьте здесь True - если нужно получать live бары

    cerebro.adddata(data)  # Добавляем данные
    # cerebro.adddata(data2)  # Добавляем данные

    cerebro.addstrategy(RSIStrategy, coin_target=coin_target, timeframe=timeframe)  # Добавляем торговую систему

    cerebro.run()  # Запуск торговой системы
    cerebro.plot()  # Рисуем график

    print()
    print("$"*77)
    print(f"Ликвидационная стоимость портфеля: {cerebro.broker.getvalue()}")  # Ликвидационная стоимость портфеля
    print(f"Остаток свободных средств: {cerebro.broker.getcash()}")  # Остаток свободных средств
    print("$" * 77)
