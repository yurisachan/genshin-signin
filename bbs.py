import os
import requests
import time
import hashlib
import random
import string
import json
import re

# ================= 核心配置与密钥 =================
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip()

# 常量 (提取自你提供的源码)
APP_VERSION = "2.99.1"
CLIENT_TYPE = "2"
SALT_DS1 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"  # mihoyobbs_salt_x6 (用于日常任务)
SALT_DS2 = "b0EofkfMKq2saWV9fwux18J5vzcFTlex"  # mihoyobbs_salt (用于签到)
VERIFY_KEY = "bll8iq97cem8"

# 支持的频道 (提取自你提供的字典)
BBS_LIST = [
    # {"id": "1", "forumId": "1", "name": "崩坏3"},
    {"id": "2", "forumId": "26", "name": "原神"},
    # {"id": "5", "forumId": "34", "name": "大别野"},
    # {"id": "6", "forumId": "52", "name": "星穹铁道"},
    # {"id": "8", "forumId": "57", "name": "绝区零"}
]
# =================================================

# 固化设备信息 (防止每次运行改变触发风控)
DEVICE_ID = "".join(random.sample(string.ascii_letters + string.digits, 32)).upper()

def extract_stoken_cookie(cookie_str):
    """提取高权限 stuid 和 stoken"""
    stuid = re.search(r'stuid=([^;]+)', cookie_str)
    stoken = re.search(r'stoken=([^;]+)', cookie_str)
    mid = re.search(r'mid=([^;]+)', cookie_str) # 部分新号需要 mid
    res = ""
    if stuid: res += f"stuid={stuid.group(1)};"
    if stoken: res += f"stoken={stoken.group(1)};"
    if mid: res += f"mid={mid.group(1)};"
    return res if res else cookie_str

def get_ds1():
    """普通的 DS1 (用于看帖、点赞、分享)"""
    t = int(time.time())
    r = "".join(random.sample(string.ascii_lowercase + string.digits, 6))
    c = hashlib.md5(f"salt={SALT_DS1}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{c}"

def get_ds2(query="", body=""):
    """严苛的 DS2 (用于社区签到 API)"""
    t = int(time.time())
    r = str(random.randint(100000, 200000))
    main = f"salt={SALT_DS2}&t={t}&r={r}&b={body}&q={query}"
    c = hashlib.md5(main.encode()).hexdigest()
    return f"{t},{r},{c}"

def get_headers(is_task_check=False):
    """
    is_task_check: 查询任务列表使用的是一套精简的头
    否则使用极其完整的 App 头
    """
    if is_task_check:
        return {
            'User-Agent': f'Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/{APP_VERSION}',
            'Referer': 'https://webstatic.mihoyo.com',
            'X-Requested-With': 'com.mihoyo.hyperion',
            "Cookie": COOKIE
        }
        
    return {
        "DS": get_ds1(), # 默认装载 DS1，签到时会覆盖
        "cookie": extract_stoken_cookie(COOKIE),
        "x-rpc-client_type": CLIENT_TYPE,
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
        "x-rpc-device_id": DEVICE_ID,
        "x-rpc-device_name": "Xiaomi Mi 10",
        "x-rpc-device_model": "Mi 10",
        "x-rpc-h265_supported": "1",
        "Referer": "https://app.mihoyo.com",
        "x-rpc-verify_key": VERIFY_KEY,
        "x-rpc-csm_source": "discussion",
        "Content-Type": "application/json; charset=UTF-8",
        "Host": "bbs-api.miyoushe.com",
        "User-Agent": "okhttp/4.9.3"
    }

def push_wechat(msg):
    if PUSH_KEY:
        try:
            requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": "🪙 米游社任务报告", "desp": msg})
        except: pass

class MihoyoBBSAuto:
    def __init__(self):
        self.logs = []
        self.task_do = {"sign": False, "read_num": 3, "like_num": 5, "share": False}
        self.have_coins = 0
        self.today_get = 0

    def log(self, msg):
        print(msg)
        self.logs.append(msg)

    def check_tasks(self):
        """核心逻辑：查询今日任务完成度 (完美还原 getUserMissionsState)"""
        url = "https://bbs-api.miyoushe.com/apihub/wapi/getUserMissionsState"
        try:
            res = requests.get(url, params={"point_sn": "myb"}, headers=get_headers(is_task_check=True)).json()
            if res.get("retcode") != 0:
                self.log(f"⚠️ 获取任务状态失败: {res}")
                return False
                
            data = res["data"]
            self.have_coins = data["total_points"]
            self.today_get = data["can_get_points"]
            
            if self.today_get == 0:
                self.log(f"🎉 任务已全部完成！当前总米游币: {self.have_coins}")
                self.task_do = {"sign": True, "read_num": 0, "like_num": 0, "share": True}
                return True
                
            missions = data["states"]
            for m in missions:
                if m["mission_id"] == 58 and m["is_get_award"]: self.task_do["sign"] = True
                if m["mission_id"] == 59: self.task_do["read_num"] -= m["happened_times"]
                if m["mission_id"] == 60: self.task_do["like_num"] -= m["happened_times"]
                if m["mission_id"] == 61 and m["is_get_award"]: self.task_do["share"] = True
                
            # 防止负数
            self.task_do["read_num"] = max(0, self.task_do["read_num"])
            self.task_do["like_num"] = max(0, self.task_do["like_num"])
            
            self.log(f"📊 今日待完成: 签到({'已完' if self.task_do['sign'] else '未完'}), 看帖 {self.task_do['read_num']}次, 点赞 {self.task_do['like_num']}次, 分享({'已完' if self.task_do['share'] else '未完'})")
            return True
        except Exception as e:
            self.log(f"❌ 任务查询异常: {e}")
            return False

    def do_sign(self):
        if self.task_do["sign"]: return
        self.log("\n>>> 开始社区讨论区签到")
        headers = get_headers()
        url = "https://bbs-api.miyoushe.com/apihub/app/api/signIn"
        
        for game in BBS_LIST:
            # 必须使用紧凑型 json 生成 DS2
            payload_str = json.dumps({"gids": game["id"]}, separators=(',', ':'))
            headers["DS"] = get_ds2("", payload_str)
            
            res = requests.post(url, headers=headers, data=payload_str).json()
            if res.get("retcode") == 0:
                self.log(f"✅ {game['name']} 签到成功")
            elif res.get("retcode") == 1034:
                self.log(f"⚠️ {game['name']} 触发图形验证码(1034)，已跳过") # 单文件脚本无法过验证码
            elif "已经签到" in str(res):
                self.log(f"✨ {game['name']} 已签到")
            else:
                self.log(f"❌ {game['name']} 签到失败: {res.get('message')}")
            time.sleep(random.randint(3, 6))

    def do_interactions(self):
        reads_needed = self.task_do["read_num"]
        likes_needed = self.task_do["like_num"]
        share_needed = not self.task_do["share"]
        
        if reads_needed == 0 and likes_needed == 0 and not share_needed:
            return

        self.log("\n>>> 获取帖子列表进行互动...")
        headers = get_headers()
        post_url = "https://bbs-api.miyoushe.com/post/api/getForumPostList?forum_id=26&is_good=false&is_hot=false&page_size=20&sort_type=1"
        
        try:
            posts = requests.get(post_url, headers=headers).json()["data"]["list"]
            post_ids = [p["post"]["post_id"] for p in posts]
        except:
            self.log("⚠️ 帖子获取失败，终止互动")
            return

        for pid in post_ids:
            # 如果全干完了，提前结束
            if reads_needed <= 0 and likes_needed <= 0 and not share_needed:
                break
                
            if reads_needed > 0:
                requests.get(f"https://bbs-api.miyoushe.com/post/api/getPostFull?post_id={pid}", headers=headers)
                self.log(f"👁️ 浏览帖子 {pid}")
                reads_needed -= 1
                time.sleep(random.randint(2, 4))
                
            if likes_needed > 0:
                payload = {"post_id": pid, "is_cancel": False, "upvote_type": "1"}
                res = requests.post("https://bbs-api.miyoushe.com/apihub/sapi/upvotePost", headers=headers, json=payload).json()
                if res.get("retcode") == 0:
                    self.log(f"👍 点赞帖子 {pid}")
                    likes_needed -= 1
                    time.sleep(2)
                    # 模拟取消点赞 (防污染主页)
                    payload["is_cancel"] = True
                    requests.post("https://bbs-api.miyoushe.com/apihub/sapi/upvotePost", headers=headers, json=payload)
                elif res.get("retcode") == 1034:
                    self.log(f"⚠️ 点赞触发验证码，跳过")
                time.sleep(random.randint(2, 4))
                
            if share_needed:
                requests.get(f"https://bbs-api.miyoushe.com/apihub/api/getShareConf?entity_id={pid}&entity_type=1", headers=headers)
                self.log(f"🔄 分享帖子 {pid}")
                share_needed = False
                time.sleep(random.randint(2, 4))

    def run(self):
        self.log("🚀 开始执行米游社日常...")
        if "stoken=" not in COOKIE:
            self.log("❌ 严重错误: Cookie 中不包含 stoken，任务无法执行。")
            push_wechat("❌ Cookie失效或缺少stoken")
            return

        # 核心防风控循环：查任务 -> 做任务 -> 再查任务确认
        for _ in range(2):
            if not self.check_tasks(): break
            if self.today_get == 0: break # 今天奖励拿满了，直接退出
            
            self.do_sign()
            self.do_interactions()
            
        self.check_tasks() # 最后确认一遍余额
        self.log("\n🏁 任务结束")
        push_wechat("\n".join(self.logs))

if __name__ == "__main__":
    MihoyoBBSAuto().run()
