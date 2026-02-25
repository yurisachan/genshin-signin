import os
import requests
import time
import hashlib
import random
import string
import json

# ================= 配置区 =================
# 读取并自动清理前后的换行符和空格
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip() # 这里对应你 GitHub Secrets 里的名字

# 签到所需的固定参数
ACT_ID = "e202009291139501"
APP_VERSION = "2.34.1"
# 社区签到特定的 Salt (LK2)
SALT = "6s9q3p0t977un3pp827he9bvbtq968ps" 

def get_ds(query: str = "", body: dict = None) -> str:
    """
    生成 DS 2.0 校验码
    计算逻辑：DS = md5(salt=n, t=time, r=random, b=body_json, q=query_string)
    """
    t = int(time.time())
    r = ''.join(random.sample(string.ascii_letters + string.digits, 6))
    
    # 核心：将 body 转化为紧凑的 JSON 字符串参与哈希，严禁包含多余空格
    b = json.dumps(body) if body else ""
    q = query
    
    main_str = f"salt={SALT}&t={t}&r={r}&b={b}&q={q}"
    c = hashlib.md5(main_str.encode(encoding='utf-8')).hexdigest()
    
    return f"{t},{r},{c}"

def push_wechat(title, content):
    """通过 Server 酱 (SEND_KEY) 推送结果"""
    if not PUSH_KEY:
        print("⚠️ 未配置 SEND_KEY，跳过推送")
        return
    # 兼容旧版和 Turbo 版接口
    url = f"https://sctapi.ftqq.com/{PUSH_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        res = requests.post(url, data=data, timeout=10)
        print(f"微信推送状态: {res.status_code}")
    except Exception as e:
        print(f"推送异常: {e}")

def sign_in():
    """执行签到逻辑"""
    if not COOKIE:
        return "❌ 运行失败：未在 Secrets 中配置 GS_COOKIE"
    
    url = "https://api-takumi.mihoyo.com/event/bbs_sign_reward/sign"
    payload = {"act_id": ACT_ID}
    
    # 模拟真实 App 的请求头
    # 使用 .strip() 确保 COOKIE 和 DS 中没有 \n
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.34.1",
        "Referer": f"https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?bbs_auth_required=true&act_id={ACT_ID}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "Host": "api-takumi.mihoyo.com",
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-client_type": "5", 
        "x-rpc-device_id": "".join(random.sample(string.ascii_letters + string.digits, 32)).upper(),
        "DS": get_ds(body=payload).strip(), 
        "Cookie": COOKIE
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        res_data = response.json()
        
        retcode = res_data.get("retcode")
        message = res_data.get("message")
        
        if retcode == 0:
            return "✅ 原神签到成功！奖励已发放到邮箱。"
        elif retcode == -5003:
            return f"💡 您今天已经签到过了：{message}"
        elif retcode == -100:
            return "❌ Cookie 已失效，请重新获取并更新 Secrets"
        else:
            return f"❌ 签到失败\n状态码: {retcode}\n信息: {message}"
            
    except Exception as e:
        # 如果依然报错，打印出具体的错误类型方便排查
        return f"🚀 脚本执行异常: {str(e)}"

if __name__ == "__main__":
    print("--- 正在启动米游社自动签到 ---")
    result_msg = sign_in()
    print(result_msg)
    
    # 执行推送逻辑
    push_wechat("米游社签到提醒", result_msg)
