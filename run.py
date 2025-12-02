#!/usr/bin/env python
"""
Backpack Exchange 做市交易程序統一入口
支持命令行模式
"""
import argparse
import sys
import os
import time
import signal
from typing import Optional
from config import ENABLE_DATABASE, DB_PATH
from core.logger import setup_logger
from core.exceptions import InsufficientFundsError

# 創建記錄器
logger = setup_logger("main")


class GracefulExit(SystemExit):
    """用於標示需要優雅退出策略的例外"""
    pass


class StrategySignalHandler:
    """在策略運行期間接管 SIGTERM/SIGINT，確保優雅退出"""

    def __init__(self, strategy):
        self.strategy = strategy
        self._original_handlers = {}

    def __enter__(self):
        def _handle(signum, frame):
            logger.info(f"收到系統信號，通知策略停止 (signal={signum})")
            if self.strategy and hasattr(self.strategy, "stop"):
                try:
                    self.strategy.stop()
                except Exception as exc:
                    logger.error(f"通知策略停止時發生錯誤: {exc}")
            raise GracefulExit()

        self._handler = _handle
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._original_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _handle)
        return self

    def __exit__(self, exc_type, exc, tb):
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        return False


def run_strategy_with_signals(strategy, duration_seconds, interval_seconds):
    """注入信號處理後運行策略"""
    if strategy is None:
        raise ValueError("strategy 實例不可為 None")

    try:
        with StrategySignalHandler(strategy):
            strategy.run(duration_seconds=duration_seconds, interval_seconds=interval_seconds)
    except GracefulExit:
        logger.info("策略收到停止信號，結束運行")

def parse_arguments():
    """解析命令行參數"""
    parser = argparse.ArgumentParser(description='Backpack Exchange 做市交易程序')
    
    # 模式選擇
    parser.add_argument('--cli', action='store_true', help='啟動命令行界面')
    parser.add_argument('--web', action='store_true', help='啟動Web界面')
    
    # 基本參數
    parser.add_argument('--exchange', type=str, choices=['backpack', 'aster', 'paradex', 'lighter', 'apex'], default='backpack', help='交易所選擇 (backpack、aster、paradex、lighter 或 apex)')
    parser.add_argument('--api-key', type=str, help='API Key (可選，默認使用環境變數或配置文件)')
    parser.add_argument('--secret-key', type=str, help='Secret Key (可選，默認使用環境變數或配置文件)')
    
    # 做市參數
    parser.add_argument('--symbol', type=str, help='交易對 (例如: SOL_USDC)')
    parser.add_argument('--spread', type=float, help='價差百分比 (例如: 0.5)')
    parser.add_argument('--quantity', type=float, help='訂單數量 (可選)')
    parser.add_argument('--max-orders', type=int, default=3, help='每側最大訂單數量 (默認: 3)')
    parser.add_argument('--duration', type=int, default=3600, help='運行時間（秒）(默認: 3600)')
    parser.add_argument('--interval', type=int, default=60, help='更新間隔（秒）(默認: 60)')
    parser.add_argument('--market-type', choices=['spot', 'perp'], default='spot', help='市場類型 (spot 或 perp)')
    parser.add_argument('--target-position', type=float, default=1.0, help='永續合約目標持倉量 (絕對值, 例如: 1.0)')
    parser.add_argument('--max-position', type=float, default=1.0, help='永續合約最大允許倉位(絕對值)')
    parser.add_argument('--position-threshold', type=float, default=0.1, help='永續倉位調整觸發值')
    parser.add_argument('--inventory-skew', type=float, default=0.0, help='永續倉位偏移調整係數 (0-1)')
    parser.add_argument('--stop-loss', type=float, help='永續倉位止損觸發值 (以報價資產計價)')
    parser.add_argument('--take-profit', type=float, help='永續倉位止盈觸發值 (以報價資產計價)')
    parser.add_argument('--strategy', choices=['standard', 'maker_hedge', 'grid', 'perp_grid'], default='standard', help='策略選擇 (standard, maker_hedge, grid 或 perp_grid)')

    # 網格策略參數
    parser.add_argument('--grid-upper', type=float, help='網格上限價格')
    parser.add_argument('--grid-lower', type=float, help='網格下限價格')
    parser.add_argument('--grid-num', type=int, default=10, help='網格數量 (默認: 10)')
    parser.add_argument('--auto-price', action='store_true', help='自動設置網格價格範圍')
    parser.add_argument('--price-range', type=float, default=5.0, help='自動模式下的價格範圍百分比 (默認: 5.0)')
    parser.add_argument('--grid-mode', choices=['arithmetic', 'geometric'], default='arithmetic', help='網格模式 (arithmetic 或 geometric)')
    parser.add_argument('--grid-type', choices=['neutral', 'long', 'short'], default='neutral', help='永續網格類型 (neutral, long 或 short)')
    
    # 網格邊界處理參數
    parser.add_argument('--boundary-action', choices=['emergency_close', 'adjust_range', 'stop_only'], default='emergency_close', help='網格邊界觸發時的處理方式 (emergency_close, adjust_range, stop_only)')
    parser.add_argument('--boundary-tolerance', type=float, default=0.001, help='網格邊界觸發的容差 (默認: 0.001 = 0.1%)')
    parser.add_argument('--enable-boundary-check', action='store_true', default=True, help='啟用網格邊界檢查 (默認: True)')
    parser.add_argument('--disable-boundary-check', dest='enable_boundary_check', action='store_false', help='禁用網格邊界檢查')

    # 數據庫選項
    parser.add_argument('--enable-db', dest='enable_db', action='store_true', help='啟用資料庫寫入功能')
    parser.add_argument('--disable-db', dest='enable_db', action='store_false', help='停用資料庫寫入功能')
    parser.set_defaults(enable_db=ENABLE_DATABASE)
    
    # 重平設置參數
    parser.add_argument('--enable-rebalance', action='store_true', help='開啟重平功能')
    parser.add_argument('--disable-rebalance', action='store_true', help='關閉重平功能')
    parser.add_argument('--base-asset-target', type=float, help='基礎資產目標比例 (0-100, 默認: 30)')
    parser.add_argument('--rebalance-threshold', type=float, help='重平觸發閾值 (>0, 默認: 15)')

    return parser.parse_args()

def validate_rebalance_args(args):
    """驗證重平設置參數"""
    if getattr(args, 'market_type', 'spot') == 'perp':
        return
    if args.enable_rebalance and args.disable_rebalance:
        logger.error("不能同時設置 --enable-rebalance 和 --disable-rebalance")
        sys.exit(1)
    
    if args.base_asset_target is not None:
        if not 0 <= args.base_asset_target <= 100:
            logger.error("基礎資產目標比例必須在 0-100 之間")
            sys.exit(1)
    
    if args.rebalance_threshold is not None:
        if args.rebalance_threshold <= 0:
            logger.error("重平觸發閾值必須大於 0")
            sys.exit(1)

def start_web_server_in_background():
    """在後台啟動Web服務器"""
    try:
        from web.server import run_server
        import threading

        # 從環境變量或配置讀取端口
        web_port = int(os.getenv('WEB_PORT', '5000'))
        web_host = os.getenv('WEB_HOST', '0.0.0.0')

        # 在後台線程中啟動Web服務器
        web_thread = threading.Thread(target=run_server, kwargs={
            'host': web_host,
            'port': web_port,
            'debug': False
        }, daemon=True)
        web_thread.start()

        logger.info(f"Web服務器已在後台啟動，可通過 http://localhost:{web_port} 訪問")
        logger.info(f"健康檢查端點: http://localhost:{web_port}/health")
        logger.info(f"詳細狀態端點: http://localhost:{web_port}/health/detailed")

        # 等待一下讓服務器有時間啟動
        time.sleep(2)

    except Exception as e:
        logger.warning(f"啟動Web服務器失敗: {e}")
        logger.info("策略將繼續運行，但Web界面不可用")

def main():
    """主函數"""
    # 在程式啟動時自動清理舊log
    try:
        from core.log_manager import cleanup_old_logs
        cleanup_old_logs()  # 清理超過2天的舊log
        logger.info("已清理超過2天的舊日誌檔案")
    except Exception as e:
        logger.warning(f"清理舊日誌時發生錯誤: {e}")
    
    args = parse_arguments()
    
    # 驗證重平參數
    validate_rebalance_args(args)
    
    exchange = args.exchange
    api_key = ''
    secret_key = ''
    account_address: Optional[str] = None
    exchange_config = {}

    if exchange == 'backpack':
        api_key = os.getenv('BACKPACK_KEY', '')
        secret_key = os.getenv('BACKPACK_SECRET', '')
        base_url = os.getenv('BASE_URL', 'https://api.backpack.work')
        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
            'base_url': base_url,
            'api_version': 'v1',
            'default_window': '5000',
        }
    elif exchange == 'aster':
        api_key = os.getenv('ASTER_API_KEY', '')
        secret_key = os.getenv('ASTER_SECRET_KEY', '')
        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
        }
    elif exchange == 'paradex':
        private_key = os.getenv('PARADEX_PRIVATE_KEY', '')  # StarkNet 私鑰
        account_address = os.getenv('PARADEX_ACCOUNT_ADDRESS')  # StarkNet 帳户地址
        base_url = os.getenv('PARADEX_BASE_URL', 'https://api.prod.paradex.trade/v1')

        secret_key = private_key
        api_key = ''  # Paradex 不需要 API Key

        exchange_config = {
            'private_key': private_key,
            'account_address': account_address,
            'base_url': base_url,
        }
    elif exchange == 'lighter':
        api_key = os.getenv('LIGHTER_PRIVATE_KEY') or os.getenv('LIGHTER_API_KEY')
        secret_key = os.getenv('LIGHTER_SECRET_KEY') or api_key
        base_url = os.getenv('LIGHTER_BASE_URL')
        account_index = os.getenv('LIGHTER_ACCOUNT_INDEX')
        account_address = os.getenv('LIGHTER_ADDRESS')
        if not account_index and account_address:
            from api.lighter_client import _get_lihgter_account_index
            account_index = _get_lihgter_account_index(account_address)
        api_key_index = os.getenv('LIGHTER_API_KEY_INDEX')
        chain_id = os.getenv('LIGHTER_CHAIN_ID')

        exchange_config = {
            'api_private_key': api_key,
            'account_index': account_index,
            'api_key_index': api_key_index,
            'base_url': base_url,
        }
        if chain_id is not None:
            exchange_config['chain_id'] = chain_id
    elif exchange == 'apex':
        api_key = os.getenv('APEX_API_KEY', '')
        secret_key = os.getenv('APEX_SECRET_KEY', '')
        passphrase = os.getenv('APEX_PASSPHRASE', '')
        zk_seeds = os.getenv('APEX_ZK_SEEDS', '')
        base_url = os.getenv('APEX_BASE_URL', 'https://omni.apex.exchange')

        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
            'passphrase': passphrase,
            'zk_seeds': zk_seeds,
            'base_url': base_url,
        }
    else:
        logger.error("不支持的交易所，請選擇 'backpack'、'aster'、'paradex'、'lighter' 或 'apex'")
        sys.exit(1)

    # 檢查API密鑰
    if exchange == 'paradex':
        if not secret_key or not account_address:
            logger.error("Paradex 需要提供 StarkNet 私鑰與帳户地址，請確認環境變數已設定")
            sys.exit(1)
    elif exchange == 'lighter':
        if not api_key:
            logger.error("缺少 Lighter 私鑰，請使用 --api-key 或環境變量 LIGHTER_PRIVATE_KEY 提供")
            sys.exit(1)
        if not exchange_config.get('account_index'):
            logger.error("缺少 Lighter Account Index，請透過環境變量 LIGHTER_ACCOUNT_INDEX 提供")
            sys.exit(1)
    elif exchange == 'apex':
        if not api_key or not secret_key:
            logger.error("缺少 APEX API 密鑰，請通過環境變量 APEX_API_KEY 和 APEX_SECRET_KEY 提供")
            sys.exit(1)
    else:
        if not api_key or not secret_key:
            logger.error("缺少API密鑰，請通過命令行參數或環境變量提供")
            sys.exit(1)
    
    # 決定執行模式
    if args.web:
        # 啟動Web界面
        try:
            logger.info("啟動Web界面...")
            from web.server import run_server
            run_server(host='0.0.0.0', port=5000, debug=False)
        except ImportError as e:
            logger.error(f"啟動Web界面時出錯: {str(e)}")
            logger.error("請確保已安裝Flask和flask-socketio: pip install flask flask-socketio")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Web服務器錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    elif args.cli:
        # 啟動命令行界面
        try:
            from cli.commands import main_cli
            main_cli(api_key, secret_key, enable_database=args.enable_db, exchange=exchange)
        except ImportError as e:
            logger.error(f"啟動命令行界面時出錯: {str(e)}")
            sys.exit(1)
    elif args.symbol and (args.spread is not None or args.strategy in ['grid', 'perp_grid']):
        # 如果指定了交易對，直接運行策略（做市或網格）
        
        # 在後台啟動Web服務器，提供健康檢查和監控界面
        start_web_server_in_background()
        
        try:
            from strategies.market_maker import MarketMaker
            from strategies.maker_taker_hedge import MakerTakerHedgeStrategy
            from strategies.perp_market_maker import PerpetualMarketMaker
            from strategies.grid_strategy import GridStrategy
            from strategies.perp_grid_strategy import PerpGridStrategy
            
            # 處理重平設置
            market_type = args.market_type

            strategy_name = args.strategy

            # 獲取數據庫路徑（優先從環境變量讀取，支持多實例隔離）
            db_path = os.getenv('DB_PATH', DB_PATH)
            logger.info(f"數據庫路徑: {db_path}")

            # 網格策略處理
            if strategy_name == 'grid':
                logger.info("啟動現貨網格交易策略")
                logger.info(f"  網格數量: {args.grid_num}")
                logger.info(f"  網格模式: {args.grid_mode}")
                if args.auto_price:
                    logger.info(f"  自動價格範圍: ±{args.price_range}%")
                else:
                    logger.info(f"  價格範圍: {args.grid_lower} ~ {args.grid_upper}")

                market_maker = GridStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=args.symbol,
                    grid_upper_price=args.grid_upper,
                    grid_lower_price=args.grid_lower,
                    grid_num=args.grid_num,
                    order_quantity=args.quantity,
                    auto_price_range=args.auto_price,
                    price_range_percent=args.price_range,
                    grid_mode=args.grid_mode,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=args.enable_db,
                    db_path=db_path
                )

            elif strategy_name == 'perp_grid':
                logger.info("啟動永續合約網格交易策略")
                logger.info(f"  網格數量: {args.grid_num}")
                logger.info(f"  網格模式: {args.grid_mode}")
                logger.info(f"  網格類型: {args.grid_type}")
                logger.info(f"  最大持倉量: {args.max_position}")
                logger.info(f"  邊界處理方式: {args.boundary_action}")
                logger.info(f"  邊界容差: {args.boundary_tolerance:.3%}")
                logger.info(f"  邊界檢查: {'啟用' if args.enable_boundary_check else '禁用'}")
                if args.auto_price:
                    logger.info(f"  自動價格範圍: ±{args.price_range}%")
                else:
                    logger.info(f"  價格範圍: {args.grid_lower} ~ {args.grid_upper}")

                market_maker = PerpGridStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=args.symbol,
                    grid_upper_price=args.grid_upper,
                    grid_lower_price=args.grid_lower,
                    grid_num=args.grid_num,
                    order_quantity=args.quantity,
                    auto_price_range=args.auto_price,
                    price_range_percent=args.price_range,
                    grid_mode=args.grid_mode,
                    grid_type=args.grid_type,
                    target_position=args.target_position,
                    max_position=args.max_position,
                    position_threshold=args.position_threshold,
                    inventory_skew=args.inventory_skew,
                    stop_loss=args.stop_loss,
                    take_profit=args.take_profit,
                    boundary_action=args.boundary_action,
                    boundary_tolerance=args.boundary_tolerance,
                    enable_boundary_check=args.enable_boundary_check,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=args.enable_db,
                    db_path=db_path
                )

                if args.stop_loss is not None:
                    logger.info(f"  止損閾值: {args.stop_loss} {market_maker.quote_asset}")
                if args.take_profit is not None:
                    logger.info(f"  止盈閾值: {args.take_profit} {market_maker.quote_asset}")

            elif market_type == 'perp':
                logger.info(f"啟動永續合約做市模式 (策略: {strategy_name}, 交易所: {exchange})")
                logger.info(f"  目標持倉量: {abs(args.target_position)}")
                logger.info(f"  最大持倉量: {args.max_position}")
                logger.info(f"  倉位觸發值: {args.position_threshold}")
                logger.info(f"  報價偏移係數: {args.inventory_skew}")

                if strategy_name == 'maker_hedge':
                    market_maker = MakerTakerHedgeStrategy(
                        api_key=api_key,
                        secret_key=secret_key,
                        symbol=args.symbol,
                        base_spread_percentage=args.spread,
                        order_quantity=args.quantity,
                        target_position=args.target_position,
                        max_position=args.max_position,
                        position_threshold=args.position_threshold,
                        inventory_skew=args.inventory_skew,
                        stop_loss=args.stop_loss,
                        take_profit=args.take_profit,
                        exchange=exchange,
                        exchange_config=exchange_config,
                        enable_database=args.enable_db,
                        db_path=db_path,
                        market_type='perp'
                    )
                else:
                    market_maker = PerpetualMarketMaker(
                        api_key=api_key,
                        secret_key=secret_key,
                        symbol=args.symbol,
                        base_spread_percentage=args.spread,
                        order_quantity=args.quantity,
                        max_orders=args.max_orders,
                        target_position=args.target_position,
                        max_position=args.max_position,
                        position_threshold=args.position_threshold,
                        inventory_skew=args.inventory_skew,
                        stop_loss=args.stop_loss,
                        take_profit=args.take_profit,
                        exchange=exchange,
                        exchange_config=exchange_config,
                        enable_database=args.enable_db,
                        db_path=db_path
                    )

                if args.stop_loss is not None:
                    logger.info(f"  止損閾值: {args.stop_loss} {market_maker.quote_asset}")
                if args.take_profit is not None:
                    logger.info(f"  止盈閾值: {args.take_profit} {market_maker.quote_asset}")
            else:
                if strategy_name == 'maker_hedge':
                    logger.info("啟動 Maker-Taker 對沖現貨模式")
                    market_maker = MakerTakerHedgeStrategy(
                        api_key=api_key,
                        secret_key=secret_key,
                        symbol=args.symbol,
                        base_spread_percentage=args.spread,
                        order_quantity=args.quantity,
                        exchange=exchange,
                        exchange_config=exchange_config,
                        enable_database=args.enable_db,
                        db_path=db_path,
                        market_type='spot'
                    )
                else:
                    logger.info("啟動現貨做市模式")
                    enable_rebalance = True  # 默認開啟
                    base_asset_target_percentage = 30.0  # 默認30%
                    rebalance_threshold = 15.0  # 默認15%

                    if args.disable_rebalance:
                        enable_rebalance = False
                    elif args.enable_rebalance:
                        enable_rebalance = True

                    if args.base_asset_target is not None:
                        base_asset_target_percentage = args.base_asset_target

                    if args.rebalance_threshold is not None:
                        rebalance_threshold = args.rebalance_threshold

                    logger.info(f"重平設置:")
                    logger.info(f"  重平功能: {'開啟' if enable_rebalance else '關閉'}")
                    if enable_rebalance:
                        quote_asset_target_percentage = 100.0 - base_asset_target_percentage
                        logger.info(f"  目標比例: {base_asset_target_percentage}% 基礎資產 / {quote_asset_target_percentage}% 報價資產")
                        logger.info(f"  觸發閾值: {rebalance_threshold}%")

                    market_maker = MarketMaker(
                        api_key=api_key,
                        secret_key=secret_key,
                        symbol=args.symbol,
                        base_spread_percentage=args.spread,
                        order_quantity=args.quantity,
                        max_orders=args.max_orders,
                        enable_rebalance=enable_rebalance,
                        base_asset_target_percentage=base_asset_target_percentage,
                        rebalance_threshold=rebalance_threshold,
                        exchange=exchange,
                        exchange_config=exchange_config,
                        enable_database=args.enable_db,
                        db_path=db_path
                    )
            
            # 註冊策略到 Web 控制端（用於熱調整等功能）
            try:
                from web.server import current_strategy as web_current_strategy, bot_status
                from datetime import datetime
                
                # 更新全局狀態（使用 global 關鍵字）
                import web.server as web_server
                web_server.current_strategy = market_maker
                bot_status['running'] = True
                bot_status['strategy'] = args.strategy if hasattr(args, 'strategy') else 'standard'
                bot_status['start_time'] = datetime.now().isoformat()
                bot_status['last_update'] = datetime.now().isoformat()
                
                logger.info("策略已註冊到 Web 控制端，支持熱調整功能")
            except Exception as e:
                logger.warning(f"註冊策略到 Web 控制端失敗: {e}，熱調整功能可能不可用")
            
            # 執行做市策略（加入信號處理）
            try:
                run_strategy_with_signals(
                    market_maker,
                    duration_seconds=args.duration,
                    interval_seconds=args.interval,
                )
            finally:
                # 清理 Web 控制端狀態
                try:
                    from web.server import current_strategy as web_current_strategy, bot_status
                    from datetime import datetime
                    import web.server as web_server
                    web_server.current_strategy = None
                    bot_status['running'] = False
                    bot_status['last_update'] = datetime.now().isoformat()
                    logger.info("策略已從 Web 控制端註銷")
                except Exception:
                    pass
            
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在退出...")
        except InsufficientFundsError as e:
            # 資金不足，立即終止策略
            logger.error(f"資金不足，策略終止: {e}")
            logger.error("請確保賬戶有足夠的保證金後再重新啟動策略")
            sys.exit(1)
        except Exception as e:
            logger.error(f"做市過程中發生錯誤: {e}")
            import traceback
            traceback.print_exc()
    else:
        # 沒有指定執行模式時顯示幫助
        print("請指定執行模式：")
        print("  --web     啟動Web界面")
        print("  --cli     啟動命令行界面")
        print("  直接指定  --symbol 和 --spread 參數運行做市策略")
        print("\n支持的交易所：")
        print("  backpack  Backpack 交易所 (默認)")
        print("  aster     Aster 永續合約交易所")
        print("  paradex   Paradex 永續合約交易所")
        print("  lighter   Lighter 永續合約交易所")
        print("  apex      APEX Omni 永續合約交易所")
        print("\n資料庫參數：")
        print("  --enable-db            啟用資料庫寫入")
        print("  --disable-db           停用資料庫寫入 (預設)")
        print("\n重平設置參數：")
        print("  --enable-rebalance        開啟重平功能")
        print("  --disable-rebalance       關閉重平功能")
        print("  --base-asset-target 30    設置基礎資產目標比例為30%")
        print("  --rebalance-threshold 15  設置重平觸發閾值為15%")
        print("\n=== 範例：現貨做市 ===")
        print("  # Backpack 現貨做市")
        print("  python run.py --exchange backpack --symbol SOL_USDC --spread 0.5")
        print("\n=== 範例：現貨網格 ===")
        print("  # Backpack 現貨網格（自動價格範圍）")
        print("  python run.py --exchange backpack --symbol SOL_USDC --strategy grid --auto-price --grid-num 10")
        print("  # Backpack 現貨網格（手動設定價格範圍）")
        print("  python run.py --exchange backpack --symbol SOL_USDC --strategy grid --grid-lower 140 --grid-upper 160 --grid-num 10")
        print("\n=== 範例：永續合約做市 ===")
        print("  # Aster 永續合約做市")
        print("  python run.py --exchange aster --symbol BTCUSDT --spread 0.3 --market-type perp --max-position 0.5")
        print("  # Paradex 永續合約做市")
        print("  python run.py --exchange paradex --symbol BTC-USD-PERP --spread 0.3 --market-type perp --max-position 0.5")
        print("  # Lighter 永續合約做市")
        print("  python run.py --exchange lighter --symbol BTCUSDT --spread 0.3 --market-type perp --max-position 0.5")
        print("  # APEX 永續合約做市")
        print("  python run.py --exchange apex --symbol BTC-USDT --spread 0.3 --market-type perp --max-position 0.5")
        print("\n=== 範例：永續合約網格 ===")
        print("  # Aster 永續網格（中性網格，自動價格）")
        print("  python run.py --exchange aster --symbol BTCUSDT --strategy perp_grid --auto-price --grid-num 10 --grid-type neutral")
        print("  # Paradex 永續網格（做多網格）")
        print("  python run.py --exchange paradex --symbol BTC-USD-PERP --strategy perp_grid --grid-lower 45000 --grid-upper 50000 --grid-num 10 --grid-type long")
        print("  # Lighter 永續網格（做空網格）")
        print("  python run.py --exchange lighter --symbol BTCUSDT --strategy perp_grid --grid-lower 45000 --grid-upper 50000 --grid-num 10 --grid-type short")
        print("  # 永續網格（帶止損止盈）")
        print("  python run.py --exchange aster --symbol ETHUSDT --strategy perp_grid --auto-price --grid-num 15 --stop-loss 100 --take-profit 200")
        print("\n使用 --help 查看完整幫助")

if __name__ == "__main__":
    main()
