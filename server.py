#!/usr/bin/env python3
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import time
import urllib.request
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from flask import Flask, jsonify, make_response, request, send_file, send_from_directory
except ImportError:
    Flask = None
    jsonify = None
    make_response = None
    request = None
    send_file = None
    send_from_directory = None

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR") or ("/tmp/mary-career-agent-data" if os.environ.get("VERCEL") else ROOT / "data"))
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
SESSIONS = DATA / "sessions"
DB_PATH = DATA / "db.json"

for folder in (DATA, UPLOADS, OUTPUTS, SESSIONS):
    folder.mkdir(exist_ok=True)

DEFAULT_DB = {
    "profile": None,
    "resume": None,
    "portfolio": [],
    "saved_jobs": [],
    "applications": [],
    "custom_jobs": []
}

KANBAN_STATUSES = ["感兴趣", "已投递", "面试中", "等待结果"]
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")


def session_root(session_id):
    root = SESSIONS / safe_name(session_id or "default")
    root.mkdir(exist_ok=True)
    (root / "uploads").mkdir(exist_ok=True)
    (root / "outputs").mkdir(exist_ok=True)
    return root


def db_path(session_id=None):
    return session_root(session_id) / "db.json" if session_id else DB_PATH


def uploads_dir(session_id=None):
    return session_root(session_id) / "uploads" if session_id else UPLOADS


def outputs_dir(session_id=None):
    return session_root(session_id) / "outputs" if session_id else OUTPUTS


def load_db(session_id=None):
    path = db_path(session_id)
    if not path.exists():
        save_db(DEFAULT_DB.copy(), session_id)
    with path.open("r", encoding="utf-8") as f:
        db = json.load(f)
    for key, value in DEFAULT_DB.items():
        db.setdefault(key, value)
    return db


def save_db(db, session_id=None):
    path = db_path(session_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def normalize_saved_jobs(db):
    normalized = []
    for item in db.get("saved_jobs", []):
        if "job" in item:
            item.setdefault("status", "感兴趣")
            if item["status"] in ("准备投递", "等待反馈"):
                item["status"] = "感兴趣" if item["status"] == "准备投递" else "等待结果"
            item.setdefault("savedAt", now_text())
            normalized.append(item)
        else:
            normalized.append({
                "id": f"app-{item.get('id', int(time.time() * 1000))}",
                "jobId": item.get("id"),
                "status": "感兴趣",
                "savedAt": now_text(),
                "job": item
            })
    db["saved_jobs"] = normalized
    return normalized


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def safe_name(name):
    base = Path(name or "upload").name
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", base)


def read_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    return handler.rfile.read(length) if length else b""


def json_response(handler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if getattr(handler, "session_id", None):
        handler.send_header("Set-Cookie", f"mary_session={handler.session_id}; Path=/; HttpOnly; SameSite=Lax")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def call_deepseek(prompt, max_output_tokens=1200):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是专业、谨慎的校园招聘 HR 助手。只基于用户提供的信息生成内容，不虚构经历。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": max_output_tokens,
        "response_format": {"type": "json_object"} if "JSON" in prompt or "json" in prompt.lower() else None
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    request = urllib.request.Request(
        DEEPSEEK_BASE_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        return (message.get("content") or "").strip()
    return None


def extract_json_object(text):
    if not text:
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_multipart(headers, body):
    content_type = headers.get("Content-Type", "")
    raw = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    message = BytesParser(policy=policy.default).parsebytes(raw)
    fields = {}
    files = {}
    if not message.is_multipart():
        return fields, files
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = {"filename": filename, "content": payload}
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
    return fields, files


def text_from_doc_with_textutil(path):
    if not shutil.which("textutil"):
        return ""
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20
        )
        return result.stdout.strip()
    except Exception:
        return ""


def extract_text(path, original_name):
    ext = Path(original_name).suffix.lower().strip(".")
    result = {
        "text": "",
        "parser": "none",
        "warnings": [],
        "links": [],
        "qr_hints": [],
        "file_type": ext or "unknown"
    }
    if ext in ("txt", "md", "csv"):
        result["text"] = path.read_text(encoding="utf-8", errors="ignore")
        result["parser"] = "plain-text"
    elif ext in ("doc", "docx", "rtf", "pdf"):
        text = text_from_doc_with_textutil(path)
        result["text"] = text
        result["parser"] = "macos-textutil" if text else "parser-unavailable"
        if not text:
            result["warnings"].append("暂未提取到文本。扫描版 PDF 或复杂 Word 可通过 OCR/文档解析服务增强。")
    elif ext in ("jpg", "jpeg", "png", "webp", "heic"):
        result["parser"] = "ocr-adapter"
        result["warnings"].append("图片已上传。当前本地环境未安装 OCR 引擎，正式版会接入 OCR 和二维码识别服务。")
        result["qr_hints"].append("若图片中含二维码，正式版会解析作品集链接；当前可手动粘贴链接兜底。")
    else:
        result["warnings"].append("文件格式暂不支持自动解析，请上传 Word、PDF、图片，或粘贴文本。")

    result["links"] = extract_links(result["text"] + " " + original_name)
    return result


def extract_links(text):
    return re.findall(r"https?://[^\s，。)）]+", text or "")


def classify_content(text, name=""):
    sample = f"{name} {text}".lower()
    resume_words = ["简历", "resume", "教育", "实习", "项目", "技能", "经历", "求职", "本科", "硕士", "专业"]
    supplement_words = ["作品集", "portfolio", "github", "behance", "notion", "证书", "成绩单", "论文"]
    other_words = ["合同", "发票", "身份证", "收据"]
    resume_score = sum(word in sample for word in resume_words)
    supplement_score = sum(word in sample for word in supplement_words)
    other_score = sum(word in sample for word in other_words)
    if resume_score >= 2:
        return "resume"
    if supplement_score >= 1:
        return "portfolio_or_supplement"
    if other_score >= 1:
        return "not_resume"
    return "unknown"


def build_profile(resume, portfolios, preferences=None):
    preferences = preferences or {}
    resume_bits = []
    if resume:
        resume_bits = [resume.get("originalName", ""), resume.get("text", "")]
    text = " ".join(resume_bits + [p.get("text", "") for p in portfolios])
    links = extract_links(text)
    for p in portfolios:
        links.extend(p.get("links", []))
    skills = keyword_hits(text, [
        "社群运营", "用户运营", "内容运营", "产品运营", "数据分析", "Excel", "SQL", "Python",
        "活动策划", "用户调研", "问卷调研", "增长", "复盘", "Canva", "Figma", "前端", "后端"
    ])
    if not skills:
        skills = ["沟通表达", "学习能力", "项目协作"]
    target = infer_target(text, preferences)
    warnings = []
    if resume and resume.get("kind") != "resume":
        warnings.append("上传内容不像完整简历，建议补充教育、项目、实习和技能信息。")
    if not re.search(r"\d+[%+]?|提升|增长|转化|参与率", text):
        warnings.append("简历量化结果较少，建议补充真实数据。")
    completeness = 58 + min(len(skills) * 4, 24) + (8 if links else 0) + (10 if preferences else 0)
    completeness = min(96, completeness)
    return {
        "name": "" if preferences.get("hideName") else (displayable_name(preferences.get("preferredName")) or infer_name(text)),
        "target": target,
        "skills": skills,
        "strengths": skills[:6],
        "raw_text": text,
        "risks": warnings or ["建议根据目标岗位继续强化关键词和量化结果。"],
        "portfolio_links": sorted(set(links)),
        "preferences": preferences,
        "completeness": completeness,
        "confidence": {
            "education": "中" if text else "低",
            "experience": "中" if skills else "低",
            "skills": "高" if len(skills) >= 4 else "中",
            "portfolio": "中" if links or portfolios else "未提供",
            "ai_conclusion": "中"
        }
    }


def enhance_profile_with_llm(profile, resume_text, preferences):
    prompt = f"""
你是一名互联网科技公司 HR，请基于学生简历和偏好生成求职画像。要求只基于已给信息，不虚构经历。
请输出 JSON，字段包括 name、target、skills、strengths、risks、completeness、confidence。
confidence 包含 education、experience、skills、portfolio、ai_conclusion。

简历文本：
{resume_text[:6000]}

偏好：
{json.dumps(preferences, ensure_ascii=False)}

当前规则画像：
{json.dumps(profile, ensure_ascii=False)}
"""
    data = extract_json_object(call_deepseek(prompt, 1400))
    if not data:
        return profile
    merged = dict(profile)
    for key in ("name", "target", "skills", "strengths", "risks", "completeness", "confidence"):
        if data.get(key):
            merged[key] = data[key]
    rule_name = displayable_name(profile.get("name"))
    model_name = displayable_name(merged.get("name"))
    merged["name"] = "" if preferences.get("hideName") else (rule_name or model_name)
    merged["raw_text"] = profile.get("raw_text", resume_text)
    merged["portfolio_links"] = profile.get("portfolio_links", [])
    merged["preferences"] = preferences
    return merged


def infer_name(text):
    raw = text or ""
    candidates = []

    def is_valid_name(value):
        clean = str(value or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}", clean):
            return False
        noise = (
            "示例", "简历", "求职", "附件", "上传", "文件", "模板", "个人", "作品",
            "作品集", "暑期", "实习", "校招", "春招", "秋招", "应届", "毕业",
            "教育", "经历", "项目", "技能", "电话", "邮箱", "学校", "学院", "大学",
            "本科", "硕士", "博士", "研究生", "专业", "同学们"
        )
        english_noise = (
            "sample", "resume", "cv", "student", "candidate", "applicant", "profile",
            "education", "experience", "project", "projects", "skill", "skills",
            "contact", "portfolio", "objective", "summary", "university", "school",
            "college", "bachelor", "master", "phone", "email"
        )
        return not any(word in clean for word in noise) and not any(word in clean.lower() for word in english_noise)

    def add_candidate(value, score):
        clean = re.sub(r"\s+", " ", str(value or "").strip(" ：:|｜,，;；"))
        clean = re.sub(r"^(姓名|名字|Name|name)\s*[:：]?\s*", "", clean).strip()
        if is_valid_name(clean):
            candidates.append((score, clean))

    explicit_patterns = [
        r"(?:姓名|名字|Name|name)\s*[:： ]\s*([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
        r"([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*(?:\+?86)?1[3-9]\d{9}",
        r"([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*[|｜]\s*(?:本科|硕士|博士|研究生|应届|求职|电话|邮箱)",
    ]
    for pattern in explicit_patterns:
        for match in re.finditer(pattern, raw):
            add_candidate(match.group(1), 100)

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    bad_line_words = r"https?|@|电话|邮箱|求职意向|教育背景|教育经历|实习经历|项目经历|技能|作品集|自我评价|校园经历|证书|获奖|学校|专业|本科|硕士|博士|education|experience|projects?|skills?|contact|portfolio|objective|summary|university|school|college|bachelor|master|phone|email"
    for index, line in enumerate(lines[:12]):
        clean = re.sub(r"^[#>*\-\s·•]+", "", line)
        clean = re.sub(r"\s+", " ", clean).strip()
        if re.search(bad_line_words, clean, re.I):
            continue
        add_candidate(clean, 90 - index * 5)
        first_piece = re.split(r"[|｜,，；;/(（\s]", clean)[0]
        add_candidate(first_piece, 82 - index * 5)
        for token in re.findall(r"[\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}", clean):
            add_candidate(token, 70 - index * 4)

    file_name_matches = re.findall(r"([\u4e00-\u9fff]{2,4})(?:\d{2,4}|暑期|实习|校招|春招|秋招|简历|resume)", raw, re.I)
    for match in file_name_matches:
        add_candidate(match, 35)

    if candidates:
        best_by_name = {}
        for score, name in candidates:
            best_by_name[name] = max(score, best_by_name.get(name, 0))
        return sorted(best_by_name.items(), key=lambda item: item[1], reverse=True)[0][0]
    return ""


def displayable_name(value):
    clean = str(value or "").strip()
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z\s]{2,20}", clean):
        return ""
    noise = (
        "待确认", "学生", "示例", "简历", "求职", "附件", "上传", "文件",
        "模板", "个人", "作品", "作品集", "暑期", "实习", "校招", "春招",
        "秋招", "应届", "毕业", "教育", "经历", "项目", "技能", "电话",
        "邮箱", "学校", "学院", "大学", "本科", "硕士", "博士", "研究生",
        "专业", "候选人", "求职者"
    )
    if any(word in clean for word in noise):
        return ""
    english_noise = (
        "sample", "resume", "cv", "student", "candidate", "applicant", "profile",
        "education", "experience", "project", "projects", "skill", "skills",
        "contact", "portfolio", "objective", "summary", "university", "school",
        "college", "bachelor", "master", "phone", "email"
    )
    if any(word in clean.lower() for word in english_noise):
        return ""
    return clean


def infer_target(text, preferences):
    role_pref = preferences.get("roles") or []
    if role_pref:
        return " / ".join(role_pref[:3])
    if any(word in text for word in ["社群", "用户", "活动"]):
        return "用户运营 / 内容运营 / 产品运营"
    if any(word in text for word in ["SQL", "数据", "Python"]):
        return "数据分析 / 商业分析"
    return "待探索岗位方向"


def keyword_hits(text, keywords):
    low = (text or "").lower()
    hits = []
    for key in keywords:
        if key.lower() in low:
            hits.append(key)
    return hits


JOBS = [
    {
        "id": "bytedance-op-sh",
        "title": "产品运营实习生",
        "company": "字节跳动",
        "city": "上海",
        "source": "企业官网",
        "method": "企业官网公开岗位",
        "url": "https://jobs.bytedance.com/",
        "updatedAt": "2026-06-06 14:30",
        "postedAt": "2026-06-02",
        "trust": "高",
        "status": "岗位页面可访问",
        "intensity": "高成长高强度",
        "keywords": ["产品运营", "用户调研", "数据分析", "内容运营", "复盘"],
        "jd": "支持产品运营策略落地，参与用户调研、内容策略、数据分析和活动复盘，要求沟通能力强、逻辑清晰、能适应快速迭代。"
    },
    {
        "id": "xiaohongshu-user-hz",
        "title": "用户运营实习生",
        "company": "小红书",
        "city": "杭州",
        "source": "企业官网",
        "method": "企业官网公开岗位",
        "url": "https://job.xiaohongshu.com/",
        "updatedAt": "2026-06-06 13:20",
        "postedAt": "2026-06-01",
        "trust": "高",
        "status": "岗位页面可访问",
        "intensity": "适中强度",
        "keywords": ["用户运营", "社群运营", "活动策划", "内容策划", "用户反馈"],
        "jd": "负责用户社群维护、活动策划、用户反馈收集和内容运营，要求有校园社群或内容平台运营经验。"
    },
    {
        "id": "tencent-content-sz",
        "title": "内容运营实习生",
        "company": "腾讯",
        "city": "深圳",
        "source": "企业官网",
        "method": "企业官网公开岗位",
        "url": "https://careers.tencent.com/",
        "updatedAt": "2026-06-06 12:10",
        "postedAt": "2026-05-29",
        "trust": "高",
        "status": "岗位页面可访问",
        "intensity": "适中强度",
        "keywords": ["内容运营", "选题策划", "数据复盘", "用户增长", "活动运营"],
        "jd": "参与内容选题、活动运营和数据复盘，关注用户增长和内容质量，要求表达能力好、执行力强。"
    },
    {
        "id": "boss-data-bj",
        "title": "商业数据分析实习生",
        "company": "成长型互联网公司",
        "city": "北京",
        "source": "BOSS 直聘",
        "method": "官方开放 API / 授权接口预留",
        "url": "https://www.zhipin.com/",
        "updatedAt": "2026-06-06 11:45",
        "postedAt": "2026-06-03",
        "trust": "中",
        "status": "需跳转原平台确认",
        "intensity": "稳定节奏",
        "keywords": ["数据分析", "Excel", "SQL", "业务分析", "可视化"],
        "jd": "支持业务数据整理、报表搭建、指标分析和专题研究，要求 Excel 熟练，有 SQL 或 BI 工具经验优先。"
    },
    {
        "id": "liepin-hr-gz",
        "title": "HR 实习生",
        "company": "互联网平台公司",
        "city": "广州",
        "source": "猎聘",
        "method": "第三方招聘数据服务",
        "url": "https://www.liepin.com/",
        "updatedAt": "2026-06-05 18:00",
        "postedAt": "2026-05-20",
        "trust": "待确认",
        "status": "发布时间较早，建议确认",
        "intensity": "稳定节奏",
        "keywords": ["招聘", "沟通", "候选人运营", "Excel", "流程管理"],
        "jd": "协助招聘流程推进、候选人沟通、面试安排和数据整理，要求细致、沟通能力好。"
    }
]


def all_jobs(db):
    return JOBS + db.get("custom_jobs", [])


def score_job(job, profile):
    profile = profile or {}
    prefs = profile.get("preferences") or {}
    skills = profile.get("skills") or []
    target = profile.get("target") or ""
    raw_text = profile.get("raw_text") or ""
    text = " ".join(skills + profile.get("strengths", []) + [target, raw_text]).lower()
    matched_keywords = [
        key for key in job.get("keywords", [])
        if key.lower() in text or any(key in skill or skill in key for skill in skills)
    ]
    score = 36 + min(len(matched_keywords) * 9, 36)
    target_tokens = [token for token in re.split(r"[ /、]+", target) if token and token != "待探索岗位方向"]
    if any(token in job.get("title", "") or token in job.get("jd", "") for token in target_tokens):
        score += 14
    cities = prefs.get("cities") or []
    roles = prefs.get("roles") or []
    intensity = prefs.get("intensity") or []
    traits = prefs.get("traits") or []
    mbti = (prefs.get("mbti") or "").upper()
    if any(city and (city in job.get("city", "") or job.get("city", "") in city or "全国" in city) for city in cities):
        score += 10
    if any(role and (role in job.get("title", "") or role in job.get("jd", "")) for role in roles):
        score += 12
    if any(item and (item in job.get("intensity", "") or job.get("intensity", "") in item) for item in intensity):
        score += 8
    if any(trait and trait in job.get("jd", "") for trait in traits):
        score += 4
    if mbti.startswith("E") and any(word in job.get("jd", "") for word in ["沟通", "用户", "社群", "活动"]):
        score += 3
    if mbti.startswith("I") and any(word in job.get("jd", "") for word in ["数据", "分析", "流程", "研究"]):
        score += 3
    if profile.get("portfolio_links"):
        score += 3
    if job.get("trust") == "高":
        score += 3
    missing = [key for key in job.get("keywords", []) if key not in matched_keywords]
    return min(96, max(42, score)), matched_keywords, missing


def match_jobs(db, filters=None):
    filters = filters or {}
    profile = db.get("profile")
    items = []
    for job in all_jobs(db):
        score, matched, missing = score_job(job, profile)
        item = dict(job)
        item["score"] = score
        item["matchedKeywords"] = matched or job.get("keywords", [])[:2]
        item["missingKeywords"] = missing
        item["aiConfidence"] = "高" if profile and score >= 80 else "中"
        item["recommendation"] = "强烈建议优先投递" if score >= 85 else "建议投递" if score >= 72 else "可作为备选"
        item["evidence"] = build_evidence(item, profile)
        items.append(item)
    query = (filters.get("query") or "").lower()
    source = filters.get("source") or ""
    trust = filters.get("trust") or ""
    if query:
        items = [j for j in items if query in f"{j['title']}{j['company']}{j['city']}{''.join(j['keywords'])}".lower()]
    if source:
        items = [j for j in items if j.get("source") == source]
    if trust:
        items = [j for j in items if j.get("trust") == trust]
    return sorted(items, key=lambda x: x["score"], reverse=True)


def build_evidence(job, profile):
    prefs = (profile or {}).get("preferences") or {}
    target = (profile or {}).get("target") or "未生成画像"
    return {
        "why": [
            f"命中关键词：{'、'.join(job.get('matchedKeywords') or job.get('keywords', [])[:2])}",
            f"画像目标方向：{target}",
            f"岗位来源为{job.get('source')}，数据方式：{job.get('method')}",
            "已将作品集作为加分参考。" if (profile or {}).get("portfolio_links") else "未提供作品集，不影响基础匹配。"
        ],
        "risks": [
            f"缺失或待强化关键词：{'、'.join(job.get('missingKeywords') or ['暂无明显缺口'])}",
            "投递前建议打开原始链接确认岗位仍在招。",
            "AI 只基于已上传信息判断，缺失偏好不会作为负面因素。"
        ],
        "preferenceNotes": [
            f"城市偏好：{'、'.join(prefs.get('cities') or ['未填写'])}",
            f"工作强度：{'、'.join(prefs.get('intensity') or ['未填写'])}",
            f"岗位方向：{'、'.join(prefs.get('roles') or ['未填写'])}"
        ]
    }


SECTION_WORDS = ["教育经历", "教育背景", "实习经历", "项目经历", "校园经历", "工作经历", "技能", "专业技能", "作品集", "证书", "荣誉"]


def is_section_heading(line):
    clean = line.strip().strip("：:")
    return clean in SECTION_WORDS or (len(clean) <= 8 and any(word in clean for word in SECTION_WORDS))


def optimize_line(line, job, missing):
    clean = line.strip()
    if not clean:
        return ""
    if is_section_heading(clean):
        return clean
    keywords = job.get("keywords", [])
    focus = "、".join(keywords[:3])
    has_metrics = bool(re.search(r"\d+[%+]?|提升|增长|转化|参与率|曝光|阅读|人次|次|篇|份|场", clean))
    if any(word in clean for word in ["负责", "参与", "协助", "项目", "运营", "活动", "用户", "内容", "数据", "调研"]):
        prefix = re.match(r"^([•\-·\d.、\s]+)", clean)
        bullet = prefix.group(1) if prefix else ""
        core = clean[len(bullet):].strip()
        if "负责" in core:
            core = core.replace("负责", "围绕目标岗位负责", 1)
        elif "参与" in core:
            core = core.replace("参与", "深度参与", 1)
        elif "协助" in core:
            core = core.replace("协助", "协助推进", 1)
        else:
            core = f"围绕{focus}优化：{core}"
        if not any(key in core for key in keywords):
            core = f"{core}，突出{focus}相关能力"
        if not has_metrics:
            core = f"{core}，补充可验证结果数据，如触达人数、转化率、产出数量或复盘结论"
        return f"{bullet}{core}"
    if "熟悉" in clean or "掌握" in clean:
        missing_text = "、".join(missing[:2])
        return f"{clean}；建议结合目标岗位补充项目使用场景{f'，优先体现{missing_text}' if missing_text else ''}"
    return clean


def build_resume_advice(profile, job, resume_text):
    raw = resume_text or ""
    profile_skills = "、".join((profile or {}).get("skills", []))
    matched = [key for key in job.get("keywords", []) if key in raw or key in profile_skills]
    missing = [key for key in job.get("keywords", []) if key not in matched]
    advice = [
        f"优先强化与「{job.get('title')}」直接相关的关键词：{'、'.join(job.get('keywords', [])[:4])}。",
        f"已命中关键词：{('、'.join(matched) if matched else '暂未明显命中')}；建议补强：{('、'.join(missing) if missing else '暂无明显缺口')}。",
        "每段经历建议改成“目标对象 + 关键动作 + 工具方法 + 真实结果 + 复盘沉淀”的结构。",
        "不要编造数据；如果暂时没有量化结果，请在对应经历中保留“补充真实数据”的提示，方便二次编辑。",
        "把最匹配目标岗位的经历前置，弱相关经历压缩为一行。"
    ]
    if (profile or {}).get("portfolio_links"):
        advice.append("已识别作品集链接，建议放在简历顶部联系方式附近，方便 HR 快速验证能力。")
    return advice


def enhance_resume_with_llm(profile, job, resume_text, fallback_lines, fallback_advice):
    prompt = f"""
你是一名资深校园招聘 HR 和简历顾问。请基于用户原简历和目标岗位，生成更有竞争力的优化版简历。
硬性要求：
1. 不虚构学校、公司、经历、证书、数据。
2. 尽量保留原简历段落顺序、标题结构和信息层级。
3. 如果缺少量化数据，用“待补充真实数据：...”提示，不要编造数字。
4. 输出 JSON，字段为 optimized_lines 和 advice。optimized_lines 是字符串数组，每项是一行简历内容；advice 是 5-8 条具体建议。

目标岗位：
{json.dumps(job, ensure_ascii=False)}

学生画像：
{json.dumps(profile or {}, ensure_ascii=False)}

原简历：
{resume_text[:7000]}

本地规则优化初稿：
{json.dumps(fallback_lines, ensure_ascii=False)}
"""
    data = extract_json_object(call_deepseek(prompt, 2200))
    if not data:
        return fallback_lines, fallback_advice
    lines = data.get("optimized_lines") if isinstance(data.get("optimized_lines"), list) else fallback_lines
    advice = data.get("advice") if isinstance(data.get("advice"), list) else fallback_advice
    lines = [str(line) for line in lines]
    advice = [str(item) for item in advice]
    return lines, advice


def optimized_resume_from_original(resume_text, profile, job):
    resume_text = (resume_text or "").strip()
    lines = resume_text.splitlines()
    profile_name = displayable_name((profile or {}).get("name"))
    if not any(line.strip() for line in lines):
        lines = [
            f"求职目标：{job.get('title', '目标岗位')}",
            f"核心关键词：{'、'.join(job.get('keywords', [])[:5])}",
            "项目经历：请补充与目标岗位相关的项目、实习或校园经历。",
            "技能：请补充真实掌握的工具、技能和证书。"
        ]
    profile_text = " ".join((profile or {}).get("skills", []) + [(profile or {}).get("raw_text", "")])
    missing = [key for key in job.get("keywords", []) if key not in profile_text]
    optimized = []
    inserted_target = False
    for index, line in enumerate(lines):
        if not line.strip():
            optimized.append("")
            continue
        clean_line = line.strip()
        is_name_line = bool(profile_name) and index <= 1 and clean_line == profile_name
        if not inserted_target and index <= 2 and len(clean_line) <= 28:
            if not is_name_line:
                optimized.append(clean_line)
            optimized.append(f"求职目标：{job.get('company', '')} · {job.get('title', '')}")
            optimized.append(f"岗位关键词：{'、'.join(job.get('keywords', [])[:5])}")
            portfolio = (profile or {}).get("portfolio_links") or []
            if portfolio:
                optimized.append(f"作品集：{portfolio[0]}")
            inserted_target = True
            continue
        optimized.append(optimize_line(line, job, missing))
    if not inserted_target:
        optimized.insert(0, f"求职目标：{job.get('company', '')} · {job.get('title', '')}")
        optimized.insert(1, f"岗位关键词：{'、'.join(job.get('keywords', [])[:5])}")
    return optimized


def resume_lines_to_html(lines, name):
    clean_name = displayable_name(name)
    body = ["<div class=\"resume-doc\">"]
    if clean_name:
        body.append(f"<h1>{html.escape(clean_name)}</h1>")
    for index, line in enumerate(lines):
        clean_line = str(line or "").strip()
        line_without_label = re.sub(r"^\s*姓名\s*[:：]\s*", "", clean_line)
        if clean_name and index <= 2 and line_without_label == clean_name:
            continue
        if not line:
            body.append("<p class=\"resume-gap\">&nbsp;</p>")
        elif is_section_heading(line):
            body.append(f"<h2>{html.escape(line)}</h2>")
        else:
            body.append(f"<p>{html.escape(line)}</p>")
    body.append("</div>")
    return "\n".join(body)


def optimize_resume(profile, job, resume=None):
    name = displayable_name((profile or {}).get("name"))
    resume_text = (resume or {}).get("text", "")
    optimized_lines = optimized_resume_from_original(resume_text, profile, job)
    return resume_lines_to_html(optimized_lines, name)


def write_doc(html_body, session_id=None):
    name = f"Mary-optimized-{int(time.time())}.doc"
    path = outputs_dir(session_id) / name
    content = f"""<html><head><meta charset="UTF-8"><title>优化版简历</title><style>
body {{ font-family: Arial, "Microsoft YaHei", sans-serif; color: #172033; }}
.resume-doc {{ width: 720px; margin: 0 auto; line-height: 1.45; font-size: 11pt; }}
h1 {{ font-size: 18pt; text-align: center; margin: 0 0 10px; }}
h2 {{ font-size: 12pt; margin: 12px 0 6px; padding-bottom: 3px; border-bottom: 1px solid #b8c2e0; color: #314a9f; }}
p {{ margin: 3px 0; }}
.resume-gap {{ height: 6px; }}
</style></head><body>{html_body}</body></html>"""
    path.write_text(content, encoding="utf-8")
    return name


def interview_pack(profile, job):
    name = displayable_name((profile or {}).get("name"))
    intro_prefix = f"你好，我是{name}，关注{job.get('title')}方向" if name else f"你好，我关注{job.get('title')}方向"
    return {
        "title": f"{job.get('company')} · {job.get('title')} 面试准备包",
        "selfIntro": f"{intro_prefix}，具备{('、'.join((profile or {}).get('strengths', [])[:4]) or '项目协作、学习能力')}等经历，希望结合岗位需求进一步沟通。",
        "questions": [
            "请介绍一个你最有代表性的项目经历。",
            "你如何判断一次运营活动是否成功？",
            "如果岗位要求的数据能力你还不熟，你会如何补齐？",
            "你如何处理用户反馈和业务目标之间的冲突？"
        ],
        "opening": f"你好，我对贵公司的{job.get('title')}很感兴趣。我有相关项目/实习经历，已根据岗位要求准备简历，期待进一步沟通。"
    }


def make_upload_record(kind, original=None, content=b"", pasted_text=""):
    record = {
        "id": f"{kind}-{int(time.time() * 1000)}",
        "kind": kind,
        "originalName": None,
        "storedName": None,
        "text": pasted_text,
        "links": extract_links(pasted_text),
        "warnings": [],
        "contentKind": classify_content(pasted_text),
        "uploadedAt": now_text()
    }
    if original:
        stored = f"{int(time.time() * 1000)}-{safe_name(original)}"
        path = UPLOADS / stored
        path.write_bytes(content)
        parsed = extract_text(path, original)
        if parsed.get("text"):
            record["text"] = " ".join([pasted_text, parsed["text"]]).strip()
        record.update({
            "originalName": original,
            "storedName": stored,
            "fileType": parsed.get("fileType"),
            "parser": parsed.get("parser"),
            "links": sorted(set((record.get("links") or []) + parsed.get("links", []))),
            "warnings": parsed.get("warnings", []),
            "qrHints": parsed.get("qrHints", []),
            "contentKind": classify_content(record.get("text", ""), original)
        })
    return record


def build_flask_app():
    if Flask is None:
        return None
    app = Flask(__name__)

    def current_session_id():
        sid = request.cookies.get("mary_session")
        return sid or secrets.token_urlsafe(18)

    def respond(payload, status=200, sid=None):
        response = make_response(jsonify(payload), status)
        response.set_cookie("mary_session", sid or current_session_id(), httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 30)
        return response

    @app.get("/")
    @app.get("/index.html")
    def flask_index():
        return send_from_directory(ROOT, "index.html")

    @app.get("/styles.css")
    @app.get("/app.js")
    def flask_static():
        return send_from_directory(ROOT, request.path.lstrip("/"))

    @app.get("/api/state")
    def flask_state():
        sid = current_session_id()
        return respond({"ok": True, "data": load_db(sid)}, sid=sid)

    @app.get("/api/jobs")
    def flask_jobs():
        sid = current_session_id()
        return respond({"ok": True, "jobs": match_jobs(load_db(sid), dict(request.args))}, sid=sid)

    @app.get("/api/download")
    def flask_download():
        sid = current_session_id()
        name = safe_name(request.args.get("file", ""))
        path = outputs_dir(sid) / name
        if not path.exists():
            return respond({"ok": False, "error": "文件不存在"}, 404, sid=sid)
        return send_file(path, mimetype="application/msword", as_attachment=True, download_name=name)

    @app.post("/api/upload")
    def flask_upload():
        sid = current_session_id()
        db = load_db(sid)
        kind = request.form.get("kind") or "resume"
        pasted_text = request.form.get("text") or ""
        file_item = request.files.get("file")
        record = make_upload_record(
            kind,
            file_item.filename if file_item else None,
            file_item.read() if file_item else b"",
            pasted_text
        )
        if kind == "resume":
            old_resume = db.get("resume") or {}
            old_stored = old_resume.get("storedName")
            if old_stored:
                old_path = uploads_dir(sid) / safe_name(old_stored)
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
            if record.get("storedName"):
                src = UPLOADS / safe_name(record["storedName"])
                dst = uploads_dir(sid) / safe_name(record["storedName"])
                if src.exists():
                    shutil.move(str(src), str(dst))
            db["resume"] = record
            db["profile"] = None
        else:
            if record.get("storedName"):
                src = UPLOADS / safe_name(record["storedName"])
                dst = uploads_dir(sid) / safe_name(record["storedName"])
                if src.exists():
                    shutil.move(str(src), str(dst))
            db.setdefault("portfolio", []).append(record)
        save_db(db, sid)
        return respond({"ok": True, "record": record}, sid=sid)

    @app.post("/api/use-sample")
    def flask_use_sample():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        old_resume = db.get("resume") or {}
        old_stored = old_resume.get("storedName")
        if old_stored:
            old_path = uploads_dir(sid) / safe_name(old_stored)
            if old_path.exists():
                try:
                    old_path.unlink()
                except OSError:
                    pass
        text = payload.get("text") or ""
        db["resume"] = {
            "id": f"resume-{int(time.time() * 1000)}",
            "kind": "resume",
            "originalName": "示例简历",
            "storedName": None,
            "text": text,
            "links": extract_links(text),
            "warnings": [],
            "contentKind": "resume",
            "uploadedAt": now_text()
        }
        db["profile"] = None
        save_db(db, sid)
        return respond({"ok": True, "record": db["resume"]}, sid=sid)

    @app.post("/api/profile")
    def flask_profile():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        preferences = payload.get("preferences") or {}
        resume_text_override = (payload.get("resumeText") or "").strip()
        if resume_text_override:
            current = db.get("resume") or {
                "id": f"resume-{int(time.time() * 1000)}",
                "kind": "resume",
                "originalName": "粘贴文本简历",
                "storedName": None,
                "text": "",
                "links": [],
                "warnings": [],
                "contentKind": "resume",
                "uploadedAt": now_text()
            }
            existing_text = current.get("text") or ""
            if resume_text_override not in existing_text:
                current["text"] = " ".join([existing_text, resume_text_override]).strip()
            current["links"] = sorted(set((current.get("links") or []) + extract_links(resume_text_override)))
            current["contentKind"] = classify_content(current.get("text", ""), current.get("originalName", ""))
            db["resume"] = current
        profile = build_profile(db.get("resume"), db.get("portfolio", []), preferences)
        profile = enhance_profile_with_llm(profile, profile.get("raw_text", ""), preferences)
        db["profile"] = profile
        save_db(db, sid)
        return respond({"ok": True, "profile": profile}, sid=sid)

    @app.post("/api/custom-job")
    def flask_custom_job():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return respond({"ok": False, "error": "请先粘贴岗位链接或 JD"}, 400, sid=sid)
        is_link = text.startswith("http")
        job = {
            "id": f"custom-{int(time.time() * 1000)}",
            "title": "用户提供链接岗位" if is_link else "用户粘贴 JD 岗位",
            "company": "待确认公司",
            "city": "待确认",
            "source": "用户主动提供",
            "method": "用户粘贴岗位链接或 JD",
            "url": text if is_link else "#",
            "updatedAt": now_text(),
            "postedAt": "待确认",
            "trust": "中" if is_link else "待确认",
            "status": "需跳转原链接校验" if is_link else "JD 文本完整性待确认",
            "intensity": "待确认",
            "keywords": keyword_hits(text, ["产品", "运营", "数据", "分析", "用户", "内容", "市场", "设计", "前端", "后端"]) or ["岗位要求", "项目经历", "技能匹配"],
            "jd": text[:600]
        }
        db.setdefault("custom_jobs", []).append(job)
        save_db(db, sid)
        return respond({"ok": True, "job": job}, sid=sid)

    @app.post("/api/optimize")
    def flask_optimize():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None) or match_jobs(db)[0]
        resume_text = (db.get("resume") or {}).get("text", "")
        fallback_lines = optimized_resume_from_original(resume_text, db.get("profile"), job)
        fallback_advice = build_resume_advice(db.get("profile"), job, resume_text)
        lines, advice = enhance_resume_with_llm(db.get("profile"), job, resume_text, fallback_lines, fallback_advice)
        body = resume_lines_to_html(lines, (db.get("profile") or {}).get("name"))
        file_name = write_doc(body, sid)
        return respond({"ok": True, "html": body, "advice": advice, "download": f"/api/download?file={file_name}", "fileName": file_name}, sid=sid)

    @app.post("/api/save-job")
    def flask_save_job():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None)
        if not job:
            return respond({"ok": False, "error": "岗位不存在"}, 404, sid=sid)
        saved = db.setdefault("saved_jobs", [])
        if not any(item.get("jobId") == job_id for item in saved):
            saved.append({"jobId": job_id, "status": "感兴趣", "savedAt": now_text(), "job": job})
        save_db(db, sid)
        return respond({"ok": True, "savedJobs": saved}, sid=sid)

    @app.post("/api/update-job-status")
    def flask_update_job_status():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("jobId")
        status = payload.get("status")
        if status not in KANBAN_STATUSES:
            return respond({"ok": False, "error": "状态不合法"}, 400, sid=sid)
        for item in db.setdefault("saved_jobs", []):
            if item.get("jobId") == job_id:
                item["status"] = status
                item["updatedAt"] = now_text()
        save_db(db, sid)
        return respond({"ok": True, "savedJobs": db.get("saved_jobs", [])}, sid=sid)

    @app.post("/api/delete-saved-job")
    def flask_delete_saved_job():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("jobId")
        db["saved_jobs"] = [item for item in db.get("saved_jobs", []) if item.get("jobId") != job_id]
        save_db(db, sid)
        return respond({"ok": True, "savedJobs": db.get("saved_jobs", [])}, sid=sid)

    @app.post("/api/interview")
    def flask_interview():
        sid = current_session_id()
        db = load_db(sid)
        payload = request.get_json(silent=True) or {}
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None)
        if not job:
            return respond({"ok": False, "error": "请先选择看板中的岗位"}, 404, sid=sid)
        return respond({"ok": True, "pack": interview_pack(db.get("profile"), job)}, sid=sid)

    return app


app = build_flask_app()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def ensure_session(self):
        if getattr(self, "session_id", None):
            return self.session_id
        cookie = self.headers.get("Cookie", "")
        match = re.search(r"(?:^|;\s*)mary_session=([A-Za-z0-9_\-]+)", cookie)
        self.session_id = match.group(1) if match else secrets.token_urlsafe(18)
        return self.session_id

    def do_GET(self):
        self.ensure_session()
        parsed = urlparse(self.path)
        safe_static = {"/", "/index.html", "/styles.css", "/app.js"}
        if parsed.path == "/api/state":
            db = load_db(self.session_id)
            return json_response(self, {"ok": True, "data": db})
        if parsed.path == "/api/jobs":
            db = load_db(self.session_id)
            filters = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            return json_response(self, {"ok": True, "jobs": match_jobs(db, filters)})
        if parsed.path == "/api/download":
            qs = parse_qs(parsed.query)
            name = safe_name((qs.get("file") or [""])[0])
            path = outputs_dir(self.session_id) / name
            if not path.exists():
                return json_response(self, {"ok": False, "error": "文件不存在"}, 404)
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/msword")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path not in safe_static:
            return json_response(self, {"ok": False, "error": "Not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        self.ensure_session()
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            return self.handle_upload()
        if parsed.path == "/api/use-sample":
            return self.handle_use_sample()
        if parsed.path == "/api/profile":
            return self.handle_profile()
        if parsed.path == "/api/custom-job":
            return self.handle_custom_job()
        if parsed.path == "/api/optimize":
            return self.handle_optimize()
        if parsed.path == "/api/save-job":
            return self.handle_save_job()
        if parsed.path == "/api/update-job-status":
            return self.handle_update_job_status()
        if parsed.path == "/api/delete-saved-job":
            return self.handle_delete_saved_job()
        if parsed.path == "/api/interview":
            return self.handle_interview()
        return json_response(self, {"ok": False, "error": "Unknown API"}, 404)

    def post_json(self):
        raw = read_body(self)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def handle_upload(self):
        db = load_db(self.session_id)
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return json_response(self, {"ok": False, "error": "请使用 multipart/form-data 上传"}, 400)
        fields, files = parse_multipart(self.headers, read_body(self))
        kind = fields.get("kind") or "resume"
        pasted_text = fields.get("text") or ""
        file_item = files.get("file")
        record = {
            "id": f"{kind}-{int(time.time() * 1000)}",
            "kind": kind,
            "originalName": None,
            "storedName": None,
            "text": pasted_text,
            "links": extract_links(pasted_text),
            "warnings": [],
            "contentKind": classify_content(pasted_text),
            "uploadedAt": now_text()
        }
        if file_item is not None and file_item.get("filename"):
            original = safe_name(file_item["filename"])
            stored = f"{int(time.time() * 1000)}-{original}"
            path = uploads_dir(self.session_id) / stored
            path.write_bytes(file_item.get("content", b""))
            parsed = extract_text(path, original)
            merged_text = " ".join([parsed.get("text", ""), pasted_text]).strip()
            record.update({
                "originalName": original,
                "storedName": stored,
                "text": merged_text,
                "links": sorted(set(parsed.get("links", []) + extract_links(pasted_text))),
                "warnings": parsed.get("warnings", []),
                "parser": parsed.get("parser"),
                "fileType": parsed.get("file_type"),
                "qrHints": parsed.get("qr_hints", []),
                "contentKind": classify_content(merged_text, original)
            })
        if kind == "resume":
            old_resume = db.get("resume") or {}
            old_stored = old_resume.get("storedName")
            if old_stored:
                old_path = uploads_dir(self.session_id) / safe_name(old_stored)
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
            db["resume"] = record
            db["profile"] = None
        else:
            db["portfolio"].append(record)
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "record": record})

    def handle_profile(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        preferences = payload.get("preferences") or {}
        resume_text_override = (payload.get("resumeText") or "").strip()
        if resume_text_override:
            current = db.get("resume") or {
                "id": f"resume-{int(time.time() * 1000)}",
                "kind": "resume",
                "originalName": "粘贴文本简历",
                "storedName": None,
                "links": [],
                "warnings": [],
                "contentKind": "resume",
                "uploadedAt": now_text()
            }
            existing_text = current.get("text") or ""
            if resume_text_override not in existing_text:
                current["text"] = " ".join([existing_text, resume_text_override]).strip()
            current["links"] = sorted(set((current.get("links") or []) + extract_links(resume_text_override)))
            current["contentKind"] = classify_content(current.get("text", ""), current.get("originalName", ""))
            db["resume"] = current
        profile = build_profile(db.get("resume"), db.get("portfolio", []), preferences)
        profile = enhance_profile_with_llm(profile, profile.get("raw_text", ""), preferences)
        db["profile"] = profile
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "profile": profile})

    def handle_use_sample(self):
        db = load_db(self.session_id)
        old_resume = db.get("resume") or {}
        old_stored = old_resume.get("storedName")
        if old_stored:
            old_path = uploads_dir(self.session_id) / safe_name(old_stored)
            if old_path.exists():
                try:
                    old_path.unlink()
                except OSError:
                    pass
        payload = self.post_json()
        text = payload.get("text") or ""
        db["resume"] = {
            "id": f"resume-{int(time.time() * 1000)}",
            "kind": "resume",
            "originalName": "示例简历",
            "storedName": None,
            "text": text,
            "links": extract_links(text),
            "warnings": [],
            "contentKind": "resume",
            "uploadedAt": now_text()
        }
        db["profile"] = None
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "record": db["resume"]})

    def handle_custom_job(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        text = (payload.get("text") or "").strip()
        if not text:
            return json_response(self, {"ok": False, "error": "请粘贴岗位链接或 JD"}, 400)
        is_link = text.startswith("http://") or text.startswith("https://")
        job = {
            "id": f"custom-{int(time.time() * 1000)}",
            "title": "用户提供链接岗位" if is_link else "用户粘贴 JD 岗位",
            "company": "待确认公司",
            "city": "待确认",
            "source": "用户主动提供",
            "method": "用户粘贴岗位链接或 JD",
            "url": text if is_link else "#",
            "updatedAt": now_text(),
            "postedAt": "待确认",
            "trust": "中" if is_link else "待确认",
            "status": "需后端访问原链接校验" if is_link else "JD 文本完整性待确认",
            "intensity": "待确认",
            "keywords": ["岗位要求", "项目经历", "技能匹配", "简历优化"],
            "jd": text[:300]
        }
        db["custom_jobs"].append(job)
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "job": job})

    def handle_optimize(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None) or match_jobs(db)[0]
        resume_text = (db.get("resume") or {}).get("text", "")
        fallback_lines = optimized_resume_from_original(resume_text, db.get("profile"), job)
        fallback_advice = build_resume_advice(db.get("profile"), job, resume_text)
        lines, advice = enhance_resume_with_llm(db.get("profile"), job, resume_text, fallback_lines, fallback_advice)
        body = resume_lines_to_html(lines, (db.get("profile") or {}).get("name"))
        file_name = write_doc(body, self.session_id)
        return json_response(self, {"ok": True, "html": body, "advice": advice, "download": f"/api/download?file={file_name}", "fileName": file_name})

    def handle_save_job(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None)
        if not job:
            return json_response(self, {"ok": False, "error": "岗位不存在"}, 404)
        normalize_saved_jobs(db)
        if not any(item.get("jobId") == job_id for item in db["saved_jobs"]):
            db["saved_jobs"].append({
                "id": f"app-{int(time.time() * 1000)}",
                "jobId": job_id,
                "status": payload.get("status") or "感兴趣",
                "savedAt": now_text(),
                "job": job
            })
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "savedJobs": db["saved_jobs"]})

    def handle_update_job_status(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        job_id = payload.get("jobId")
        status = payload.get("status")
        if status not in KANBAN_STATUSES:
            return json_response(self, {"ok": False, "error": "未知投递状态"}, 400)
        normalize_saved_jobs(db)
        for item in db["saved_jobs"]:
            if item.get("jobId") == job_id:
                item["status"] = status
                item["updatedAt"] = now_text()
                save_db(db, self.session_id)
                return json_response(self, {"ok": True, "savedJobs": db["saved_jobs"]})
        return json_response(self, {"ok": False, "error": "岗位不在投递清单中"}, 404)

    def handle_delete_saved_job(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        job_id = payload.get("jobId")
        normalize_saved_jobs(db)
        db["saved_jobs"] = [item for item in db["saved_jobs"] if item.get("jobId") != job_id]
        save_db(db, self.session_id)
        return json_response(self, {"ok": True, "savedJobs": db["saved_jobs"]})

    def handle_interview(self):
        db = load_db(self.session_id)
        payload = self.post_json()
        job_id = payload.get("jobId")
        job = next((j for j in all_jobs(db) if j.get("id") == job_id), None)
        if not job:
            normalize_saved_jobs(db)
            first_saved = db.get("saved_jobs", [None])[0]
            job = (first_saved or {}).get("job") if isinstance(first_saved, dict) else first_saved
            job = job or match_jobs(db)[0]
        return json_response(self, {"ok": True, "pack": interview_pack(db.get("profile"), job)})


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Mary demo backend running on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
