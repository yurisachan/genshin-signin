import os
import requests
import time
import hashlib
import random
import string
import json

# ================= 配置区域 =================
# 注意：米游社App任务必须包含 stoken 和 stuid 字段，仅有 ltoken 可能无法点赞！
COOKIE = os.environ.get("GS_COOKIE", "").strip()
PUSH_KEY = os.environ.get("SEND_KEY", "").strip()

# BBS App 的核心常量 (与原神网页端不同)
APP_VERSION = "2.59.1"
CLIENT_TYPE = "2" # 2 代表 Android App
# 米游社 App 专用的 Salt (常被称为 K2 Salt)
BBS_SALT = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v" 

# 支持的社区列表 (gids: 2是原神, 6是星穹铁道, 8是绝区零)
# 这里以原神为例，forum_id=26 是原神酒馆
BBS_LIST = [
    {"name": "原神", "gids": "2", "forum_id": "26"}
]
# ===========================================

def get_bbs_ds() -> str:
    """
    生成米游社 App 专用的 DS 1.0 (Dynamic Secret)
    算法：md5(salt=SALT&t=t&r=r)
    """
    t = int(time.time())
    # 随机 6 位全小写字母和数字
    r = ''.join(random.sample(string.ascii_lowercase + string.digits, 6))
    
    main_str = f"salt={BBS_SALT}&t={t}&r={r}"
    c = hashlib.md5(main_str.encode(encoding='utf-8')).hexdigest()
    
    return f"{t},{r},{c}"

def get_bbs_headers():
    """封装米游社 App 的请求头"""
    return {
        "User-Agent": f"miHoYoBBS/{APP_VERSION}",
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-client_type": CLIENT_TYPE,
        "x-rpc-device_id": "".join(random.sample(string.ascii_letters + string.digits, 32)).upper(),
        "DS": get_bbs_ds(), # BBS 使用 DS1.0 即可
        "Cookie": COOKIE,
        "Host": "bbs-api.mihoyo.com"
    }

def push_wechat(summary_list):
    """微信推送逻辑"""
    if not PUSH_KEY:
        return
    title = "🪙 米游社赚米游币报告"
    content = "\n\n".join(summary_list)
    requests.post(f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data={"title": title, "desp": content})

# --- 以下为核心动作 API ---

def bbs_sign(gids):
    """1. 社区讨论区签到"""
    url = "https://bbs-api.mihoyo.com/apihub/sapi/signIn"
    payload = {"gids": gids}
    res = requests.post(url, headers=get_bbs_headers(), json=payload).json()
    return res

def get_post_list(forum_id):
    """获取帖子列表 (用于后续看帖/点赞)"""
    url = f"https://bbs-api.mihoyo.com/post/api/getForumPostList?forum_id={forum_id}&is_good=false&is_hot=false&page_size=10&sort_type=1"
    res = requests.get(url, headers=get_bbs_headers()).json()
    return [post["post"]["post_id"] for post in res.get("data", {}).get("list", [])]

def read_post(post_id):
    """2. 浏览帖子"""
    url = f"https://bbs-api.mihoyo.com/post/api/getPostFull?post_id={post_id}"
    requests.get(url, headers=get_bbs_headers())

def like_post(post_id, is_cancel=False):
    """3. 点赞/取消点赞帖子"""
    url = "https://bbs-api.mihoyo.com/apihub/sapi/upvotePost"
    payload = {"post_id": post_id, "is_cancel": is_cancel, "upvote_type": "1"}
    requests.post(url, headers=get_bbs_headers(), json=payload)

def share_post(post_id):
    """4. 分享帖子"""
    url = f"https://bbs-api.mihoyo.com/apihub/api/getShareConf?entity_id={post_id}&entity_type=1"
    requests.get(url, headers=get_bbs_headers())

# --- 主控逻辑 ---

def main():
    print("🚀 启动米游社日常任务赚米游币...")
    
    if "stuid" not in COOKIE or "stoken" not in COOKIE:
        print("⚠️ 警告：当前 Cookie 未包含 stuid 和 stoken。点赞和分享可能会失败！")
    
    summary = []
    
    for game in BBS_LIST:
        game_name = game["name"]
        gids = game["gids"]
        forum_id = game["forum_id"]
        
        print(f"\n[{game_name}] 频道开始执行...")
        
        # 1. 讨论区打卡签到
        sign_res = bbs_sign(gids)
        if sign_res.get("retcode") == 0:
            summary.append(f"✅ [{game_name}] 社区签到成功 (或已签到)")
            print(" -> 签到成功")
        else:
            summary.append(f"❌ [{game_name}] 社区签到失败: {sign_res.get('message')}")
            print(f" -> 签到失败: {sign_res.get('message')}")
        time.sleep(1)

        # 2. 获取最新帖子列表
        post_ids = get_post_list(forum_id)
        if not post_ids:
            print(" -> 未获取到帖子列表，跳过后续任务")
            continue
            
        print(f" -> 成功获取到 {len(post_ids)} 个帖子，开始互动...")

        # 3. 执行日常循环 (3次看帖, 5次点赞, 1次分享)
        read_count, like_count, share_count = 0, 0, 0
        
        for post_id in post_ids:
            # 每日要求：看 3 帖
            if read_count < 3:
                read_post(post_id)
                read_count += 1
                print(f"   👁️ 浏览帖子: {post_id}")
                time.sleep(1)
            
            # 每日要求：点赞 5 帖
            if like_count < 5:
                # 动作1：点赞
                like_post(post_id, is_cancel=False)
                print(f"   👍 点赞帖子: {post_id}")
                time.sleep(0.5)
                # 动作2：立刻取消点赞 (神仙细节，防止主页全是垃圾赞)
                like_post(post_id, is_cancel=True)
                like_count += 1
                time.sleep(1)
            
            # 每日要求：分享 1 帖
            if share_count < 1:
                share_post(post_id)
                share_count += 1
                print(f"   🔄 分享帖子: {post_id}")
                time.sleep(1)
            
            # 如果都完成了，就跳出循环
            if read_count >= 3 and like_count >= 5 and share_count >= 1:
                break
                
        summary.append(f"🎉 [{game_name}] 互动完毕：浏览{read_count}/3，点赞{like_count}/5，分享{share_count}/1")

    print("\n🏁 任务完成，正在发送汇总报告...")
    push_wechat(summary)

if __name__ == "__main__":
    main()
