import os
import requests
import time
import hashlib
import random
import string
import json

# ================= 配置区域 =================
# 读取并清理环境变量
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip() 

# 核心常量 (请确保 ACT_ID 和 SALT 是最新的)
ACT_ID = "e202311201442471"  
APP_VERSION = "2.68.1"
SALT = "k8v1tj7p176403t835560ndnx32230v7" 
# ===========================================

def get_ds():
    """生成米游社所需的动态签名 (DS)"""
    t = int(time.time())
    r = ''.join(random.sample(string.ascii_letters + string.digits, 6))
    # 这里的算法需要根据实际接口调整，若持续 -10001 请参考之前的 DS 2.0 逻辑
    text = f"salt={SALT}&t={t}&r={r}"
    md5_hash = hashlib.md5(text.encode(encoding='utf-8')).hexdigest()
    return f"{t},{r},{md5_hash}"

def get_headers(use_ds=True):
    """构造请求头"""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) miHoYoBBS/2.68.1",
        "Referer": f"https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?act_id={ACT_ID}",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": COOKIE,
        "x-rpc-device_id": "".join(random.sample(string.ascii_letters + string.digits, 32)).upper(),
        "x-rpc-client_type": "5", 
        "x-rpc-app_version": APP_VERSION,
    }
    if use_ds:
        # 移除可能存在的换行符，防止 Header 报错
        headers["DS"] = get_ds().replace("\n", "").strip()
    return headers

def get_roles():
    """获取绑定的原神角色信息"""
    url = f"https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie?game_biz=hk4e_cn"
    try:
        response = requests.get(url, headers=get_headers(use_ds=False), timeout=10)
        data = response.json()
        if data["retcode"] != 0:
            return None, f"获取角色失败: {data['message']}"
        return data["data"]["list"], "Success"
    except Exception as e:
        return None, f"请求异常: {str(e)}"

def do_sign(role):
    """执行签到操作并返回结果字符串"""
    url = "https://api-takumi.mihoyo.com/event/luna/sign"
    payload = {
        "act_id": ACT_ID,
        "region": role["region"],
        "uid": role["game_uid"]
    }
    role_name = f"{role['nickname']}({role['game_uid']})"
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=10)
        data = response.json()
        
        if data["retcode"] == 0:
            return f"✅ {role_name}: 签到成功"
        elif data["retcode"] == -5003:
            return f"✨ {role_name}: 今日已签到"
        else:
            return f"⚠️ {role_name}: 失败({data['message']})"
    except Exception as e:
        return f"❌ {role_name}: 请求异常({str(e)})"

def push_wechat(title, content):
    """通过 Server 酱 (SEND_KEY) 推送结果"""
    if not PUSH_KEY:
        print("⚠️ 未配置 SEND_KEY，跳过微信推送")
        return
    url = f"https://sctapi.ftqq.com/{PUSH_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        res = requests.post(url, data=data, timeout=10)
        print(f"微信推送结果状态码: {res.status_code}")
    except Exception as e:
        print(f"微信推送异常: {e}")
        
def main():
    print("🚀 开始执行原神自动签到...")
    results = [] # 用于收集所有签到结果
    
    # 1. 获取角色
    roles, status_msg = get_roles()
    if not roles:
        err_msg = f"终止运行：{status_msg}"
        print(err_msg)
        push_wechat("原神签到异常中断", err_msg)
        return
    
    print(f"🔍 找到 {len(roles)} 个角色，准备依次签到...")
    
    # 2. 遍历角色签到
    for role in roles:
        res = do_sign(role)
        print(res)
        results.append(res)
        # 随机等待，模拟人类行为
        if len(roles) > 1:
            time.sleep(random.randint(2, 5))
        
    # 3. 汇总并推送最终结果
    final_report = "\n".join(results)
    print("🏁 所有任务执行完毕，正在推送结果...")
    push_wechat("原神自动签到汇总报告", f"本次运行结果如下：\n\n{final_report}")

if __name__ == "__main__":
    main()
