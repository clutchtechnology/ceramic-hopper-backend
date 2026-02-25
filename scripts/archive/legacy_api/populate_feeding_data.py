
import sys
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict

# 添加项目根目录到 pythonpath
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from config import get_settings
from app.core.influxdb import get_influx_client
from app.services.history_query_service import get_history_service

def populate_feeding_data():
    """
    根据最近3天的称重历史数据，计算并填充投料记录(feeding_records)
    """
    print("🚀 开始生成投料历史数据...")
    
    settings = get_settings()
    client = get_influx_client()
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = settings.influx_bucket
    
    # 1. 获取所有料仓设备列表
    # (这里硬编码或者从配置读取，为简单起见列出主要料仓)
    devices = [
        "short_hopper_1", "short_hopper_2", "short_hopper_3", "short_hopper_4",
        "no_hopper_1", "no_hopper_2",
        "long_hopper_1", "long_hopper_2", "long_hopper_3"
    ]
    
    total_records = 0
    
    for device_id in devices:
        print(f"\n📦 处理设备: {device_id}")
        
        # 2. 查询最近3天的重量数据
        # 仅查询 weight 字段 (Raw Weight)
        query = f'''
        from(bucket: "{bucket}")
            |> range(start: -3d)
            |> filter(fn: (r) => r["_measurement"] == "sensor_data")
            |> filter(fn: (r) => r["device_id"] == "{device_id}")
            |> filter(fn: (r) => r["_field"] == "weight")
            |> sort(columns: ["_time"], desc: false)
        '''
        
        try:
            result = query_api.query(query)
            
            points = []
            for table in result:
                for record in table.records:
                    points.append({
                        "time": record.get_time(),
                        "value": float(record.get_value())
                    })
            
            if not points:
                print(f"    无历史重量数据，跳过")
                continue
                
            print(f"   📊 找到 {len(points)} 条重量记录，正在分析投料事件...")
            
            # 3. 分析投料事件 (检测重量上升沿)
            # 逻辑说明:
            # - 监控重量变化趋势
            # - 当 detecting (当前值 - 上一次值) > 敏感阈值 (5kg) 时
            # - 判定为一次"投料行为"
            # - 记录增加的重量量 delta_weight
            
            feeding_events = []
            threshold_kg = 10.0 # 阈值: 5kg (过滤抖动)
            
            prev_val = points[0]["value"]
            prev_time = points[0]["time"]
            
            total_added_weight = 0.0 # 该设备总投料量
            
            for i in range(1, len(points)):
                curr = points[i]
                curr_val = curr["value"]
                curr_time = curr["time"]
                
                diff = curr_val - prev_val
                
                # 时间间隔过大(如断线重连)，重置状态，避免计算错误
                time_diff = (curr_time - prev_time).total_seconds()
                if time_diff > 300: # 5分钟断档
                     prev_val = curr_val
                     prev_time = curr_time
                     continue

                if diff > threshold_kg:
                    # [关键逻辑] 检测到重量显著增加 -> 判定为投料
                    # print(f"      检测到增加: +{diff:.2f} kg at {curr_time}")
                    
                    p = Point("feeding_records") \
                        .tag("device_id", device_id) \
                        .field("added_weight", float(diff)) \
                        .time(curr_time)
                    
                    feeding_events.append(p)
                    total_added_weight += diff
                    
                prev_val = curr_val
                prev_time = curr_time
            
            # 4. 写入数据库
            if feeding_events:
                print(f"   📈 统计: 检测到 {len(feeding_events)} 次投料，总计加入 {total_added_weight:.2f} kg 原料")
                print(f"   💾 正在写入数据库...")
                # 分批写入
                batch_size = 500
                for i in range(0, len(feeding_events), batch_size):
                    batch = feeding_events[i:i+batch_size]
                    write_api.write(bucket=bucket, record=batch)
                
                total_records += len(feeding_events)
            else:
                print("   ⚪ 未检测到投料事件")
                
        except Exception as e:
            print(f"   ❌ 处理出错: {e}")
            
    print(f"\n✅ 完成! 共生成 {total_records} 条投料历史数据。")

if __name__ == "__main__":
    populate_feeding_data()
