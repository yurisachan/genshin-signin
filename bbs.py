import os
import requests
import time
import hashlib
import random
import string
import json
import re

# ================= 核心配置 =================
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip()

# 严格同步你提供的源码配置
APP_VERSION = "2.99.1" 
CLIENT_TYPE = "2" # Android App
SALT_DS1 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"  #用于互动
SALT_DS2 = "b0EofkfMKq2saWV9fwux18J5vzcFTlex"  #用于签到
VERIFY_KEY = "bll8iq97cem8"

# 频道列表 (注意id是字符串)
BBS_LIST = [
    # {"id": "1", "forumId": "1", "name": "崩坏3"},
    {"id": "2", "forumId": "26", "name": "原神"}
    # {"id": "5", "forumId": "34", "name": "大别野"},
    # {"id": "6", "forumId": "52", "name": "星穹铁道"},
    # {"id": "8", "forumId": "57", "name": "绝区零"}
]
# ===========================================

# 固定设备信息，防止风控
DEVICE_ID = "".join(random.sample(string.ascii_letters + string.digits, 32)).upper()

def get_ds1():
    """DS1: 用于点赞/看帖/分享"""
    t = int(time.time())
    r = "".join(random.sample(string.ascii_lowercase + string.digits, 6))
    c = hashlib.md5(f"salt={SALT_DS1}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{c}"

def get_ds2(query="", body=""):
    """DS2: 专用于签到，必须配合紧凑JSON"""
    t = int(time.time())
    r = str(random.randint(100000, 200000))
    # 确保 body 是字符串
    main = f"salt={SALT_DS2}&t={t}&r={r}&b={body}&q={query}"
    c = hashlib.md5(main.encode()).hexdigest()
    return f"{t},{r},{c}"

def get_headers(name="generic", ds_type=1, body="", query=""):
    """
    构造请求头
    ds_type: 1=DS1(互动), 2=DS2(签到)
    """
    headers = {
        "cookie": COOKIE, # 就算有多余字段也全发过去，防止缺失必要字段
        "x-rpc-client_type": CLIENT_TYPE,
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
        "x-rpc-device_id": DEVICE_ID,
        "x-rpc-device_name": "Xiaomi Mi 10",
        "x-rpc-device_model": "Mi 10",
        "x-rpc-h265_supported": "1",
        "x-rpc-csm_source": "discussion",
        "Referer": "https://app.mihoyo.com",
        "Host": "bbs-api.miyoushe.com",
        "User-Agent": "okhttp/4.9.3"
    }
    
    if ds_type == 2:
        headers["DS"] = get_ds2(query, body)
        headers["Content-Type"] = "application/json; charset=UTF-8"
    else:
        headers["DS"] = get_ds1()
        
    if name == "task": # 查询任务需要特殊的头
        return {
            'User-Agent': f'Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/{APP_VERSION}',
            'Referer': 'https://webstatic.mihoyo.com',
            'X-Requested-With': 'com.mihoyo.hyperion',
            "Cookie": COOKIE
        }
        
    return headers

def push_wechat(msg):
    if PUSH_KEY:
        try:
            requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": "🪙 米游社任务报告", "desp": msg})
        except: pass

class MihoyoBBSAuto:
    def __init__(self):
        self.logs = []
        self.task_do = {"sign": False, "read_num": 3, "like_num": 5, "share": False}
        
    def log(self, msg):
        print(msg)
        self.logs.append(msg)

    def check_tasks(self):
        url = "https://bbs-api.miyoushe.com/apihub/wapi/getUserMissionsState"
        try:
            res = requests.get(url, params={"point_sn": "myb"}, headers=get_headers(name="task")).json()
            data = res["data"]
            today_get = data["can_get_points"]
            
            if today_get == 0:
                self.log(f"🎉 任务已全部完成！当前总米游币: {data['total_points']}")
                return False
            
            # 更新任务状态
            for m in data["states"]:
                if m["mission_id"] == 58 and m["is_get_award"]: self.task_do["sign"] = True
                if m["mission_id"] == 59: self.task_do["read_num"] -= m["happened_times"]
                if m["mission_id"] == 60: self.task_do["like_num"] -= m["happened_times"]
                if m["mission_id"] == 61 and m["is_get_award"]: self.task_do["share"] = True
                
            self.task_do["read_num"] = max(0, self.task_do["read_num"])
            self.task_do["like_num"] = max(0, self.task_do["like_num"])
            
            self.log(f"📊 待完成: 签到[{'❌' if not self.task_do['sign'] else '✅'}] 看帖[{self.task_do['read_num']}] 点赞[{self.task_do['like_num']}] 分享[{'❌' if not self.task_do['share'] else '✅'}]")
            return True
        except Exception as e:
            self.log(f"❌ 获取任务失败: {e}")
            return False

    def do_sign(self):
        if self.task_do["sign"]: return
        self.log("\n>>> 开始签到")
        url = "https://bbs-api.miyoushe.com/apihub/app/api/signIn"
        
        for game in BBS_LIST:
            # 【核心修复】: 手动构建无空格 JSON 字符串
            # 这里的 "2" 必须是字符串，因为 BBS_LIST 里定义的是字符串
            payload_str = json.dumps({"gids": game["id"]}, separators=(',', ':'))
            
            # 使用 DS2 并在 headers 里带上 Content-Type
            headers = get_headers(ds_type=2, body=payload_str)
            
            # data=payload_str 确保发送的数据和算 DS 的数据 byte 级一致
            try:
                res = requests.post(url, headers=headers, data=payload_str).json()
                if res["retcode"] == 0:
                    self.log(f"✅ {game['name']}: 签到成功")
                elif "已经签到" in str(res):
                    self.log(f"👀 {game['name']}: 已签到")
                else:
                    self.log(f"❌ {game['name']}: {res['message']} ({res['retcode']})")
            except Exception as e:
                self.log(f"❌ {game['name']}: 请求异常 {e}")
            
            time.sleep(random.uniform(2, 4))

    def do_interactions(self):
        if self.task_do["read_num"] <= 0 and self.task_do["like_num"] <= 0 and self.task_do["share"]:
            return

        self.log("\n>>> 开始互动")
        headers = get_headers(ds_type=1) # 互动使用 DS1
        
        # 获取帖子
        try:
            list_url = "https://bbs-api.miyoushe.com/post/api/getForumPostList?forum_id=26&is_good=false&is_hot=false&page_size=20&sort_type=1"
            posts = requests.get(list_url, headers=headers).json()["data"]["list"]
            post_ids = [p["post"]["post_id"] for p in posts]
        except:
            self.log("❌ 无法获取帖子列表")
            return

        for pid in post_ids:
            # 任务全部完成则提前退出
            if self.task_do["read_num"] <= 0 and self.task_do["like_num"] <= 0 and self.task_do["share"]:
                break
                
            # 1. 看帖
            if self.task_do["read_num"] > 0:
                requests.get(f"https://bbs-api.miyoushe.com/post/api/getPostFull?post_id={pid}", headers=headers)
                self.log(f"👁️ 浏览: {pid}")
                self.task_do["read_num"] -= 1
                time.sleep(1.5)

            # 2. 点赞 (包含失败重试日志)
            if self.task_do["like_num"] > 0:
                # 注意：requests.post(json=...) 默认是 DS1 签名，body 不需要紧凑
                like_url = "https://bbs-api.miyoushe.com/apihub/sapi/upvotePost"
                payload = {"post_id": pid, "is_cancel": False, "upvote_type": "1"}
                
                res = requests.post(like_url, headers=headers, json=payload).json()
                if res["retcode"] == 0:
                    self.log(f"👍 点赞: {pid}")
                    self.task_do["like_num"] -= 1
                    time.sleep(1)
                    # 马上取消点赞
                    payload["is_cancel"] = True
                    requests.post(like_url, headers=headers, json=payload)
                else:
                    self.log(f"⚠️ 点赞失败 {pid}: {res['message']}")
                time.sleep(1.5)

            # 3. 分享
            if not self.task_do["share"]:
                requests.get(f"https://bbs-api.miyoushe.com/apihub/api/getShareConf?entity_id={pid}&entity_type=1", headers=headers)
                self.log(f"🔄 分享: {pid}")
                self.task_do["share"] = True
                time.sleep(1.5)

    def run(self):
        self.log(f"🚀 启动脚本 v{APP_VERSION}")
        if "stoken" not in COOKIE:
             self.log("⚠️ Cookie中未检测到 stoken，任务可能失败！")

        for _ in range(3): # 最多尝试3轮，防止无限循环
            if not self.check_tasks(): break
            self.do_sign()
            self.do_interactions()
            time.sleep(2)
            
        self.log("🏁 任务结束")
        push_wechat("\n".join(self.logs))

if __name__ == "__main__":
    MihoyoBBSAuto().run()
