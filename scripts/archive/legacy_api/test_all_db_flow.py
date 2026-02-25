#!/usr/bin/env python3
"""
完整数据流测试 - 一键测试所有 DB 块
流程: 原始字节 → 解析 → 转换 → 存储 → API验证

使用方法:
1. 先启动服务: python3 main.py
2. 再运行测试: python3 scripts/test_all_db_flow.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入各DB块测试模块
from tests.integration.test_db8_full_flow import (
    generate_db8_test_data,
    parse_db8_data,
    convert_and_write as convert_db8
)
from tests.integration.test_db9_full_flow import (
    generate_db9_test_data,
    parse_db9_data,
    convert_and_write as convert_db9
)
from tests.integration.test_db10_full_flow import (
    generate_db10_test_data,
    parse_db10_data,
    convert_and_write as convert_db10
)

import httpx

API_BASE = "http://localhost:8080"


async def verify_all_apis():
    """验证所有 API 端点"""
    print("\n" + "=" * 70)
    print("🔍 API 验证")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        api_tests = [
            # 健康检查
            ("GET", "/api/health", None, "健康检查"),
            
            # 料仓 API
            ("GET", "/api/hopper/list", None, "料仓列表"),
            ("GET", "/api/hopper/short_hopper_1", None, "短料仓1实时"),
            ("GET", "/api/hopper/long_hopper_1", None, "长料仓1实时"),
            
            # 辊道窑 API
            ("GET", "/api/roller/info", None, "辊道窑信息"),
            ("GET", "/api/roller/realtime", None, "辊道窑实时"),
            ("GET", "/api/roller/zone/zone1", None, "温区1数据"),
            
            # SCR API
            ("GET", "/api/scr/list", None, "SCR列表"),
            ("GET", "/api/scr/scr_1", None, "SCR_1实时"),
            
            # 风机 API
            ("GET", "/api/fan/list", None, "风机列表"),
            ("GET", "/api/fan/fan_1", None, "风机1实时"),
        ]
        
        success_count = 0
        fail_count = 0
        
        for method, path, params, desc in api_tests:
            try:
                if method == "GET":
                    resp = await client.get(f"{API_BASE}{path}", params=params)
                else:
                    resp = await client.post(f"{API_BASE}{path}", json=params)
                
                data = resp.json()
                
                if data.get('success') or resp.status_code == 200:
                    print(f"   ✅ {desc}: {path}")
                    success_count += 1
                else:
                    print(f"   ❌ {desc}: {path} - {data.get('error', 'Unknown error')}")
                    fail_count += 1
                    
            except Exception as e:
                print(f"   ❌ {desc}: {path} - {e}")
                fail_count += 1
        
        print(f"\n   📊 结果: {success_count} 成功, {fail_count} 失败")
        return success_count, fail_count


def main():
    print("=" * 70)
    print("🚀 完整数据流测试 - 一键测试所有 DB 块")
    print("=" * 70)
    print("流程: 原始字节 → 解析 → 转换 → 存储 → API验证")
    print("=" * 70)
    
    total_writes = 0
    
    # ============================================================
    # DB8 料仓测试
    # ============================================================
    print("\n" + "=" * 70)
    print("📦 DB8 料仓测试 (9个设备)")
    print("=" * 70)
    
    raw_db8 = generate_db8_test_data()
    devices_db8 = parse_db8_data(raw_db8)
    writes = convert_db8(devices_db8, db_number=8)
    total_writes += writes
    
    # ============================================================
    # DB9 辊道窑测试
    # ============================================================
    print("\n" + "=" * 70)
    print("🔥 DB9 辊道窑测试 (1个设备, 6温区)")
    print("=" * 70)
    
    raw_db9 = generate_db9_test_data()
    devices_db9 = parse_db9_data(raw_db9)
    writes = convert_db9(devices_db9, db_number=9)
    total_writes += writes
    
    # ============================================================
    # DB10 SCR/风机测试
    # ============================================================
    print("\n" + "=" * 70)
    print("💨 DB10 SCR/风机测试 (4个设备)")
    print("=" * 70)
    
    raw_db10 = generate_db10_test_data()
    devices_db10 = parse_db10_data(raw_db10)
    writes = convert_db10(devices_db10, db_number=10)
    total_writes += writes
    
    # ============================================================
    # 汇总
    # ============================================================
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    print(f"   DB8 料仓:   {len(devices_db8)} 个设备")
    print(f"   DB9 辊道窑: {len(devices_db9)} 个设备")
    print(f"   DB10 SCR/风机: {len(devices_db10)} 个设备")
    print(f"   总计写入:  {total_writes} 条记录")
    
    # ============================================================
    # API 验证 (需要服务运行)
    # ============================================================
    print("\n🔍 验证 API (需要 main.py 运行中)...")
    try:
        success, fail = asyncio.run(verify_all_apis())
        
        if fail == 0:
            print("\n" + "=" * 70)
            print("🎉 全部测试通过!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print(f"  部分测试失败 ({fail} 个)")
            print("=" * 70)
            
    except Exception as e:
        print(f"\n     API 验证跳过 (服务未运行): {e}")
        print("   提示: 请先运行 python3 main.py 启动服务")
    
    print("\n✅ 测试完成!")


if __name__ == "__main__":
    main()
