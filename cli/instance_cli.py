#!/usr/bin/env python3
"""
實例管理命令行工具
提供查看、清理、驗證實例的命令行界面
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.instance_manager import InstanceRegistry, InstanceManager


def format_timestamp(timestamp_str: str) -> str:
    """格式化時間戳"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str


def list_instances_cmd(args):
    """列出所有實例"""
    registry = InstanceRegistry()
    instances = registry.list_instances(include_dead=args.all)

    if not instances:
        print("沒有實例記錄")
        return

    print(f"\n{'=' * 140}")
    print(f"{'實例ID':<20} {'狀態':<12} {'PID':<10} {'Web端口':<10} {'配置文件':<40} {'啟動時間':<25}")
    print(f"{'=' * 140}")

    for inst in instances:
        status = "🟢 運行中" if inst['is_alive'] else "🔴 已停止"
        instance_id = inst.get('instance_id', 'N/A')
        pid = inst.get('pid', 'N/A')
        web_port = inst.get('web_port', 'N/A')
        config_file = inst.get('config_file', 'N/A')

        # 縮短配置文件路徑
        if len(str(config_file)) > 40:
            config_file = '...' + str(config_file)[-37:]

        started_at = format_timestamp(inst.get('started_at', 'N/A'))

        print(f"{instance_id:<20} {status:<12} {pid:<10} {web_port:<10} {str(config_file):<40} {started_at:<25}")

    print(f"{'=' * 140}")

    running_count = sum(1 for inst in instances if inst['is_alive'])
    total_count = len(instances)

    if args.all:
        print(f"\n總計: {total_count} 個實例 (運行中: {running_count}, 已停止: {total_count - running_count})")
    else:
        print(f"\n總計: {running_count} 個運行中的實例")

    print()


def cleanup_instances_cmd(args):
    """清理已停止的實例記錄"""
    registry = InstanceRegistry()

    # 先列出將要清理的實例
    instances = registry.list_instances(include_dead=True)
    dead_instances = [inst for inst in instances if not inst['is_alive']]

    if not dead_instances:
        print("沒有需要清理的已停止實例")
        return

    print(f"\n發現 {len(dead_instances)} 個已停止的實例:")
    for inst in dead_instances:
        print(f"  - {inst['instance_id']} (PID: {inst.get('pid', 'N/A')})")

    if not args.force:
        confirm = input("\n確認清理這些實例記錄? (y/N): ")
        if confirm.lower() != 'y':
            print("已取消")
            return

    count = registry.cleanup_dead_instances()
    print(f"\n✅ 已清理 {count} 個已停止的實例記錄")


def stats_cmd(args):
    """顯示實例統計信息"""
    manager = InstanceManager()

    if args.instance_id:
        # 顯示特定實例的統計
        stats = manager.get_instance_stats(args.instance_id)
        if not stats:
            print(f"❌ 實例 {args.instance_id} 不存在")
            return

        print(f"\n{'=' * 80}")
        print(f"實例統計: {args.instance_id}")
        print(f"{'=' * 80}")

        status = "🟢 運行中" if stats['is_alive'] else "🔴 已停止"
        print(f"狀態:       {status}")
        print(f"PID:        {stats.get('pid', 'N/A')}")
        print(f"Web端口:    {stats.get('web_port', 'N/A')}")
        print(f"配置文件:   {stats.get('config_file', 'N/A')}")
        print(f"日誌目錄:   {stats.get('log_dir', 'N/A')}")
        print(f"啟動時間:   {format_timestamp(stats.get('started_at', 'N/A'))}")

        if 'process_info' in stats:
            proc = stats['process_info']
            print(f"\n進程信息:")
            print(f"  進程名:   {proc.get('name', 'N/A')}")
            print(f"  狀態:     {proc.get('status', 'N/A')}")
            print(f"  CPU:      {proc.get('cpu_percent', 0):.1f}%")
            print(f"  內存:     {proc.get('memory_mb', 0):.1f} MB")
            print(f"  線程數:   {proc.get('num_threads', 0)}")
            print(f"  創建時間: {format_timestamp(proc.get('create_time', 'N/A'))}")

        print(f"{'=' * 80}\n")

    else:
        # 顯示所有實例的簡要統計
        all_stats = manager.get_all_stats()

        if not all_stats:
            print("沒有實例記錄")
            return

        print(f"\n{'=' * 120}")
        print(f"{'實例ID':<20} {'狀態':<12} {'PID':<10} {'CPU':<8} {'內存(MB)':<12} {'線程數':<10} {'啟動時間':<25}")
        print(f"{'=' * 120}")

        for stats in all_stats:
            status = "🟢 運行中" if stats['is_alive'] else "🔴 已停止"
            instance_id = stats.get('instance_id', 'N/A')
            pid = stats.get('pid', 'N/A')
            started_at = format_timestamp(stats.get('started_at', 'N/A'))

            if 'process_info' in stats:
                proc = stats['process_info']
                cpu = f"{proc.get('cpu_percent', 0):.1f}%"
                memory = f"{proc.get('memory_mb', 0):.1f}"
                threads = proc.get('num_threads', 'N/A')
            else:
                cpu = 'N/A'
                memory = 'N/A'
                threads = 'N/A'

            print(f"{instance_id:<20} {status:<12} {pid:<10} {cpu:<8} {memory:<12} {str(threads):<10} {started_at:<25}")

        print(f"{'=' * 120}")

        running_count = sum(1 for s in all_stats if s['is_alive'])
        print(f"\n總計: {len(all_stats)} 個實例 (運行中: {running_count}, 已停止: {len(all_stats) - running_count})")
        print()


def validate_cmd(args):
    """驗證實例配置"""
    manager = InstanceManager()

    if args.instance_id:
        # 驗證特定實例
        result = manager.validate_instance_config(args.instance_id)

        print(f"\n{'=' * 80}")
        print(f"驗證實例: {args.instance_id}")
        print(f"{'=' * 80}")

        if result['valid']:
            print("✅ 配置驗證通過")
        else:
            print("❌ 配置驗證失敗")

        if result['errors']:
            print("\n錯誤:")
            for error in result['errors']:
                print(f"  - {error}")

        if result['warnings']:
            print("\n警告:")
            for warning in result['warnings']:
                print(f"  - {warning}")

        print(f"{'=' * 80}\n")

    else:
        # 驗證所有實例
        registry = InstanceRegistry()
        instances = registry.list_instances(include_dead=True)

        if not instances:
            print("沒有實例記錄")
            return

        print(f"\n{'=' * 80}")
        print("驗證所有實例配置")
        print(f"{'=' * 80}\n")

        valid_count = 0
        invalid_count = 0

        for inst in instances:
            instance_id = inst.get('instance_id')
            result = manager.validate_instance_config(instance_id)

            if result['valid']:
                status = "✅"
                valid_count += 1
            else:
                status = "❌"
                invalid_count += 1

            print(f"{status} {instance_id}")

            if result['errors']:
                for error in result['errors']:
                    print(f"   錯誤: {error}")

            if result['warnings'] and args.verbose:
                for warning in result['warnings']:
                    print(f"   警告: {warning}")

        print(f"\n{'=' * 80}")
        print(f"總計: {len(instances)} 個實例 (有效: {valid_count}, 無效: {invalid_count})")
        print(f"{'=' * 80}\n")


def info_cmd(args):
    """顯示實例詳細信息"""
    registry = InstanceRegistry()
    info = registry.get(args.instance_id)

    if not info:
        print(f"❌ 實例 {args.instance_id} 不存在")
        return

    print(f"\n{'=' * 80}")
    print(f"實例信息: {args.instance_id}")
    print(f"{'=' * 80}\n")

    # 顯示所有字段
    for key, value in sorted(info.items()):
        if key in ['started_at', 'registered_at', 'last_updated']:
            value = format_timestamp(value)
        print(f"{key:<20}: {value}")

    print(f"\n{'=' * 80}\n")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='實例管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 列出所有運行中的實例
  python cli/instance_cli.py list

  # 列出所有實例（包括已停止的）
  python cli/instance_cli.py list --all

  # 顯示統計信息
  python cli/instance_cli.py stats

  # 顯示特定實例的統計信息
  python cli/instance_cli.py stats --instance-id bp_sol_01

  # 驗證所有實例配置
  python cli/instance_cli.py validate

  # 清理已停止的實例記錄
  python cli/instance_cli.py cleanup

  # 顯示實例詳細信息
  python cli/instance_cli.py info bp_sol_01
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有實例')
    list_parser.add_argument('--all', '-a', action='store_true',
                           help='包括已停止的實例')

    # cleanup 命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理已停止的實例記錄')
    cleanup_parser.add_argument('--force', '-f', action='store_true',
                              help='不詢問直接清理')

    # stats 命令
    stats_parser = subparsers.add_parser('stats', help='顯示實例統計信息')
    stats_parser.add_argument('--instance-id', '-i', help='實例ID（可選，不指定則顯示所有）')

    # validate 命令
    validate_parser = subparsers.add_parser('validate', help='驗證實例配置')
    validate_parser.add_argument('--instance-id', '-i', help='實例ID（可選，不指定則驗證所有）')
    validate_parser.add_argument('--verbose', '-v', action='store_true', help='顯示詳細信息')

    # info 命令
    info_parser = subparsers.add_parser('info', help='顯示實例詳細信息')
    info_parser.add_argument('instance_id', help='實例ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == 'list':
            list_instances_cmd(args)
        elif args.command == 'cleanup':
            cleanup_instances_cmd(args)
        elif args.command == 'stats':
            stats_cmd(args)
        elif args.command == 'validate':
            validate_cmd(args)
        elif args.command == 'info':
            info_cmd(args)
        else:
            parser.print_help()

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
