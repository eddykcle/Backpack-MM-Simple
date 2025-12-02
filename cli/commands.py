"""
CLI命令模塊，提供命令行交互功能
"""
import time
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import requests
import json
from pathlib import Path

from api.bp_client import BPClient
from api.aster_client import AsterClient
from api.paradex_client import ParadexClient
from api.lighter_client import LighterClient
from api.apex_client import ApexClient
from ws_client.client import BackpackWebSocket
from strategies.market_maker import MarketMaker
from strategies.perp_market_maker import PerpetualMarketMaker
from strategies.maker_taker_hedge import MakerTakerHedgeStrategy
from strategies.grid_strategy import GridStrategy
from strategies.perp_grid_strategy import PerpGridStrategy
from utils.helpers import calculate_volatility
from utils.input_validation import CliValidator
from database.db import Database
from config import API_KEY, SECRET_KEY, ENABLE_DATABASE
from core.logger import setup_logger
from core.instance_manager import InstanceRegistry

logger = setup_logger("cli")

# 緩存客户端實例以提高性能
_client_cache = {}
USE_DATABASE = ENABLE_DATABASE

def _resolve_api_credentials(exchange: str, api_key: Optional[str], secret_key: Optional[str]):
    """根據交易所解析並返回對應的 API/Secret Key。"""
    exchange = (exchange or "backpack").lower()

    if exchange == "aster":
        api_candidates = [
            os.getenv("ASTER_API_KEY"),
            os.getenv("ASTER_KEY"),
        ]
        secret_candidates = [
            os.getenv("ASTER_SECRET_KEY"),
            os.getenv("ASTER_SECRET"),
        ]
    elif exchange == "paradex":
        # Paradex 使用 StarkNet 認證，不需要傳統的 API Key
        # 使用 account_address 作為 api_key 的佔位符
        api_candidates = [
            os.getenv("PARADEX_ACCOUNT_ADDRESS"),
        ]
        secret_candidates = [
            os.getenv("PARADEX_PRIVATE_KEY"),
        ]
        # Paradex 使用 StarkNet 賬户地址和私鑰進行認證
    elif exchange == "lighter":
        # Lighter私鑰候選項（支持多個環境變量名）
        api_candidates = [
            os.getenv("LIGHTER_PRIVATE_KEY"),
            os.getenv("LIGHTER_API_KEY"),
        ]
        # Account Index候選項
        account_index_candidates = [
            os.getenv("LIGHTER_ACCOUNT_INDEX"),
        ]
        # 如果沒有account_index，嘗試通過地址自動獲取
        account_index_value = next((value for value in account_index_candidates if value), None)
        if not account_index_value:
            lighter_address = os.getenv("LIGHTER_ADDRESS")
            if lighter_address:
                try:
                    from api.lighter_client import _get_lihgter_account_index
                    account_index_value = str(_get_lihgter_account_index(lighter_address))
                    logger.info(f"通過地址 {lighter_address} 自動獲取到 account_index: {account_index_value}")
                except Exception as e:
                    logger.warning(f"無法通過地址自動獲取account_index: {e}")
                    account_index_value = None

        # 將account_index作為secret_candidates返回
        secret_candidates = [account_index_value] if account_index_value else []
    elif exchange == "apex":
        api_candidates = [
            os.getenv("APEX_API_KEY"),
        ]
        secret_candidates = [
            os.getenv("APEX_SECRET_KEY"),
        ]
    else:
        api_candidates = [
            os.getenv("BACKPACK_KEY"),
            os.getenv("API_KEY"),
        ]
        secret_candidates = [
            os.getenv("BACKPACK_SECRET"),
            os.getenv("SECRET_KEY"),
        ]

    resolved_api_key = next((value for value in api_candidates if value), None) or api_key
    resolved_secret_key = next((value for value in secret_candidates if value), None) or secret_key

    return resolved_api_key, resolved_secret_key


def _get_client(api_key=None, secret_key=None, exchange='backpack', exchange_config=None):
    """獲取緩存的客户端實例，避免重複創建"""
    exchange = (exchange or 'backpack').lower()
    if exchange not in ('backpack', 'aster', 'paradex', 'lighter', 'apex'):
        raise ValueError(f"不支持的交易所: {exchange}")

    config = dict(exchange_config or {})
    config_api_key = api_key or config.get('api_key')
    config_secret_key = secret_key or config.get('secret_key') or config.get('private_key')

    # Lighter特殊處理：api_key是private_key，secret_key是account_index
    if exchange == 'lighter':
        if config_api_key:
            config['api_private_key'] = config_api_key
            config.pop('api_key', None)
        if config_secret_key:
            config['account_index'] = config_secret_key
            config.pop('secret_key', None)
            config.pop('private_key', None)

        # 確保其他必要的Lighter配置存在
        if 'base_url' not in config:
            config['base_url'] = os.getenv('LIGHTER_BASE_URL')
        if 'api_key_index' not in config:
            api_key_index = os.getenv('LIGHTER_API_KEY_INDEX')
            if api_key_index:
                config['api_key_index'] = api_key_index
        if 'chain_id' not in config:
            chain_id = os.getenv('LIGHTER_CHAIN_ID')
            if chain_id:
                config['chain_id'] = chain_id
        if 'verify_ssl' not in config:
            verify_ssl_env = os.getenv('LIGHTER_VERIFY_SSL')
            if verify_ssl_env is not None:
                config['verify_ssl'] = verify_ssl_env.lower() not in ('0', 'false', 'no')
    # Paradex使用private_key
    elif exchange == 'paradex':
        if config_api_key:
            config['api_key'] = config_api_key
        if config_secret_key:
            config['private_key'] = config_secret_key
            config.pop('secret_key', None)
    # APEX需要額外的zk_seeds
    elif exchange == 'apex':
        if config_api_key:
            config['api_key'] = config_api_key
        if config_secret_key:
            config['secret_key'] = config_secret_key
        if 'passphrase' not in config:
            config['passphrase'] = os.getenv('APEX_PASSPHRASE', '')
        if 'zk_seeds' not in config:
            config['zk_seeds'] = os.getenv('APEX_ZK_SEEDS', '')
        if 'base_url' not in config:
            config['base_url'] = os.getenv('APEX_BASE_URL', 'https://omni.apex.exchange')
    # 其他交易所使用傳統的api_key/secret_key
    else:
        if config_api_key:
            config['api_key'] = config_api_key
        else:
            config.pop('api_key', None)

        if config_secret_key:
            config['secret_key'] = config_secret_key
            config.pop('private_key', None)
        else:
            config.pop('secret_key', None)
            config.pop('private_key', None)

    # 生成緩存鍵
    if exchange == 'lighter':
        # Lighter使用api_private_key和account_index
        cache_suffix = (
            f"{config.get('api_private_key', '')}_{config.get('account_index', '')}"
            if config.get('api_private_key') or config.get('account_index')
            else 'public'
        )
    elif exchange == 'paradex':
        # Paradex使用private_key
        cache_suffix = (
            f"{config.get('account_address', '')}_{config.get('private_key', '')}"
            if config.get('account_address') or config.get('private_key')
            else 'public'
        )
    elif exchange == 'apex':
        # APEX使用api_key/secret_key
        cache_suffix = (
            f"{config.get('api_key', '')}_{config.get('secret_key', '')}"
            if config.get('api_key') or config.get('secret_key')
            else 'public'
        )
    else:
        # 其他交易所使用api_key/secret_key
        cache_suffix = (
            f"{config.get('api_key', '')}_{config.get('secret_key', '')}"
            if config.get('api_key') or config.get('secret_key')
            else 'public'
        )
    cache_key = f"{exchange}:{cache_suffix}"

    if cache_key not in _client_cache:
        if exchange == 'backpack':
            client_cls = BPClient
        elif exchange == 'aster':
            client_cls = AsterClient
        elif exchange == 'paradex':
            client_cls = ParadexClient
        elif exchange == 'lighter':
            client_cls = LighterClient
        else:  # apex
            client_cls = ApexClient
        _client_cache[cache_key] = client_cls(config)

    return _client_cache[cache_key]


def get_address_command(api_key, secret_key):
    """獲取存款地址命令"""
    blockchain = input("請輸入區塊鏈名稱(Solana, Ethereum, Bitcoin等): ")
    result = _get_client(api_key, secret_key).get_deposit_address(blockchain)
    print(result)

def get_balance_command(api_key, secret_key):
    """獲取餘額命令 - 檢查所有已配置的交易所"""

    # 定義要檢查的交易所列表
    exchanges_to_check = []

    # 檢查 Backpack
    backpack_api, backpack_secret = _resolve_api_credentials('backpack', api_key, secret_key)
    if backpack_api and backpack_secret:
        exchanges_to_check.append(('backpack', backpack_api, backpack_secret))

    # 檢查 Aster
    aster_api, aster_secret = _resolve_api_credentials('aster', None, None)
    if aster_api and aster_secret:
        exchanges_to_check.append(('aster', aster_api, aster_secret))

    # 檢查 Paradex
    paradex_account, paradex_key = _resolve_api_credentials('paradex', None, None)
    if paradex_account and paradex_key:
        exchanges_to_check.append(('paradex', paradex_account, paradex_key))

    # 檢查 Lighter
    lighter_private, lighter_account_index = _resolve_api_credentials('lighter', None, None)
    if lighter_private and lighter_account_index:
        exchanges_to_check.append(('lighter', lighter_private, lighter_account_index))

    # 檢查 APEX
    apex_api, apex_secret = _resolve_api_credentials('apex', None, None)
    if apex_api and apex_secret:
        exchanges_to_check.append(('apex', apex_api, apex_secret))

    if not exchanges_to_check:
        print("未找到任何已配置的交易所 API 密鑰")
        return

    # 遍歷所有交易所並獲取餘額
    for exchange, ex_api_key, ex_secret_key in exchanges_to_check:
        print(f"\n{'='*60}")
        print(f"交易所: {exchange.upper()}")
        print(f"{'='*60}")

        try:
            exchange_config = {
                'api_key': ex_api_key,
            }

            if exchange == 'paradex':
                exchange_config['private_key'] = ex_secret_key
                exchange_config['account_address'] = ex_api_key
                exchange_config['base_url'] = os.getenv('PARADEX_BASE_URL', 'https://api.prod.paradex.trade/v1')
            elif exchange == 'lighter':
                exchange_config = {
                    'api_private_key': ex_api_key,
                    'account_index': ex_secret_key,
                    'api_key_index': os.getenv('LIGHTER_API_KEY_INDEX'),
                    'base_url': os.getenv('LIGHTER_BASE_URL'),
                }
                chain_id = os.getenv('LIGHTER_CHAIN_ID')
                if chain_id:
                    exchange_config['chain_id'] = chain_id
                verify_ssl_env = os.getenv('LIGHTER_VERIFY_SSL')
                if verify_ssl_env is not None:
                    exchange_config['verify_ssl'] = verify_ssl_env.lower() not in ('0', 'false', 'no')
            elif exchange == 'apex':
                exchange_config = {
                    'api_key': ex_api_key,
                    'secret_key': ex_secret_key,
                    'passphrase': os.getenv('APEX_PASSPHRASE', ''),
                    'base_url': os.getenv('APEX_BASE_URL', 'https://omni.apex.exchange'),
                }
            else:
                exchange_config['secret_key'] = ex_secret_key
            
            secret_for_client = ex_secret_key
            c = _get_client(api_key=ex_api_key, secret_key=secret_for_client, exchange=exchange, exchange_config=exchange_config)
            balances = c.get_balance()
            collateral = c.get_collateral()
            
            if isinstance(balances, dict) and "error" in balances and balances["error"]:
                print(f"獲取餘額失敗: {balances['error']}")
            else:
                print("\n當前餘額:")
                has_balance = False
                if isinstance(balances, dict):
                    # 對於Lighter，USDC/USD/USDT是別名，只顯示一次
                    seen_objects = set()
                    for coin, details in balances.items():
                        if isinstance(details, dict):
                            # 使用id()檢查是否是同一對象（別名）
                            obj_id = id(details)
                            if obj_id in seen_objects:
                                continue
                            seen_objects.add(obj_id)

                            available = float(details.get('available', 0))
                            locked = float(details.get('locked', 0))
                            total = float(details.get('total', available + locked))
                            if available > 0 or locked > 0 or total > 0:
                                asset_name = details.get('asset', coin)
                                # APEX 顯示總權益和可用保證金
                                if exchange == 'apex':
                                    print(f"{asset_name}: 總權益 {total}, 可用保證金 {available}")
                                else:
                                    print(f"{asset_name}: 可用 {available}, 凍結 {locked}")
                                has_balance = True
                    if not has_balance:
                        print("無餘額記錄")
                else:
                    print(f"獲取餘額失敗: 無法識別返回格式 {type(balances)}")

            # Paradex 的抵押品信息格式不同
            if exchange == 'paradex':
                if isinstance(collateral, dict) and "error" in collateral:
                    print(f"獲取賬户摘要失敗: {collateral['error']}")
                elif isinstance(collateral, dict) and collateral.get('account'):
                    print("\n賬户摘要:")
                    print(f"賬户地址: {collateral.get('account', 'N/A')}")
                    print(f"賬户價值: {collateral.get('account_value', '0')} USDC")
                    print(f"總抵押品: {collateral.get('total_collateral', '0')} USDC")
                    print(f"可用抵押品: {collateral.get('free_collateral', '0')} USDC")
                    print(f"初始保證金: {collateral.get('initial_margin', '0')} USDC")
                    print(f"維持保證金: {collateral.get('maintenance_margin', '0')} USDC")
            elif exchange == 'lighter':
                # Lighter 的抵押品信息格式
                if isinstance(collateral, dict) and "error" in collateral:
                    print(f"獲取抵押品失敗: {collateral['error']}")
                elif isinstance(collateral, dict):
                    total_collateral = collateral.get('totalCollateral', 0)
                    available_collateral = collateral.get('availableCollateral', 0)
                    total_asset_value = collateral.get('totalAssetValue', 0)
                    cross_asset_value = collateral.get('crossAssetValue', 0)

                    print("\n賬户摘要:")
                    print(f"總抵押品: {total_collateral} USDC")
                    print(f"可用抵押品: {available_collateral} USDC")
                    if total_asset_value:
                        print(f"總資產價值: {total_asset_value} USDC")
                    if cross_asset_value:
                        print(f"跨倉資產價值: {cross_asset_value} USDC")

                    # 顯示持倉信息（如果有）
                    assets = collateral.get('assets', [])
            elif exchange == 'apex':
                # APEX 的抵押品信息格式
                if isinstance(collateral, dict) and "error" in collateral:
                    print(f"獲取抵押品失敗: {collateral['error']}")
                elif isinstance(collateral, dict):
                    total_collateral = collateral.get('totalCollateral', 0)
                    available_collateral = collateral.get('availableCollateral', 0)
                    token = collateral.get('token', 'USDC')
                    maker_fee = collateral.get('makerFeeRate', '0')
                    taker_fee = collateral.get('takerFeeRate', '0')

                    print("\n賬户摘要:")
                    print(f"合約錢包餘額: {total_collateral} {token}")
                    if maker_fee != '0' or taker_fee != '0':
                        print(f"Maker 費率: {float(maker_fee)*100:.2f}%")
                        print(f"Taker 費率: {float(taker_fee)*100:.2f}%")
            else:
                # 其他交易所的抵押品信息
                if isinstance(collateral, dict) and "error" in collateral:
                    print(f"獲取抵押品失敗: {collateral['error']}")
                elif isinstance(collateral, dict):
                    assets = collateral.get('assets') or collateral.get('collateral', [])
                    if assets:
                        print("\n抵押品資產:")
                        for item in assets:
                            symbol = item.get('symbol', '')
                            total = item.get('totalQuantity', '')
                            available = item.get('availableQuantity', '')
                            lend = item.get('lendQuantity', '')
                            collateral_value = item.get('collateralValue', '')
                            print(f"{symbol}: 總量 {total}, 可用 {available}, 出借中 {lend}, 抵押價值 {collateral_value}")
        
        except Exception as e:
            print(f"查詢 {exchange.upper()} 餘額時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()

def get_markets_command():
    """獲取市場信息命令"""
    print("\n獲取市場信息...")
    markets_info = _get_client().get_markets()
    
    if isinstance(markets_info, dict) and "error" in markets_info:
        print(f"獲取市場信息失敗: {markets_info['error']}")
        return
    
    spot_markets = [m for m in markets_info if m.get('marketType') == 'SPOT']
    print(f"\n找到 {len(spot_markets)} 個現貨市場:")
    for i, market in enumerate(spot_markets):
        symbol = market.get('symbol')
        base = market.get('baseSymbol')
        quote = market.get('quoteSymbol')
        market_type = market.get('marketType')
        print(f"{i+1}. {symbol} ({base}/{quote}) - {market_type}")

def get_orderbook_command(api_key, secret_key):
    """獲取市場深度命令"""
    symbol = input("請輸入交易對 (例如: SOL_USDC): ")
    try:
        print("連接WebSocket獲取實時訂單簿...")
        ws = BackpackWebSocket(api_key, secret_key, symbol, auto_reconnect=True)
        ws.connect()
        
        # 等待連接建立
        wait_time = 0
        max_wait_time = 5
        while not ws.connected and wait_time < max_wait_time:
            time.sleep(0.5)
            wait_time += 0.5
        
        if not ws.connected:
            print("WebSocket連接超時，使用REST API獲取訂單簿")
            depth = _get_client().get_order_book(symbol)
        else:
            # 初始化訂單簿並訂閲深度流
            ws.initialize_orderbook()
            ws.subscribe_depth()
            
            # 等待數據更新
            time.sleep(2)
            depth = ws.get_orderbook()
        
        print("\n訂單簿:")
        print("\n賣單 (從低到高):")
        if 'asks' in depth and depth['asks']:
            asks = sorted(depth['asks'], key=lambda x: x[0])[:10]  # 多展示幾個深度
            for i, (price, quantity) in enumerate(asks):
                print(f"{i+1}. 價格: {price}, 數量: {quantity}")
        else:
            print("無賣單數據")
        
        print("\n買單 (從高到低):")
        if 'bids' in depth and depth['bids']:
            bids = sorted(depth['bids'], key=lambda x: x[0], reverse=True)[:10]  # 多展示幾個深度
            for i, (price, quantity) in enumerate(bids):
                print(f"{i+1}. 價格: {price}, 數量: {quantity}")
        else:
            print("無買單數據")
        
        # 分析市場情緒
        if ws.connected:
            liquidity_profile = ws.get_liquidity_profile()
            if liquidity_profile:
                buy_volume = liquidity_profile['bid_volume']
                sell_volume = liquidity_profile['ask_volume']
                imbalance = liquidity_profile['imbalance']
                
                print("\n市場流動性分析:")
                print(f"買單量: {buy_volume:.4f}")
                print(f"賣單量: {sell_volume:.4f}")
                print(f"買賣比例: {(buy_volume/sell_volume):.2f}") if sell_volume > 0 else print("買賣比例: 無限")
                
                # 判斷市場情緒
                sentiment = "買方壓力較大" if imbalance > 0.2 else "賣方壓力較大" if imbalance < -0.2 else "買賣壓力平衡"
                print(f"市場情緒: {sentiment} ({imbalance:.2f})")
        
        # 關閉WebSocket連接
        ws.close()
        
    except Exception as e:
        print(f"獲取訂單簿失敗: {str(e)}")
        # 嘗試使用REST API
        try:
            depth = _get_client().get_order_book(symbol)
            if isinstance(depth, dict) and "error" in depth:
                print(f"獲取訂單簿失敗: {depth['error']}")
                return
            
            print("\n訂單簿 (REST API):")
            print("\n賣單 (從低到高):")
            if 'asks' in depth and depth['asks']:
                asks = sorted([
                    [float(price), float(quantity)] for price, quantity in depth['asks']
                ], key=lambda x: x[0])[:10]
                for i, (price, quantity) in enumerate(asks):
                    print(f"{i+1}. 價格: {price}, 數量: {quantity}")
            else:
                print("無賣單數據")
            
            print("\n買單 (從高到低):")
            if 'bids' in depth and depth['bids']:
                bids = sorted([
                    [float(price), float(quantity)] for price, quantity in depth['bids']
                ], key=lambda x: x[0], reverse=True)[:10]
                for i, (price, quantity) in enumerate(bids):
                    print(f"{i+1}. 價格: {price}, 數量: {quantity}")
            else:
                print("無買單數據")
        except Exception as e:
            print(f"使用REST API獲取訂單簿也失敗: {str(e)}")

def configure_rebalance_settings():
    """配置重平設置"""
    print("\n=== 重平設置配置 ===")
    
    # 是否開啟重平功能
    while True:
        enable_input = input("是否開啟重平功能? (y/n，默認: y): ").strip().lower()
        if enable_input in ['', 'y', 'yes']:
            enable_rebalance = True
            break
        elif enable_input in ['n', 'no']:
            enable_rebalance = False
            break
        else:
            print("請輸入 y 或 n")
    
    base_asset_target_percentage = 30.0  # 默認值
    rebalance_threshold = 15.0  # 默認值
    
    if enable_rebalance:
        # 設置基礎資產目標比例
        while True:
            try:
                percentage_input = input("請輸入基礎資產目標比例 (0-100，默認: 30): ").strip()
                if percentage_input == '':
                    base_asset_target_percentage = 30.0
                    break
                else:
                    percentage = float(percentage_input)
                    if 0 <= percentage <= 100:
                        base_asset_target_percentage = percentage
                        break
                    else:
                        print("比例必須在 0-100 之間")
            except ValueError:
                print("請輸入有效的數字")
        
        # 設置重平觸發閾值
        while True:
            try:
                threshold_input = input("請輸入重平觸發閾值 (>0，默認: 15): ").strip()
                if threshold_input == '':
                    rebalance_threshold = 15.0
                    break
                else:
                    threshold = float(threshold_input)
                    if threshold > 0:
                        rebalance_threshold = threshold
                        break
                    else:
                        print("閾值必須大於 0")
            except ValueError:
                print("請輸入有效的數字")
        
        quote_asset_target_percentage = 100.0 - base_asset_target_percentage
        
        print(f"\n重平設置:")
        print(f"重平功能: 開啟")
        print(f"目標比例: {base_asset_target_percentage}% 基礎資產 / {quote_asset_target_percentage}% 報價資產")
        print(f"觸發閾值: {rebalance_threshold}%")
    else:
        print(f"\n重平設置:")
        print(f"重平功能: 關閉")
    
    return enable_rebalance, base_asset_target_percentage, rebalance_threshold

def run_market_maker_command(api_key, secret_key):
    """執行做市策略命令"""
    # [整合功能] 1. 增加交易所選擇
    exchange_input = input("請選擇交易所 (backpack/aster/paradex/lighter/apex，默認 backpack): ").strip().lower()

    # 處理交易所選擇
    if exchange_input in ('backpack', 'aster', 'paradex', 'lighter', 'apex', ''):
        exchange = exchange_input if exchange_input else 'backpack'
    else:
        print(f"警告: 不識別的交易所 '{exchange_input}'，使用默認 'backpack'")
        exchange = 'backpack'

    print(f"已選擇交易所: {exchange}")

    # [整合功能] 2. 根據選擇配置交易所信息
    api_key, secret_key = _resolve_api_credentials(exchange, api_key, secret_key)

    if not api_key or not secret_key:
        print("錯誤：未找到對應交易所的 API Key 或 Secret Key，請先設置環境變數或配置檔案。")
        return

    # 初始化 exchange_config
    exchange_config = None

    if exchange == 'backpack':
        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
            'base_url': os.getenv('BASE_URL', 'https://api.backpack.work'),
            'api_version': 'v1',
            'default_window': '5000',
        }
    elif exchange == 'aster':
        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
        }
    elif exchange == 'paradex':
        exchange_config = {
            'private_key': secret_key,  # Paradex 使用 StarkNet 私鑰
            'account_address': api_key or os.getenv('PARADEX_ACCOUNT_ADDRESS'),  # StarkNet 賬户地址
            'base_url': os.getenv('PARADEX_BASE_URL', 'https://api.prod.paradex.trade/v1'),
        }
    elif exchange == 'lighter':
        exchange_config = {
            'api_private_key': api_key,
            'account_index': secret_key,
            'base_url': os.getenv('LIGHTER_BASE_URL'),
        }
        api_key_index = os.getenv('LIGHTER_API_KEY_INDEX')
        if api_key_index:
            exchange_config['api_key_index'] = api_key_index
        chain_id = os.getenv('LIGHTER_CHAIN_ID')
        if chain_id:
            exchange_config['chain_id'] = chain_id
        verify_ssl_env = os.getenv('LIGHTER_VERIFY_SSL')
        if verify_ssl_env is not None:
            exchange_config['verify_ssl'] = verify_ssl_env.lower() not in ('0', 'false', 'no')
    elif exchange == 'apex':
        exchange_config = {
            'api_key': api_key,
            'secret_key': secret_key,
            'passphrase': os.getenv('APEX_PASSPHRASE', ''),
            'base_url': os.getenv('APEX_BASE_URL', 'https://omni.apex.exchange'),
        }
    else:
        print("錯誤：不支持的交易所。")
        return

    # 市場類型選擇
    market_type_input = input("請選擇市場類型 (spot/perp，默認 spot): ").strip().lower()

    # 處理常見別名
    if market_type_input in ("perpetual", "future", "futures", "contract"):
        print("提示: 已識別為永續合約 'perp'")
        market_type = "perp"
    elif market_type_input in ("spot", "perp", ""):
        market_type = market_type_input if market_type_input else "spot"
    else:
        print(f"警告: 不識別的市場類型 '{market_type_input}'，使用默認 'spot'")
        market_type = "spot"

    # 策略選擇（支援拼寫糾正）
    strategy_input = input("請選擇策略 (standard/maker_hedge/grid，默認 standard): ").strip().lower()

    # 處理常見拼寫錯誤
    if strategy_input in ("marker_hedge", "make_hedge", "makertaker", "maker-hedge"):
        print(f"提示: 已自動糾正 '{strategy_input}' -> 'maker_hedge'")
        strategy = "maker_hedge"
    elif strategy_input in ("standard", "maker_hedge", "grid", ""):
        strategy = strategy_input if strategy_input else "standard"
    else:
        print(f"警告: 不識別的策略 '{strategy_input}'，使用默認策略 'standard'")
        strategy = "standard"

    print(f"已選擇策略: {strategy}")

    symbol = input("請輸入要做市的交易對 (例如: SOL_USDC): ")
    client = _get_client(exchange=exchange, exchange_config=exchange_config)
    market_limits = client.get_market_limits(symbol)
    if not market_limits:
        print(f"交易對 {symbol} 不存在或不可交易")
        return

    base_asset = market_limits.get('base_asset') or symbol
    quote_asset = market_limits.get('quote_asset') or ''
    market_desc = f"{symbol}" if not quote_asset else f"{symbol} ({base_asset}/{quote_asset})"

    if market_type == "spot":
        print(f"已選擇現貨市場 {market_desc}")
    else:
        print(f"已選擇永續合約市場 {market_desc}")

    # 根據策略類型獲取不同的參數
    if strategy == "grid":
        # 網格策略參數
        print("\n=== 網格策略參數配置 ===")

        # 自動價格範圍選項
        auto_range_input = input("是否自動設置價格範圍? (y/n，默認 n): ").strip().lower()
        auto_price_range = auto_range_input in ('y', 'yes', '是')

        grid_upper_price = None
        grid_lower_price = None
        price_range_percent = 5.0

        if not auto_price_range:
            # 手動設置價格範圍
            grid_upper_input = input("請輸入網格上限價格: ").strip()
            grid_lower_input = input("請輸入網格下限價格: ").strip()

            if grid_upper_input and grid_lower_input:
                grid_upper_price = float(grid_upper_input)
                grid_lower_price = float(grid_lower_input)
            else:
                print("警告: 價格範圍未設置，將自動計算")
                auto_price_range = True

        if auto_price_range:
            # 自動模式：設置價格範圍百分比
            range_input = input("請輸入價格範圍百分比 (默認 5，表示當前價格 ±5%): ").strip()
            price_range_percent = float(range_input) if range_input else 5.0

        # 網格數量
        grid_num_input = input("請輸入網格數量 (默認 10): ").strip()
        grid_num = int(grid_num_input) if grid_num_input else 10

        # 網格模式
        grid_mode_input = input("請選擇網格模式 (arithmetic/geometric，默認 arithmetic): ").strip().lower()
        grid_mode = grid_mode_input if grid_mode_input in ('arithmetic', 'geometric') else 'arithmetic'

        # 每格訂單數量
        quantity_input = input("請輸入每格訂單數量 (留空則使用最小訂單量): ").strip()
        quantity = float(quantity_input) if quantity_input else None

        # 永續合約網格特有參數
        if market_type == "perp":
            grid_type_input = input("請選擇網格類型 (neutral/long/short，默認 neutral): ").strip().lower()
            grid_type = grid_type_input if grid_type_input in ('neutral', 'long', 'short') else 'neutral'
            print(f"已選擇網格類型: {grid_type}")
        else:
            grid_type = None

        # 標準策略的參數（網格不使用）
        spread_percentage = 0.1
        max_orders = 1
    else:
        # 標準策略和對沖策略參數
        spread_percentage = float(input("請輸入價差百分比 (例如: 0.5 表示0.5%): "))
        quantity_input = input("請輸入每個訂單的數量 (留空則自動根據餘額計算): ")
        quantity = float(quantity_input) if quantity_input.strip() else None
        max_orders = int(input("請輸入每側(買/賣)最大訂單數 (例如: 3): "))

        # 網格策略參數（標準策略不使用）
        grid_upper_price = None
        grid_lower_price = None
        grid_num = 10
        grid_mode = 'arithmetic'
        auto_price_range = False
        price_range_percent = 5.0
        grid_type = None

    if market_type == "perp":
        if strategy == "grid":
            # 網格策略使用簡化的持倉參數
            print("\n=== 永續合約網格持倉參數 ===")
            max_position_input = input("最大允許持倉量(絕對值) (默認 1.0): ").strip()
            max_position = float(max_position_input) if max_position_input else 1.0

            stop_loss_input = input("未實現止損閾值 (報價資產金額，支援輸入負值，例如 -25，留空不啟用): ").strip()
            stop_loss = float(stop_loss_input) if stop_loss_input else None

            take_profit_input = input("未實現止盈閾值 (報價資產金額，留空不啟用): ").strip()
            take_profit = float(take_profit_input) if take_profit_input else None

            # 網格策略的默認值
            target_position = 0.0
            position_threshold = 0.1
            inventory_skew = 0.0

            if max_position <= 0:
                print("錯誤: 最大持倉量必須大於0")
                return
            if stop_loss is not None and stop_loss >= 0:
                print("錯誤: 止損閾值必須輸入負值 (例如 -25)")
                return
            if take_profit is not None and take_profit <= 0:
                print("錯誤: 止盈閾值必須大於0")
                return
        else:
            # 標準策略和對沖策略的持倉參數
            try:
                target_position_input = input("請輸入目標持倉量 (絕對值, 例如 1.0, 默認 1): ").strip()
                target_position = float(target_position_input) if target_position_input else 1.0

                max_position_input = input("最大允許持倉量(絕對值) (默認 1.0): ").strip()
                max_position = float(max_position_input) if max_position_input else 1.0

                threshold_input = input("倉位調整觸發值 (默認 0.1): ").strip()
                position_threshold = float(threshold_input) if threshold_input else 0.1

                skew_input = input("倉位偏移調整係數 (0-1，默認 0.0): ").strip()
                inventory_skew = float(skew_input) if skew_input else 0.0

                stop_loss_input = input("未實現止損閾值 (報價資產金額，支援輸入負值，例如 -25，留空不啟用): ").strip()
                stop_loss = float(stop_loss_input) if stop_loss_input else None

                take_profit_input = input("未實現止盈閾值 (報價資產金額，留空不啟用): ").strip()
                take_profit = float(take_profit_input) if take_profit_input else None

                if max_position <= 0:
                    raise ValueError("最大持倉量必須大於0")
                if position_threshold <= 0:
                    raise ValueError("倉位調整觸發值必須大於0")
                if not 0 <= inventory_skew <= 1:
                    raise ValueError("倉位偏移調整係數需介於0-1之間")
                if stop_loss is not None:
                    if stop_loss >= 0:
                        raise ValueError("止損閾值必須輸入負值 (例如 -25)")
                if take_profit is not None and take_profit <= 0:
                    raise ValueError("止盈閾值必須大於0")
            except ValueError as exc:
                print(f"倉位參數輸入錯誤: {exc}")
                return

        enable_rebalance = False
        base_asset_target_percentage = 0.0
        rebalance_threshold = 0.0
    else:
        if strategy in ("maker_hedge", "grid"):
            enable_rebalance = False
            base_asset_target_percentage = 0.0
            rebalance_threshold = 0.0
        else:
            enable_rebalance, base_asset_target_percentage, rebalance_threshold = configure_rebalance_settings()
        target_position = 0.0
        max_position = 0.0
        position_threshold = 0.0
        inventory_skew = 0.0
        stop_loss = None
        take_profit = None

    duration = int(input("請輸入運行時間(秒) (例如: 3600 表示1小時): "))
    interval = int(input("請輸入更新間隔(秒) (例如: 60 表示1分鐘): "))

    if not USE_DATABASE:
        print("提示: 資料庫寫入已停用，本次執行僅在記憶體中追蹤統計。")

    db = None
    try:
        if USE_DATABASE:
            db = Database()
        # 原有的 exchange_config 創建邏輯已被新的動態配置取代
							   
									
		 

        if market_type == "perp":
            if strategy == "grid":
                # 永續合約網格策略
                market_maker = PerpGridStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    grid_upper_price=grid_upper_price,
                    grid_lower_price=grid_lower_price,
                    grid_num=grid_num,
                    order_quantity=quantity,
                    auto_price_range=auto_price_range,
                    price_range_percent=price_range_percent,
                    grid_mode=grid_mode,
                    grid_type=grid_type,
                    target_position=target_position,
                    max_position=max_position,
                    position_threshold=position_threshold,
                    inventory_skew=inventory_skew,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE,
                    db_instance=db if USE_DATABASE else None
                )
            elif strategy == "maker_hedge":
                # 永續合約對沖策略
                market_maker = MakerTakerHedgeStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    target_position=target_position,
                    max_position=max_position,
                    position_threshold=position_threshold,
                    inventory_skew=inventory_skew,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE,
                    market_type="perp"
                )
            else:
                # 永續合約標準策略
                market_maker = PerpetualMarketMaker(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    max_orders=max_orders,
                    target_position=target_position,
                    max_position=max_position,
                    position_threshold=position_threshold,
                    inventory_skew=inventory_skew,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE
                )
        else:
            if strategy == "grid":
                # 現貨網格策略
                market_maker = GridStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    grid_upper_price=grid_upper_price,
                    grid_lower_price=grid_lower_price,
                    grid_num=grid_num,
                    order_quantity=quantity,
                    auto_price_range=auto_price_range,
                    price_range_percent=price_range_percent,
                    grid_mode=grid_mode,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE,
                    db_instance=db if USE_DATABASE else None
                )
            elif strategy == "maker_hedge":
                # 現貨對沖策略
                market_maker = MakerTakerHedgeStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE,
                    market_type="spot"
                )
            else:
                # 現貨標準策略
                market_maker = MarketMaker(
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    max_orders=max_orders,
                    enable_rebalance=enable_rebalance,
                    base_asset_target_percentage=base_asset_target_percentage,
                    rebalance_threshold=rebalance_threshold,
                    exchange=exchange,
                    exchange_config=exchange_config,
                    enable_database=USE_DATABASE
                )

        market_maker.run(duration_seconds=duration, interval_seconds=interval)

    except Exception as e:
        print(f"做市過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def _get_running_instances() -> List[Dict[str, Any]]:
    """獲取所有運行中的實例及其配置信息
    
    Returns:
        包含實例信息的列表，每個實例包含 instance_id, symbol, web_port, config_file 等
    """
    registry = InstanceRegistry()
    running_instances = []
    
    # 從 InstanceRegistry 獲取運行中的實例
    instances = registry.list_instances(include_dead=False)
    
    for inst in instances:
        instance_info = {
            'instance_id': inst.get('instance_id', 'unknown'),
            'symbol': inst.get('symbol', 'N/A'),
            'web_port': inst.get('web_port'),
            'config_file': inst.get('config_file', ''),
            'strategy': inst.get('strategy', 'N/A'),
            'exchange': inst.get('exchange', 'N/A'),
            'is_alive': inst.get('is_alive', False),
        }
        
        # 如果沒有 web_port，嘗試從配置文件讀取
        if not instance_info['web_port'] and instance_info['config_file']:
            try:
                config_path = Path(instance_info['config_file'])
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        daemon_config = config.get('daemon_config', {})
                        instance_info['web_port'] = daemon_config.get('web_port')
                        
                        # 補充其他信息
                        metadata = config.get('metadata', {})
                        if not instance_info['symbol'] or instance_info['symbol'] == 'N/A':
                            instance_info['symbol'] = metadata.get('symbol', 'N/A')
                        if not instance_info['exchange'] or instance_info['exchange'] == 'N/A':
                            instance_info['exchange'] = metadata.get('exchange', 'N/A')
                        if not instance_info['strategy'] or instance_info['strategy'] == 'N/A':
                            instance_info['strategy'] = metadata.get('strategy', 'N/A')
            except Exception as e:
                logger.debug(f"讀取配置文件失敗: {e}")
        
        if instance_info['web_port']:
            running_instances.append(instance_info)
    
    # 如果 InstanceRegistry 沒有數據，嘗試從活躍配置文件中掃描
    if not running_instances:
        running_instances = _scan_active_configs_for_ports()
    
    return running_instances


def _scan_active_configs_for_ports() -> List[Dict[str, Any]]:
    """掃描活躍配置文件目錄，獲取可能運行的實例端口
    
    Returns:
        包含實例信息的列表
    """
    active_config_dir = Path("config/active")
    instances = []
    
    if not active_config_dir.exists():
        return instances
    
    for config_file in active_config_dir.glob("*.json"):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            daemon_config = config.get('daemon_config', {})
            metadata = config.get('metadata', {})
            web_port = daemon_config.get('web_port')
            
            if web_port:
                # 檢查端口是否有服務在運行
                is_running = _check_port_responsive(web_port)
                
                instances.append({
                    'instance_id': metadata.get('instance_id', config_file.stem),
                    'symbol': metadata.get('symbol', 'N/A'),
                    'web_port': web_port,
                    'config_file': str(config_file),
                    'strategy': metadata.get('strategy', 'N/A'),
                    'exchange': metadata.get('exchange', 'N/A'),
                    'is_alive': is_running,
                })
        except Exception as e:
            logger.debug(f"掃描配置文件 {config_file} 失敗: {e}")
    
    # 只返回正在運行的實例
    return [inst for inst in instances if inst.get('is_alive')]


def _check_port_responsive(port: int, host: str = '127.0.0.1', timeout: float = 2.0) -> bool:
    """檢查指定端口是否有響應的服務
    
    Args:
        port: 端口號
        host: 主機地址
        timeout: 超時時間
        
    Returns:
        端口是否有響應
    """
    try:
        response = requests.get(
            f"http://{host}:{port}/health",
            timeout=timeout
        )
        return response.status_code in (200, 503)  # 503 表示服務在運行但機器人未啟動
    except Exception:
        return False


def _display_running_instances(instances: List[Dict[str, Any]]) -> None:
    """顯示運行中的實例列表
    
    Args:
        instances: 實例信息列表
    """
    if not instances:
        print("\n📋 未發現運行中的實例")
        print("   提示: 請確保實例已啟動並配置了 Web 端口")
        return
    
    print(f"\n📋 運行中的實例 ({len(instances)} 個):")
    print("─" * 70)
    print(f"{'序號':<4} {'實例ID':<15} {'交易對':<18} {'端口':<6} {'策略':<12}")
    print("─" * 70)
    
    for i, inst in enumerate(instances, 1):
        instance_id = inst.get('instance_id', 'unknown')[:14]
        symbol = inst.get('symbol', 'N/A')[:17]
        web_port = inst.get('web_port', 'N/A')
        strategy = inst.get('strategy', 'N/A')[:11]
        
        print(f"{i:<4} {instance_id:<15} {symbol:<18} {web_port:<6} {strategy:<12}")
    
    print("─" * 70)


def _select_instance(instances: List[Dict[str, Any]]) -> Optional[str]:
    """讓用戶選擇要操作的實例
    
    Args:
        instances: 實例信息列表
        
    Returns:
        選中實例的 Web URL，如果取消則返回 None
    """
    if not instances:
        return None
    
    # 如果只有一個實例，自動選擇
    if len(instances) == 1:
        inst = instances[0]
        web_port = inst.get('web_port')
        instance_id = inst.get('instance_id', 'unknown')
        symbol = inst.get('symbol', 'N/A')
        
        print(f"\n🎯 自動選擇唯一運行的實例: {instance_id} ({symbol})")
        return f"http://127.0.0.1:{web_port}"
    
    # 多個實例，讓用戶選擇
    print("\n請選擇要調整的實例:")
    print("  輸入序號 (1, 2, ...) 選擇對應實例")
    print("  輸入實例ID (如 bp_sol_01) 直接選擇")
    print("  輸入完整地址 (如 http://127.0.0.1:5001) 直接使用")
    print("  按 Enter 取消操作")
    
    user_input = input("\n請選擇: ").strip()
    
    if not user_input:
        return None
    
    # 嘗試解析為序號
    try:
        index = int(user_input)
        if 1 <= index <= len(instances):
            inst = instances[index - 1]
            web_port = inst.get('web_port')
            return f"http://127.0.0.1:{web_port}"
        else:
            print(f"❌ 無效的序號，請輸入 1-{len(instances)} 之間的數字")
            return None
    except ValueError:
        pass
    
    # 嘗試匹配實例ID
    for inst in instances:
        if inst.get('instance_id', '').lower() == user_input.lower():
            web_port = inst.get('web_port')
            return f"http://127.0.0.1:{web_port}"
    
    # 檢查是否為完整URL
    if user_input.startswith('http://') or user_input.startswith('https://'):
        return user_input.rstrip('/')
    
    # 嘗試作為端口號處理
    try:
        port = int(user_input)
        if 1024 <= port <= 65535:
            return f"http://127.0.0.1:{port}"
    except ValueError:
        pass
    
    print(f"❌ 無法識別的輸入: {user_input}")
    print("   請輸入序號、實例ID、端口號或完整URL")
    return None


def grid_adjust_command():
    """透過 Web 控制端即時調整網格上下限
    
    改進功能:
    1. 自動發現運行中的實例
    2. 支持通過實例ID選擇
    3. 單實例時自動選擇
    """
    print("\n" + "=" * 50)
    print("        🔧 網格範圍調整工具")
    print("=" * 50)
    
    # 獲取運行中的實例
    instances = _get_running_instances()
    
    # 顯示實例列表
    _display_running_instances(instances)
    
    # 選擇實例
    base_url = _select_instance(instances)
    
    if base_url is None:
        # 如果沒有運行的實例或用戶取消，提供手動輸入選項
        if not instances:
            print("\n💡 您也可以手動輸入 Web 控制端地址")
        
        default_host = os.getenv('WEB_HOST', '127.0.0.1')
        default_port = os.getenv('WEB_PORT', '5000')
        default_base = os.getenv('WEB_API_BASE', f"http://127.0.0.1:{default_port}")
        
        base_url_input = input(f"\n請輸入 Web 控制端地址 (默認 {default_base}, 按 Enter 取消): ").strip()
        
        if not base_url_input:
            print("⚠️  操作已取消")
            return
        
        base_url = base_url_input
    
    base_url = base_url.rstrip('/')

    # URL 驗證
    validator = CliValidator()
    is_valid, errors = validator.validate({'base_url': base_url})
    
    if not is_valid:
        error_messages = []
        for field, field_errors in errors.items():
            error_messages.extend(field_errors)
        
        print(f"\n❌ 錯誤: {'; '.join(error_messages)}")
        print("\n📋 安全提示:")
        print("  只允許訪問本地或內網地址，例如:")
        print("    - http://127.0.0.1:5000")
        print("    - https://localhost:5000")
        print("    - http://192.168.1.100:5000")
        print("    - http://10.0.0.50:5000")
        print("  不允許訪問外部網址，防止 SSRF 攻擊")
        return

    print(f"\n📍 目標地址: {base_url}")
    
    # 嘗試獲取當前網格狀態
    try:
        status_response = requests.get(f"{base_url}/api/status", timeout=5)
        if status_response.ok:
            status = status_response.json()
            stats = status.get('stats', {})
            current_lower = stats.get('grid_lower_price')
            current_upper = stats.get('grid_upper_price')
            current_price = stats.get('current_price')
            
            if current_lower and current_upper:
                print(f"\n📊 當前網格狀態:")
                print(f"   網格範圍: {current_lower} ~ {current_upper}")
                if current_price:
                    print(f"   當前價格: {current_price}")
    except Exception:
        pass  # 獲取狀態失敗不影響主流程

    print("\n" + "-" * 50)
    lower_input = input("新的網格下限價格 (留空沿用當前設定): ").strip()
    upper_input = input("新的網格上限價格 (留空沿用當前設定): ").strip()

    # 構建請求負載
    payload = {}
    try:
        if lower_input:
            payload['grid_lower_price'] = float(lower_input)
        if upper_input:
            payload['grid_upper_price'] = float(upper_input)
    except ValueError:
        print("❌ 錯誤: 請輸入有效的數值。")
        return

    if not payload:
        print("⚠️  未輸入任何新範圍，操作已取消。")
        return

    endpoint = f"{base_url}/api/grid/adjust"
    print(f"\n🔄 正在向 {endpoint} 發送調整請求...")

    try:
        # 添加超時和驗證
        response = requests.post(
            endpoint,
            json=payload,
            timeout=15,
            headers={'Content-Type': 'application/json'}
        )
    except requests.exceptions.Timeout:
        print("❌ 錯誤: 請求超時，請檢查網絡連接或服務器狀態")
        return
    except requests.exceptions.ConnectionError:
        print("❌ 錯誤: 無法連接到服務器，請檢查地址是否正確")
        return
    except requests.RequestException as exc:
        print(f"❌ 錯誤: 發送請求失敗: {exc}")
        return

    try:
        result = response.json()
    except ValueError:
        print(f"❌ 錯誤: 服務端返回非JSON響應: {response.text}")
        return

    if response.ok and result.get('success'):
        lower = result.get('grid_lower_price')
        upper = result.get('grid_upper_price')
        print(f"\n✅ 網格範圍調整成功!")
        print(f"   新區間: {lower} ~ {upper}")
    else:
        message = result.get('message') if isinstance(result, dict) else response.text
        print(f"\n❌ 網格調整失敗: {message}")

def rebalance_settings_command():
    """重平設置管理命令"""
    print("\n=== 重平設置管理 ===")
    print("1 - 查看重平設置説明")
    print("2 - 測試重平設置")
    print("3 - 返回主菜單")
    
    choice = input("請選擇操作: ")
    
    if choice == '1':
        print("\n=== 重平設置説明 ===")
        print("重平功能用於保持資產配置的平衡，避免因市場波動導致的資產比例失衡。")
        print("\n主要參數:")
        print("1. 重平功能開關: 控制是否啟用自動重平衡")
        print("2. 基礎資產目標比例: 基礎資產應佔總資產的百分比 (0-100%)")
        print("3. 重平觸發閾值: 當實際比例偏離目標比例超過此閾值時觸發重平衡")
        print("\n範例:")
        print("- 目標比例 30%: 假設總資產價值 1000 USDC，則理想基礎資產價值為 300 USDC")
        print("- 觸發閾值 15%: 當偏差超過總資產的 15% 時觸發重平衡")
        print("- 如果基礎資產價值變為 450 USDC，偏差為 150 USDC (15%)，將觸發重平衡")
        print("\n注意事項:")
        print("- 重平衡會產生交易手續費")
        print("- 過低的閾值可能導致頻繁重平衡")
        print("- 過高的閾值可能無法及時控制風險")
        
    elif choice == '2':
        print("\n=== 測試重平設置 ===")
        enable_rebalance, base_asset_target_percentage, rebalance_threshold = configure_rebalance_settings()
        
        # 模擬計算示例
        if enable_rebalance:
            print(f"\n=== 模擬計算示例 ===")
            total_assets = 1000  # 假設總資產 1000 USDC
            ideal_base_value = total_assets * (base_asset_target_percentage / 100)
            quote_asset_target_percentage = 100 - base_asset_target_percentage
            
            print(f"假設總資產: {total_assets} USDC")
            print(f"理想基礎資產價值: {ideal_base_value} USDC ({base_asset_target_percentage}%)")
            print(f"理想報價資產價值: {total_assets - ideal_base_value} USDC ({quote_asset_target_percentage}%)")
            print(f"重平觸發閾值: {rebalance_threshold}% = {total_assets * (rebalance_threshold / 100)} USDC")
            
            # 示例偏差情況
            print(f"\n觸發重平衡的情況示例:")
            trigger_amount = total_assets * (rebalance_threshold / 100)
            high_threshold = ideal_base_value + trigger_amount
            low_threshold = ideal_base_value - trigger_amount
            
            print(f"- 當基礎資產價值 > {high_threshold:.2f} USDC 時，將賣出基礎資產")
            print(f"- 當基礎資產價值 < {low_threshold:.2f} USDC 時，將買入基礎資產")
            print(f"- 在 {low_threshold:.2f} - {high_threshold:.2f} USDC 範圍內不會觸發重平衡")
        
    elif choice == '3':
        return
    else:
        print("無效選擇")

def trading_stats_command(api_key, secret_key):
    """查看交易統計命令"""
    if not USE_DATABASE:
        print("資料庫功能已關閉，無法查詢交易統計。請啟用資料庫後再試。")
        return

    symbol = input("請輸入要查看統計的交易對 (例如: SOL_USDC): ")

    try:
        # 初始化數據庫
        db = Database()
        
        # 獲取今日統計
        today = datetime.now().strftime('%Y-%m-%d')
        today_stats = db.get_trading_stats(symbol, today)
        
        print("\n=== 做市商交易統計 ===")
        print(f"交易對: {symbol}")
        
        if today_stats and len(today_stats) > 0:
            stat = today_stats[0]
            maker_buy = stat['maker_buy_volume']
            maker_sell = stat['maker_sell_volume']
            taker_buy = stat['taker_buy_volume']
            taker_sell = stat['taker_sell_volume']
            profit = stat['realized_profit']
            fees = stat['total_fees']
            net = stat['net_profit']
            avg_spread = stat.get('avg_spread', 0)
            volatility = stat.get('volatility', 0)
            
            total_volume = maker_buy + maker_sell + taker_buy + taker_sell
            maker_percentage = ((maker_buy + maker_sell) / total_volume * 100) if total_volume > 0 else 0
            
            print(f"\n今日統計 ({today}):")
            print(f"總成交量: {total_volume}")
            print(f"Maker買入量: {maker_buy}")
            print(f"Maker賣出量: {maker_sell}")
            print(f"Taker買入量: {taker_buy}")
            print(f"Taker賣出量: {taker_sell}")
            print(f"Maker佔比: {maker_percentage:.2f}%")
            print(f"平均價差: {avg_spread:.4f}%")
            print(f"波動率: {volatility:.4f}%")
            print(f"毛利潤: {profit:.8f}")
            print(f"總手續費: {fees:.8f}")
            print(f"凈利潤: {net:.8f}")
        else:
            print(f"今日沒有 {symbol} 的交易記錄")
        
        # 獲取所有時間的統計
        all_time_stats = db.get_all_time_stats(symbol)
        
        if all_time_stats:
            maker_buy = all_time_stats['total_maker_buy']
            maker_sell = all_time_stats['total_maker_sell']
            taker_buy = all_time_stats['total_taker_buy']
            taker_sell = all_time_stats['total_taker_sell']
            profit = all_time_stats['total_profit']
            fees = all_time_stats['total_fees']
            net = all_time_stats['total_net_profit']
            avg_spread = all_time_stats.get('avg_spread_all_time', 0)
            
            total_volume = maker_buy + maker_sell + taker_buy + taker_sell
            maker_percentage = ((maker_buy + maker_sell) / total_volume * 100) if total_volume > 0 else 0
            
            print(f"\n累計統計:")
            print(f"總成交量: {total_volume}")
            print(f"Maker買入量: {maker_buy}")
            print(f"Maker賣出量: {maker_sell}")
            print(f"Taker買入量: {taker_buy}")
            print(f"Taker賣出量: {taker_sell}")
            print(f"Maker佔比: {maker_percentage:.2f}%")
            print(f"平均價差: {avg_spread:.4f}%")
            print(f"毛利潤: {profit:.8f}")
            print(f"總手續費: {fees:.8f}")
            print(f"凈利潤: {net:.8f}")
        else:
            print(f"沒有 {symbol} 的歷史交易記錄")
        
        # 獲取最近交易
        recent_trades = db.get_recent_trades(symbol, 10)
        
        if recent_trades and len(recent_trades) > 0:
            print("\n最近10筆成交:")
            for i, trade in enumerate(recent_trades):
                maker_str = "Maker" if trade['maker'] else "Taker"
                print(f"{i+1}. {trade['timestamp']} - {trade['side']} {trade['quantity']} @ {trade['price']} ({maker_str}) 手續費: {trade['fee']:.8f}")
        else:
            print(f"沒有 {symbol} 的最近成交記錄")
        
        # 關閉數據庫連接
        db.close()
        
    except Exception as e:
        print(f"查看交易統計時發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()


def toggle_database_command():
    """互動式切換資料庫寫入功能"""
    global USE_DATABASE

    status_text = "開啟" if USE_DATABASE else "關閉"
    print(f"當前資料庫寫入狀態: {status_text}")

    choice = input("是否要啟用資料庫寫入? (y=啟用, n=停用, Enter=維持原狀): ").strip().lower()

    if choice == "":
        print("設定未變更。")
        return

    if choice in ("y", "yes", "是"):
        if USE_DATABASE:
            print("資料庫寫入已經是開啟狀態。")
            return

        try:
            db = Database()
            db.close()
            USE_DATABASE = True
            print("已啟用資料庫寫入，後續操作將紀錄交易資訊。")
        except Exception as exc:
            print(f"啟用資料庫寫入失敗: {exc}")
            print("請確認資料庫設定後再嘗試。")
    elif choice in ("n", "no", "否"):
        if not USE_DATABASE:
            print("資料庫寫入已經是關閉狀態。")
        else:
            USE_DATABASE = False
            print("已停用資料庫寫入，僅保留記憶體內統計資料。")
    else:
        print("輸入無效，設定未變更。")


def market_analysis_command(api_key, secret_key):
    """市場分析命令"""
    symbol = input("請輸入要分析的交易對 (例如: SOL_USDC): ")
    try:
        print("\n執行市場分析...")

        # 創建臨時WebSocket連接
        ws = BackpackWebSocket(api_key, secret_key, symbol, auto_reconnect=True)
        ws.connect()
        
        # 等待連接建立
        wait_time = 0
        max_wait_time = 5
        while not ws.connected and wait_time < max_wait_time:
            time.sleep(0.5)
            wait_time += 0.5
        
        if not ws.connected:
            print("WebSocket連接超時，無法進行完整分析")
        else:
            # 初始化訂單簿
            ws.initialize_orderbook()
            
            # 訂閲必要數據流
            ws.subscribe_depth()
            ws.subscribe_bookTicker()
            
            # 等待數據更新
            print("等待數據更新...")
            time.sleep(3)
            
            # 獲取K線數據分析趨勢
            print("獲取歷史數據分析趨勢...")
            klines = _get_client().get_klines(symbol, "15m")

            # 添加調試信息查看數據結構
            print("K線數據結構: ")
            if isinstance(klines, dict) and "error" in klines:
                print(f"獲取K線數據出錯: {klines['error']}")
            else:
                print(f"收到 {len(klines) if isinstance(klines, list) else type(klines)} 條K線數據")
                
                # 檢查第一條記錄以確定結構
                if isinstance(klines, list) and len(klines) > 0:
                    print(f"第一條K線數據: {klines[0]}")
                    
                    # 根據實際結構提取收盤價
                    try:
                        if isinstance(klines[0], dict):
                            if 'close' in klines[0]:
                                # 如果是包含'close'字段的字典
                                prices = [float(kline['close']) for kline in klines]
                            elif 'c' in klines[0]:
                                # 另一種常見格式
                                prices = [float(kline['c']) for kline in klines]
                            else:
                                print(f"無法識別的字典K線格式，可用字段: {list(klines[0].keys())}")
                                raise ValueError("無法識別的K線數據格式")
                        elif isinstance(klines[0], list):
                            # 如果是列表格式，打印元素數量和數據樣例
                            print(f"K線列表格式，每條記錄有 {len(klines[0])} 個元素")
                            if len(klines[0]) >= 5:
                                # 通常第4或第5個元素是收盤價
                                try:
                                    # 嘗試第4個元素 (索引3)
                                    prices = [float(kline[3]) for kline in klines]
                                    print("使用索引3作為收盤價")
                                except (ValueError, IndexError):
                                    # 如果失敗，嘗試第5個元素 (索引4)
                                    prices = [float(kline[4]) for kline in klines]
                                    print("使用索引4作為收盤價")
                            else:
                                print("K線記錄元素數量不足")
                                raise ValueError("K線數據格式不兼容")
                        else:
                            print(f"未知的K線數據類型: {type(klines[0])}")
                            raise ValueError("未知的K線數據類型")
                        
                        # 計算移動平均
                        short_ma = sum(prices[-5:]) / 5 if len(prices) >= 5 else sum(prices) / len(prices)
                        medium_ma = sum(prices[-20:]) / 20 if len(prices) >= 20 else short_ma
                        long_ma = sum(prices[-50:]) / 50 if len(prices) >= 50 else medium_ma
                        
                        # 判斷趨勢
                        trend = "上漲" if short_ma > medium_ma > long_ma else "下跌" if short_ma < medium_ma < long_ma else "盤整"
                        
                        # 計算波動率
                        volatility = calculate_volatility(prices)
                        
                        print("\n市場趨勢分析:")
                        print(f"短期均價 (5週期): {short_ma:.6f}")
                        print(f"中期均價 (20週期): {medium_ma:.6f}")
                        print(f"長期均價 (50週期): {long_ma:.6f}")
                        print(f"當前趨勢: {trend}")
                        print(f"波動率: {volatility:.2f}%")
                        
                        # 獲取最新價格和波動性指標
                        current_price = ws.get_current_price()
                        liquidity_profile = ws.get_liquidity_profile()
                        
                        if current_price and liquidity_profile:
                            print(f"\n當前價格: {current_price}")
                            print(f"相對長期均價: {(current_price / long_ma - 1) * 100:.2f}%")
                            
                            # 流動性分析
                            buy_volume = liquidity_profile['bid_volume']
                            sell_volume = liquidity_profile['ask_volume']
                            imbalance = liquidity_profile['imbalance']
                            
                            print("\n市場流動性分析:")
                            print(f"買單量: {buy_volume:.4f}")
                            print(f"賣單量: {sell_volume:.4f}")
                            print(f"買賣比例: {(buy_volume/sell_volume):.2f}" if sell_volume > 0 else "買賣比例: 無限")
                            
                            # 判斷市場情緒
                            sentiment = "買方壓力較大" if imbalance > 0.2 else "賣方壓力較大" if imbalance < -0.2 else "買賣壓力平衡"
                            print(f"市場情緒: {sentiment} ({imbalance:.2f})")
                            
                            # 給出建議的做市參數
                            print("\n建議做市參數:")
                            
                            # 根據波動率調整價差
                            suggested_spread = max(0.2, min(2.0, volatility * 0.2))
                            print(f"建議價差: {suggested_spread:.2f}%")
                            
                            # 根據流動性調整訂單數量
                            liquidity_score = (buy_volume + sell_volume) / 2
                            orders_suggestion = 3
                            if liquidity_score > 10:
                                orders_suggestion = 5
                            elif liquidity_score < 1:
                                orders_suggestion = 2
                            print(f"建議訂單數: {orders_suggestion}")
                            
                            # 根據趨勢和情緒建議執行模式
                            if trend == "上漲" and imbalance > 0:
                                mode = "adaptive"
                                print("建議執行模式: 自適應模式 (跟隨上漲趨勢)")
                            elif trend == "下跌" and imbalance < 0:
                                mode = "passive"
                                print("建議執行模式: 被動模式 (降低下跌風險)")
                            else:
                                mode = "standard"
                                print("建議執行模式: 標準模式")
                            
                            # 建議重平設置
                            print("\n建議重平設置:")
                            if volatility > 5:
                                print("高波動率市場，建議:")
                                print("- 基礎資產比例: 20-25% (降低風險暴露)")
                                print("- 重平閾值: 10-12% (更頻繁重平衡)")
                            elif volatility > 2:
                                print("中等波動率市場，建議:")
                                print("- 基礎資產比例: 25-35% (標準配置)")
                                print("- 重平閾值: 12-18% (適中頻率)")
                            else:
                                print("低波動率市場，建議:")
                                print("- 基礎資產比例: 30-40% (可承受更高暴露)")
                                print("- 重平閾值: 15-25% (較少重平衡)")
                    except Exception as e:
                        print(f"處理K線數據時出錯: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("未收到有效的K線數據")
        
        # 關閉WebSocket連接
        if ws:
            ws.close()
            
    except Exception as e:
        print(f"市場分析時發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

def config_list_command():
    """列出所有配置文件"""
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        print("\n=== 配置文件列表 ===")
        
        # 列出模板文件
        templates = config_manager.list_templates()
        if templates:
            print("\n📋 模板文件:")
            for template in templates:
                print(f"  - {template}")
        else:
            print("\n📋 模板文件: 無")
        
        # 列出活躍配置
        active_configs = config_manager.list_active_configs()
        if active_configs:
            print("\n🟢 活躍配置:")
            for config in active_configs:
                print(f"  - {config}")
        else:
            print("\n🟢 活躍配置: 無")
        
        # 列出歸檔配置
        archived_configs = config_manager.list_archived_configs()
        if archived_configs:
            print("\n📦 歸檔配置:")
            for config in archived_configs:
                print(f"  - {config}")
        else:
            print("\n📦 歸檔配置: 無")
            
    except Exception as e:
        print(f"列出配置文件失敗: {str(e)}")

def config_create_command():
    """從模板創建新配置"""
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        print("\n=== 從模板創建配置 ===")
        
        # 列出可用模板
        templates = config_manager.list_templates()
        if not templates:
            print("沒有可用的模板文件")
            return
        
        print("\n可用模板:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template}")
        
        # 選擇模板
        while True:
            try:
                choice = input(f"\n請選擇模板 (1-{len(templates)}): ").strip()
                if not choice:
                    return
                
                template_index = int(choice) - 1
                if 0 <= template_index < len(templates):
                    selected_template = templates[template_index]
                    break
                else:
                    print("無效選擇，請重新輸入")
            except ValueError:
                print("請輸入有效數字")
        
        # 輸入配置參數
        print(f"\n使用模板: {selected_template}")
        print("請輸入配置參數:")
        
        params = {}
        
        # 基本參數
        params['exchange'] = input("交易所 (backpack/aster/paradex/lighter): ").strip().lower()
        params['symbol'] = input("交易對 (例如: SOL_USDC): ").strip().upper()
        params['market_type'] = input("市場類型 (spot/perp): ").strip().lower()
        params['strategy'] = input("策略 (standard/grid/maker_hedge): ").strip().lower()
        
        # API 密鑰
        print("\nAPI 密鑰配置 (留空使用環境變量):")
        api_key = input(f"{params['exchange'].upper()}_API_KEY: ").strip()
        secret_key = input(f"{params['exchange'].upper()}_SECRET_KEY: ").strip()
        
        if api_key:
            params['api_key'] = api_key
        if secret_key:
            params['secret_key'] = secret_key
        
        # 策略特定參數
        if params['strategy'] == 'grid':
            print("\n網格策略參數:")
            try:
                params['grid_upper'] = float(input("網格上限價格: ") or "0")
                params['grid_lower'] = float(input("網格下限價格: ") or "0")
                params['grid_num'] = int(input("網格數量: ") or "10")
                params['grid_mode'] = input("網格模式 (arithmetic/geometric): ").strip().lower() or "arithmetic"
                params['order_quantity'] = float(input("訂單數量: ") or "0")
            except ValueError:
                print("參數輸入錯誤，將使用默認值")
        
        # 創建配置
        config_name = f"{params['exchange']}_{params['symbol']}_{params['market_type']}_{params['strategy']}.json"
        
        try:
            config_path = config_manager.create_config_from_template(
                template_name=selected_template,
                output_name=config_name,
                **params
            )
            
            print(f"\n✅ 配置文件已創建: {config_path}")
            print(f"配置名稱: {config_name}")
            
            # 驗證配置
            validation_result = config_manager.validate_config_file(config_path)
            if validation_result.is_valid:
                print("✅ 配置驗證通過")
            else:
                print("⚠️ 配置驗證失敗:")
                for error in validation_result.errors:
                    print(f"  - {error}")
            
        except Exception as e:
            print(f"創建配置失敗: {str(e)}")
            
    except Exception as e:
        print(f"創建配置失敗: {str(e)}")

def config_validate_command():
    """驗證配置文件"""
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        print("\n=== 驗證配置文件 ===")
        
        # 選擇配置文件
        config_file = input("請輸入配置文件路徑或名稱: ").strip()
        if not config_file:
            print("未輸入配置文件")
            return
        
        # 如果只輸入文件名，嘗試在活躍配置目錄中查找
        if not os.path.exists(config_file):
            active_config_path = Path("config/active") / config_file
            if active_config_path.exists():
                config_file = str(active_config_path)
            else:
                print(f"配置文件不存在: {config_file}")
                return
        
        # 驗證配置
        validation_result = config_manager.validate_config_file(config_file)
        
        if validation_result.is_valid:
            print(f"✅ 配置文件驗證通過: {config_file}")
        else:
            print(f"❌ 配置文件驗證失敗: {config_file}")
            print("\n錯誤列表:")
            for error in validation_result.errors:
                print(f"  - {error}")
        
        if validation_result.warnings:
            print("\n警告列表:")
            for warning in validation_result.warnings:
                print(f"  - {warning}")
                
    except Exception as e:
        print(f"驗證配置文件失敗: {str(e)}")

def config_run_command():
    """使用指定配置運行交易機器人"""
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        print("\n=== 使用配置運行交易機器人 ===")
        
        # 選擇配置文件
        config_file = input("請輸入配置文件路徑或名稱: ").strip()
        if not config_file:
            print("未輸入配置文件")
            return
        
        # 如果只輸入文件名，嘗試在活躍配置目錄中查找
        if not os.path.exists(config_file):
            active_config_path = Path("config/active") / config_file
            if active_config_path.exists():
                config_file = str(active_config_path)
            else:
                print(f"配置文件不存在: {config_file}")
                return
        
        # 驗證配置
        validation_result = config_manager.validate_config_file(config_file)
        if not validation_result.is_valid:
            print("❌ 配置驗證失敗，無法運行")
            for error in validation_result.errors:
                print(f"  - {error}")
            return
        
        # 詢問是否以守護進程模式運行
        daemon_mode = input("是否以守護進程模式運行? (y/n，默認 y): ").strip().lower()
        daemon_mode = daemon_mode in ['', 'y', 'yes']
        
        print(f"\n🚀 使用配置文件啟動交易機器人: {config_file}")
        print(f"守護進程模式: {'開啟' if daemon_mode else '關閉'}")
        
        # 構建啟動命令
        import subprocess
        import sys
        
        cmd = [
            sys.executable,
            "core/daemon_manager.py",
            "start",
            "--config", config_file
        ]
        
        if daemon_mode:
            cmd.append("--daemon")
        
        print(f"\n執行命令: {' '.join(cmd)}")
        
        # 啟動進程
        try:
            result = subprocess.run(cmd, check=True)
            print("✅ 交易機器人已啟動")
        except subprocess.CalledProcessError as e:
            print(f"❌ 啟動失敗: {e}")
        except KeyboardInterrupt:
            print("\n⚠️ 用戶中斷啟動")
            
    except Exception as e:
        print(f"運行交易機器人失敗: {str(e)}")

def config_management_command():
    """配置管理主菜單"""
    while True:
        print("\n=== 配置管理 ===")
        print("1 - 列出所有配置文件")
        print("2 - 從模板創建新配置")
        print("3 - 驗證配置文件")
        print("4 - 使用配置運行交易機器人")
        print("5 - 高級配置管理")
        print("6 - 返回主菜單")
        
        choice = input("請選擇操作: ").strip()
        
        if choice == '1':
            config_list_command()
        elif choice == '2':
            config_create_command()
        elif choice == '3':
            config_validate_command()
        elif choice == '4':
            config_run_command()
        elif choice == '5':
            config_advanced_command()
        elif choice == '6':
            break
        else:
            print("無效選擇，請重新輸入")

def config_batch_validate_command():
    """批量驗證配置文件"""
    try:
        from core.config_manager import ConfigManager
        from core.exceptions import ConfigValidationError
        config_manager = ConfigManager()
        
        print("\n=== 批量驗證配置文件 ===")
        
        # 獲取所有配置文件
        all_configs = config_manager.list_configs()
        
        if not all_configs:
            print("沒有找到任何配置文件")
            return
        
        # 篩選選項
        print("選擇要驗證的配置類型:")
        print("1 - 所有配置文件")
        print("2 - 僅活躍配置")
        print("3 - 僅模板文件")
        print("4 - 僅歸檔配置")
        
        choice = input("請選擇 (1-4): ").strip()
        
        if choice == '1':
            configs_to_validate = all_configs
        elif choice == '2':
            configs_to_validate = [c for c in all_configs if c.is_active]
        elif choice == '3':
            configs_to_validate = [c for c in all_configs if c.is_template]
        elif choice == '4':
            configs_to_validate = [c for c in all_configs if c.is_archived]
        else:
            print("無效選擇")
            return
        
        print(f"\n開始驗證 {len(configs_to_validate)} 個配置文件...")
        
        valid_count = 0
        error_count = 0
        warning_count = 0
        
        for config_info in configs_to_validate:
            try:
                validation_result = config_manager.validate_config_file(config_info.path)
                
                if validation_result.is_valid:
                    print(f"✅ {config_info.name} - 驗證通過")
                    valid_count += 1
                else:
                    print(f"❌ {config_info.name} - 驗證失敗")
                    error_count += 1
                    for error in validation_result.errors:
                        print(f"    - {error}")
                
                if validation_result.warnings:
                    warning_count += len(validation_result.warnings)
                    for warning in validation_result.warnings:
                        print(f"    ⚠️ {warning}")
                        
            except ConfigValidationError as e:
                print(f"❌ {config_info.name} - 驗證異常: {e}")
                error_count += 1
            except Exception as e:
                print(f"❌ {config_info.name} - 未知錯誤: {e}")
                error_count += 1
        
        print(f"\n=== 驗證結果 ===")
        print(f"總計: {len(configs_to_validate)} 個配置文件")
        print(f"✅ 通過: {valid_count} 個")
        print(f"❌ 失敗: {error_count} 個")
        print(f"⚠️ 警告: {warning_count} 個")
        
        if error_count > 0:
            print(f"\n建議: 修復失敗的配置文件後重新驗證")
        
    except Exception as e:
        print(f"批量驗證失敗: {str(e)}")

def config_batch_backup_command():
    """批量備份配置文件"""
    try:
        from core.config_manager import ConfigManager
        from core.exceptions import ConfigBackupError
        config_manager = ConfigManager()
        
        print("\n=== 批量備份配置文件 ===")
        
        # 獲取活躍配置
        active_configs = config_manager.list_active_configs()
        
        if not active_configs:
            print("沒有找到活躍配置文件")
            return
        
        print(f"找到 {len(active_configs)} 個活躍配置文件")
        
        confirm = input(f"確定要備份所有活躍配置文件嗎? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("操作已取消")
            return
        
        print("\n開始批量備份...")
        
        success_count = 0
        error_count = 0
        
        for config_name in active_configs:
            config_path = config_manager.get_config_path(config_name.replace('.json', ''), 'active')
            
            try:
                backup_path = config_manager.backup_config(config_path)
                if backup_path:
                    print(f"✅ {config_name} -> {Path(backup_path).name}")
                    success_count += 1
                else:
                    print(f"❌ {config_name} - 備份失敗")
                    error_count += 1
            except ConfigBackupError as e:
                print(f"❌ {config_name} - 備份異常: {e}")
                error_count += 1
            except Exception as e:
                print(f"❌ {config_name} - 未知錯誤: {e}")
                error_count += 1
        
        print(f"\n=== 備份結果 ===")
        print(f"總計: {len(active_configs)} 個配置文件")
        print(f"✅ 成功: {success_count} 個")
        print(f"❌ 失敗: {error_count} 個")
        
        if error_count == 0:
            print("\n🎉 所有配置文件備份成功!")
        else:
            print(f"\n⚠️ 有 {error_count} 個配置文件備份失敗，請檢查日誌")
        
    except Exception as e:
        print(f"批量備份失敗: {str(e)}")

def config_batch_cleanup_command():
    """批量清理舊備份文件"""
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        
        print("\n=== 批量清理舊備份文件 ===")
        
        # 獲取歸檔配置
        archived_configs = config_manager.list_archived_configs()
        
        if not archived_configs:
            print("沒有找到歸檔配置文件")
            return
        
        # 篩選備份文件
        backup_files = [f for f in archived_configs if '_backup_' in f]
        
        if not backup_files:
            print("沒有找到備份文件")
            return
        
        print(f"找到 {len(backup_files)} 個備份文件:")
        for backup_file in backup_files[:10]:  # 只顯示前10個
            print(f"  - {backup_file}")
        
        if len(backup_files) > 10:
            print(f"  ... 還有 {len(backup_files) - 10} 個文件")
        
        # 詢問保留天數
        days_input = input("請輸入要保留的天數 (默認 7 天): ").strip()
        try:
            keep_days = int(days_input) if days_input else 7
        except ValueError:
            print("無效的天數，使用默認值 7 天")
            keep_days = 7
        
        # 計算截止日期
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        print(f"\n將刪除 {keep_days} 天前的備份文件 (早於 {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")
        
        confirm = input("確定要繼續嗎? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("操作已取消")
            return
        
        print("\n開始清理...")
        
        deleted_count = 0
        error_count = 0
        
        for backup_file in backup_files:
            backup_path = config_manager.get_config_path(backup_file.replace('.json', ''), 'archived')
            
            try:
                # 獲取文件修改時間
                file_mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    backup_path.unlink()
                    print(f"🗑️ 已刪除: {backup_file}")
                    deleted_count += 1
                    
            except Exception as e:
                print(f"❌ 刪除失敗 {backup_file}: {e}")
                error_count += 1
        
        print(f"\n=== 清理結果 ===")
        print(f"🗑️ 已刪除: {deleted_count} 個文件")
        print(f"❌ 刪除失敗: {error_count} 個文件")
        
        if deleted_count > 0:
            print(f"\n✨ 清理完成，釋放了磁盤空間")
        
    except Exception as e:
        print(f"批量清理失敗: {str(e)}")

def config_advanced_command():
    """高級配置管理命令"""
    while True:
        print("\n=== 高級配置管理 ===")
        print("1 - 批量驗證配置文件")
        print("2 - 批量備份配置文件")
        print("3 - 批量清理舊備份")
        print("4 - 返回配置管理主菜單")
        
        choice = input("請選擇操作: ").strip()
        
        if choice == '1':
            config_batch_validate_command()
        elif choice == '2':
            config_batch_backup_command()
        elif choice == '3':
            config_batch_cleanup_command()
        elif choice == '4':
            break
        else:
            print("無效選擇，請重新輸入")

def main_cli(api_key=API_KEY, secret_key=SECRET_KEY, enable_database=ENABLE_DATABASE, exchange='backpack'):
    """主CLI函數"""
    global USE_DATABASE
    USE_DATABASE = bool(enable_database)

    if not USE_DATABASE:
        print("提示: 資料庫寫入功能已關閉，統計與歷史查詢功能將不可用。")

    # 顯示當前交易所
    exchange_display = {
        'backpack': 'Backpack',
        'aster': 'Aster',
        'paradex': 'Paradex',
        'lighter': 'Lighter',
        'apex': 'APEX',
    }.get(exchange.lower(), 'Backpack')

    while True:
        print(f"\n===== 量化交易程序 =====")
        print("1 - 查詢存款地址")
        print("2 - 查詢餘額")
        print("3 - 獲取市場信息")
        print("4 - 獲取訂單簿")
        print("5 - 執行現貨/合約做市/對沖/網格 策略")
        print("6 - 調整運行中網格範圍（需 Web 控制端）")
        stats_label = "7 - 交易統計報表" if USE_DATABASE else "7 - 交易統計報表 (已停用)"
        print(stats_label)
        print("8 - 市場分析")
        print("9 - 重平設置管理")
        db_status = "開啟" if USE_DATABASE else "關閉"
        print(f"10 - 切換資料庫寫入 (目前: {db_status})")
        print("11 - 配置管理")
        print("12 - 退出程序")

        operation = input("請輸入操作類型: ")

        if operation == '1':
            get_address_command(api_key, secret_key)
        elif operation == '2':
            get_balance_command(api_key, secret_key)
        elif operation == '3':
            get_markets_command()
        elif operation == '4':
            get_orderbook_command(api_key, secret_key)
        elif operation == '5':
            run_market_maker_command(api_key, secret_key)
        elif operation == '6':
            grid_adjust_command()
        elif operation == '7':
            trading_stats_command(api_key, secret_key)
        elif operation == '8':
            market_analysis_command(api_key, secret_key)
        elif operation == '9':
            rebalance_settings_command()
        elif operation == '10' or operation.lower() == 'd':
            toggle_database_command()
        elif operation == '11':
            config_management_command()
        elif operation == '12':
            print("退出程序。")
            break
        else:
            print("輸入錯誤，請重新輸入。")
