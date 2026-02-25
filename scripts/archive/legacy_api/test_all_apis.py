#!/usr/bin/env python3
"""
============================================================
API 完整测试脚本
============================================================
测试所有 12 个 API 端点，验证返回格式和数据正确性

用法:
    python3 scripts/test_all_apis.py

前提:
    1. 服务已启动: python3 main.py
    2. InfluxDB 运行中: http://localhost:8086/health
============================================================
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

# 配置
BASE_URL = "http://localhost:8080"

# 颜色输出
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"{BLUE}{title}{RESET}")
    print('='*60)


def print_result(name: str, success: bool, detail: str = ""):
    """打印测试结果"""
    status = f"{GREEN}✅ PASS{RESET}" if success else f"{RED}❌ FAIL{RESET}"
    print(f"{status} {name}")
    if detail:
        print(f"       {YELLOW}{detail}{RESET}")


def test_api(method: str, url: str, expected_success: bool = True) -> Tuple[bool, Dict[str, Any]]:
    """测试单个API
    
    Returns:
        (测试是否通过, 响应数据)
    """
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.request(method, url, timeout=10)
        
        data = resp.json()
        
        # 检查响应格式
        if "success" not in data:
            return False, {"error": "响应缺少 success 字段"}
        
        if data.get("success") == expected_success:
            return True, data
        else:
            return False, data
            
    except requests.exceptions.ConnectionError:
        return False, {"error": "连接失败，请确认服务已启动"}
    except Exception as e:
        return False, {"error": str(e)}


def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}   陶瓷车间后端 API 测试{RESET}")
    print(f"{BLUE}   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    results = []
    
    # ============================================================
    # 1. 健康检查 APIs
    # ============================================================
    print_header("1. 健康检查 APIs")
    
    # 1.1 系统健康
    passed, data = test_api("GET", f"{BASE_URL}/api/health")
    results.append(passed)
    print_result("GET /api/health", passed, 
                 f"status={data.get('data', {}).get('status', 'N/A')}" if passed else data.get('error', ''))
    
    # 1.2 PLC 状态
    passed, data = test_api("GET", f"{BASE_URL}/api/health/plc")
    results.append(passed)
    print_result("GET /api/health/plc", passed,
                 f"connected={data.get('data', {}).get('connected', 'N/A')}" if passed else data.get('error', ''))
    
    # 1.3 数据库状态
    passed, data = test_api("GET", f"{BASE_URL}/api/health/database")
    results.append(passed)
    print_result("GET /api/health/database", passed,
                 f"connected={data.get('data', {}).get('connected', 'N/A')}" if passed else data.get('error', ''))
    
    # ============================================================
    # 2. 设备列表 APIs
    # ============================================================
    print_header("2. 设备列表 APIs")
    
    # 2.1 所有设备
    passed, data = test_api("GET", f"{BASE_URL}/api/devices")
    results.append(passed)
    device_count = len(data.get('data', [])) if passed else 0
    print_result("GET /api/devices", passed,
                 f"返回 {device_count} 个设备" if passed else data.get('error', ''))
    
    # 2.2 按类型筛选
    passed, data = test_api("GET", f"{BASE_URL}/api/devices?device_type=short_hopper")
    results.append(passed)
    short_count = len(data.get('data', [])) if passed else 0
    print_result("GET /api/devices?device_type=short_hopper", passed,
                 f"返回 {short_count} 个短料仓" if passed else data.get('error', ''))
    
    # 2.3 按 DB 块查询
    passed, data = test_api("GET", f"{BASE_URL}/api/db/6/devices")
    results.append(passed)
    db6_count = len(data.get('data', [])) if passed else 0
    print_result("GET /api/db/6/devices", passed,
                 f"返回 {db6_count} 个 DB6 设备" if passed else data.get('error', ''))
    
    # ============================================================
    # 3. 设备实时数据 API
    # ============================================================
    print_header("3. 设备实时数据 API")
    
    # 3.1 查询实时数据
    passed, data = test_api("GET", f"{BASE_URL}/api/devices/short_hopper_1/realtime")
    results.append(passed)
    if passed:
        device_data = data.get('data', {})
        module_count = len(device_data.get('modules', {}))
        print_result("GET /api/devices/short_hopper_1/realtime", passed,
                     f"返回 {module_count} 个模块数据")
    else:
        print_result("GET /api/devices/short_hopper_1/realtime", passed, data.get('error', ''))
    
    # ============================================================
    # 4. 设备历史数据 APIs
    # ============================================================
    print_header("4. 设备历史数据 APIs")
    
    # 时间范围: 最近30天
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")
    interval = "5m"  # 5分钟聚合
    
    # 4.1 历史数据 (核心接口)
    url = f"{BASE_URL}/api/devices/short_hopper_1/history?start={start_str}&end={end_str}&interval={interval}"
    passed, data = test_api("GET", url)
    results.append(passed)
    record_count = len(data.get('data', [])) if passed and isinstance(data.get('data'), list) else 0
    print_result("GET /api/devices/{id}/history", passed,
                 f"返回 {record_count} 条记录 (30天, 5分钟聚合)" if passed else data.get('error', ''))
    
    # 4.2 温度历史
    url = f"{BASE_URL}/api/devices/short_hopper_1/temperature?start={start_str}&end={end_str}&interval={interval}"
    passed, data = test_api("GET", url)
    results.append(passed)
    record_count = len(data.get('data', [])) if passed and isinstance(data.get('data'), list) else 0
    print_result("GET /api/devices/{id}/temperature", passed,
                 f"返回 {record_count} 条温度记录 (30天, 5分钟聚合)" if passed else data.get('error', ''))
    
    # 4.3 功率历史
    url = f"{BASE_URL}/api/devices/short_hopper_1/power?start={start_str}&end={end_str}&interval={interval}"
    passed, data = test_api("GET", url)
    results.append(passed)
    record_count = len(data.get('data', [])) if passed and isinstance(data.get('data'), list) else 0
    print_result("GET /api/devices/{id}/power", passed,
                 f"返回 {record_count} 条功率记录 (30天, 5分钟聚合)" if passed else data.get('error', ''))
    
    # 4.4 称重历史
    url = f"{BASE_URL}/api/devices/short_hopper_1/weight?start={start_str}&end={end_str}&interval={interval}"
    passed, data = test_api("GET", url)
    results.append(passed)
    record_count = len(data.get('data', [])) if passed and isinstance(data.get('data'), list) else 0
    print_result("GET /api/devices/{id}/weight", passed,
                 f"返回 {record_count} 条称重记录 (30天, 5分钟聚合)" if passed else data.get('error', ''))
    
    # ============================================================
    # 5. 多设备对比 API
    # ============================================================
    print_header("5. 多设备对比 API")
    
    url = (f"{BASE_URL}/api/devices/compare"
           f"?device_ids=short_hopper_1,short_hopper_2"
           f"&field=Temperature"
           f"&start={start_str}&end={end_str}"
           f"&interval={interval}")
    passed, data = test_api("GET", url)
    results.append(passed)
    record_count = len(data.get('data', [])) if passed and isinstance(data.get('data'), list) else 0
    print_result("GET /api/devices/compare", passed,
                 f"返回 {record_count} 条对比记录 (30天, 5分钟聚合)" if passed else data.get('error', ''))
    
    # ============================================================
    # 测试汇总
    # ============================================================
    print_header("测试汇总")
    
    total = len(results)
    passed_count = sum(results)
    failed_count = total - passed_count
    
    print(f"总计: {total} 个测试")
    print(f"{GREEN}通过: {passed_count}{RESET}")
    print(f"{RED}失败: {failed_count}{RESET}")
    
    if failed_count == 0:
        print(f"\n{GREEN}🎉 所有 API 测试通过！{RESET}")
        return 0
    else:
        print(f"\n{RED} 有 {failed_count} 个测试失败{RESET}")
        return 1


if __name__ == "__main__":
    exit(main())
