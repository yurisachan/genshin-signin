import os
import requests
import time
import hashlib
import random
import string
import json

# ================= 配置区域 =================
# 1. 自动清理环境变量中的空白字符
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip()

# 2. 核心常量
# 国服原神新版 Luna 签到活动 ID
ACT_ID = "e202311201442471"  
SALT = "k8v1tj7p176403t835560ndnx32230v7" 
APP_VERSION = "2.99.1"
CLIENT_TYPE = "5" # mobile web

# API 接口
ROLES_URL = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie?game_biz=hk4e_cn"
SIGN_URL = "https://api-takumi.mihoyo.com/event/luna/sign"
# ===========================================

def get_ds(query: str = "", body: dict = None) -> str:
    """
    生成国服最新的 DS 2.0 签名
    """
    t = int(time.time())
    r = ''.join(random.sample(string.ascii_letters + string.digits, 6))
    
    # 将请求体转换为紧凑 JSON 字符串（去空格）
    b = json.dumps(body, separators=(',', ':')) if body else ""
    q = query
    
    main_str = f"salt={SALT}&t={t}&r={r}&b={b}&q={q}"
    c = hashlib.md5(main_str.encode(encoding='utf-8')).hexdigest()
    
    return f"{t},{r},{c}"

def get_headers(body: dict = None):
    """封装统一的请求头"""
    headers = {
        "User-Agent": f"Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/{APP_VERSION}",
        # [修改点 1]：更新正确的 Origin 和 Referer 域名
        "Origin": "https://act.mihoyo.com",
        "Referer": f"https://act.mihoyo.com/bbs/event/signin/h5/index.html?act_id={ACT_ID}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "Host": "api-takumi.mihoyo.com",
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-client_type": CLIENT_TYPE,
        # [修改点 2]：最核心的一行！Luna 统一接口必须指定签到的游戏代号，hk4e 代表原神
        "x-rpc-signgame": "hk4e", 
        "x-rpc-device_id": "".join(random.sample(string.ascii_letters + string.digits, 32)).upper(),
        "DS": get_ds(body=body),
        "Cookie": COOKIE
    }
    return headers

def push_wechat(summary_list):
    """汇总结果并执行单次推送"""
    if not PUSH_KEY:
        print("⚠️ 未配置 SEND_KEY，跳过推送")
        return
        
    title = "🌟 原神自动签到报告"
    content = "\n\n".join(summary_list)
    
    url = f"https://sctapi.ftqq.com/{PUSH_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        print("✅ 结果已推送到微信")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def main():
    print(f"🚀 启动原神国服自动签到 (版本 {APP_VERSION})...")
    
    if not COOKIE:
        print("终止运行：请先在 Secrets 中配置 GS_COOKIE")
        return

    # 1. 获取角色列表
    try:
        # GET 请求，没有 body
        role_res = requests.get(ROLES_URL, headers=get_headers(), timeout=15).json()
        
        # [补充点]：增加对 Cookie 失效的判断 (-100)
        if role_res.get("retcode") == -100:
            msg = "❌ 获取角色失败：Cookie已失效或不完整，请重新抓取Cookie"
            print(msg)
            push_wechat([msg])
            return
            
        if role_res.get("retcode") != 0:
            msg = f"❌ 获取角色失败：{role_res.get('message')}"
            print(msg)
            push_wechat([msg])
            return
        
        roles = role_res["data"]["list"]
        print(f"🔍 找到 {len(roles)} 个角色，准备开始签到...")
    except Exception as e:
        msg = f"🚀 系统异常：{str(e)}"
        print(msg)
        push_wechat([msg])
        return

    # 2. 依次签到并收集结果
    summary = []
    for role in roles:
        role_info = f"{role['nickname']}({role['game_uid']})"
        payload = {
            "act_id": ACT_ID,
            "region": role["region"],
            "uid": role["game_uid"]
        }
        
        try:
            # POST 请求，必须把 payload 传给 get_headers 以计算出正确的 DS2.0
            headers = get_headers(body=payload)
            res = requests.post(SIGN_URL, headers=headers, json=payload, timeout=15).json()
            retcode = res.get("retcode")
            msg = res.get("message")
            
            if retcode == 0:
                result = f"✅ {role_info}: 签到成功！"
            elif retcode == -5003:
                result = f"✨ {role_info}: 今天已经签过啦~"
            else:
                result = f"⚠️ {role_info}: 失败 | {msg} ({retcode})"
            
            print(result)
            summary.append(result)
        except Exception as e:
            err = f"❌ {role_info}: 请求异常 ({str(e)})"
            print(err)
            summary.append(err)
        
        # 随机延迟防止风控
        time.sleep(random.uniform(2, 5))

    # 3. 最终推送
    print("🏁 任务完成，正在发送汇总报告...")
    push_wechat(summary)

if __name__ == "__main__":
    main()
