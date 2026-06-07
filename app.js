const state = {
  resume: null,
  portfolio: [],
  profile: null,
  selectedJob: null,
  savedJobs: [],
  customJobs: [],
  jobs: [],
  downloadUrl: null,
  apiOnline: false,
  isUploadingResume: false,
  loadedSample: false,
  preferredName: "",
  hideName: false,
  pendingNameDialog: null,
  saveJumpCount: Number(localStorage.getItem("marySaveJumpCount") || "0"),
  saveJumpPreference: localStorage.getItem("marySaveJumpPreference") || ""
};

const API_BASE = "";

const sampleResume = `王同学
上海某大学 新闻传播学 本科 2027 届
求职方向：用户运营、内容运营、产品运营实习
实习经历：某校园社区 App 用户运营实习生，负责 4 个学生社群日常运营，策划线上活动，整理用户反馈并输出复盘报告。
项目经历：校园二手交易小程序增长项目，负责用户调研、活动策划、内容发布和数据复盘。
技能：Excel、问卷调研、内容策划、社群运营、数据分析、Canva、飞书文档
作品集：https://portfolio.example.com/mary-student`;

const sampleJobs = [
  {
    id: "bytedance-op-sh",
    title: "产品运营实习生",
    company: "字节跳动",
    city: "上海",
    source: "企业官网",
    method: "企业官网公开岗位",
    url: "https://jobs.bytedance.com/",
    updatedAt: "2026-06-06 14:30",
    postedAt: "2026-06-02",
    trust: "高",
    status: "岗位页面可访问",
    intensity: "高成长高强度",
    keywords: ["产品运营", "用户调研", "数据分析", "内容运营", "复盘"],
    jd: "支持产品运营策略落地，参与用户调研、内容策略、数据分析和活动复盘，要求沟通能力强、逻辑清晰、能适应快速迭代。"
  },
  {
    id: "xiaohongshu-user-hz",
    title: "用户运营实习生",
    company: "小红书",
    city: "杭州",
    source: "企业官网",
    method: "企业官网公开岗位",
    url: "https://job.xiaohongshu.com/",
    updatedAt: "2026-06-06 13:20",
    postedAt: "2026-06-01",
    trust: "高",
    status: "岗位页面可访问",
    intensity: "适中强度",
    keywords: ["用户运营", "社群运营", "活动策划", "内容策划", "用户反馈"],
    jd: "负责用户社群维护、活动策划、用户反馈收集和内容运营，要求有校园社群或内容平台运营经验。"
  },
  {
    id: "tencent-content-sz",
    title: "内容运营实习生",
    company: "腾讯",
    city: "深圳",
    source: "企业官网",
    method: "企业官网公开岗位",
    url: "https://careers.tencent.com/",
    updatedAt: "2026-06-06 12:10",
    postedAt: "2026-05-29",
    trust: "高",
    status: "岗位页面可访问",
    intensity: "适中强度",
    keywords: ["内容运营", "选题策划", "数据复盘", "用户增长", "活动运营"],
    jd: "参与内容选题、活动运营和数据复盘，关注用户增长和内容质量，要求表达能力好、执行力强。"
  },
  {
    id: "boss-data-bj",
    title: "商业数据分析实习生",
    company: "成长型互联网公司",
    city: "北京",
    source: "BOSS 直聘",
    method: "官方开放 API / 授权接口预留",
    url: "https://www.zhipin.com/",
    updatedAt: "2026-06-06 11:45",
    postedAt: "2026-06-03",
    trust: "中",
    status: "需跳转原平台确认",
    intensity: "稳定节奏",
    keywords: ["数据分析", "Excel", "SQL", "业务分析", "可视化"],
    jd: "支持业务数据整理、报表搭建、指标分析和专题研究，要求 Excel 熟练，有 SQL 或 BI 工具经验优先。"
  },
  {
    id: "liepin-hr-gz",
    title: "HR 实习生",
    company: "互联网平台公司",
    city: "广州",
    source: "猎聘",
    method: "第三方招聘数据服务",
    url: "https://www.liepin.com/",
    updatedAt: "2026-06-05 18:00",
    postedAt: "2026-05-20",
    trust: "待确认",
    status: "发布时间较早，建议确认",
    intensity: "稳定节奏",
    keywords: ["招聘", "沟通", "候选人运营", "Excel", "流程管理"],
    jd: "协助招聘流程推进、候选人沟通、面试安排和数据整理，要求细致、沟通能力好。"
  }
];

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "请求失败");
  }
  state.apiOnline = true;
  return data;
}

function showStep(id) {
  $$(".panel").forEach((panel) => panel.classList.toggle("visible", panel.id === id));
  $$(".step").forEach((step) => step.classList.toggle("active", step.dataset.step === id));
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function status(containerId, text, type = "") {
  const node = document.createElement("div");
  node.className = `status ${type}`;
  const span = document.createElement("span");
  span.textContent = text;
  node.append(span);
  $(`#${containerId}`)?.prepend(node);
}

function clearStatus(containerId) {
  const container = $(`#${containerId}`);
  if (container) container.innerHTML = "";
}

function setStatus(containerId, text, type = "") {
  clearStatus(containerId);
  status(containerId, text, type);
}

function showToast(text) {
  let toast = $("#toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.append(toast);
  }
  toast.textContent = text;
  toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function detectResumeLike(text, fileName = "") {
  const content = `${fileName} ${text}`.toLowerCase();
  const resumeSignals = ["简历", "resume", "教育", "实习", "项目", "技能", "经历", "求职", "专业", "本科", "硕士"];
  const otherSignals = ["成绩单", "证书", "合同", "论文", "发票", "身份证"];
  const resumeScore = resumeSignals.filter((word) => content.includes(word)).length;
  const otherScore = otherSignals.filter((word) => content.includes(word)).length;
  if (resumeScore >= 2) return "resume";
  if (otherScore >= 1 && resumeScore === 0) return "supplement";
  return "unknown";
}

function inferClientName(text) {
  const raw = text || "";
  const candidates = [];
  const add = (value, score) => {
    const clean = String(value || "").replace(/^(姓名|名字|Name|name)\s*[:：]?\s*/, "").trim();
    if (displayableName(clean)) candidates.push([score, clean]);
  };
  [
    /(?:姓名|名字|Name|name)\s*[:： ]\s*([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})/g,
    /([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*(?:\+?86)?1[3-9]\d{9}/g,
    /([\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*[|｜]\s*(?:本科|硕士|博士|研究生|应届|求职|电话|邮箱)/g
  ].forEach((pattern) => {
    for (const match of raw.matchAll(pattern)) add(match[1], 100);
  });
  raw.split(/\n+/).filter(Boolean).slice(0, 12).forEach((line, index) => {
    const clean = line.replace(/^[#>*\-\s·•]+/, "").replace(/\s+/g, " ").trim();
    if (/https?|@|电话|邮箱|求职意向|教育背景|教育经历|实习经历|项目经历|技能|作品集|自我评价|校园经历|证书|获奖|学校|专业|本科|硕士|博士|education|experience|projects?|skills?|contact|portfolio|objective|summary|university|school|college|bachelor|master|phone|email/i.test(clean)) return;
    add(clean, 90 - index * 5);
    add(clean.split(/[|｜,，；;/(（\s]/)[0], 82 - index * 5);
    const tokens = clean.match(/[\u4e00-\u9fff]{2,4}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}/g) || [];
    tokens.forEach((token) => add(token, 70 - index * 4));
  });
  const best = candidates.reduce((map, [score, name]) => {
    map.set(name, Math.max(score, map.get(name) || 0));
    return map;
  }, new Map());
  return [...best.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "";
}

function displayableName(value) {
  const clean = String(value || "").trim();
  const invalid = /(待确认|学生|示例|简历|求职|附件|上传|文件|模板|作品集|暑期|实习|校招|春招|秋招|教育|经历|项目|技能|电话|邮箱|学校|学院|大学|本科|硕士|博士|研究生|专业|候选人|求职者)/;
  const englishInvalid = /(sample|resume|cv|student|candidate|applicant|profile|education|experience|projects?|skills?|contact|portfolio|objective|summary|university|school|college|bachelor|master|phone|email)/i;
  if (!/^[\u4e00-\u9fffA-Za-z\s]{2,20}$/.test(clean)) return "";
  return invalid.test(clean) || englishInvalid.test(clean) ? "" : clean;
}

function setPreferredName(name) {
  state.preferredName = displayableName(name);
  state.hideName = !state.preferredName;
  if (state.profile) {
    state.profile.name = state.preferredName || "";
    applyProfileToUI(state.profile);
  }
}

function activeDisplayName(profileName = "") {
  if (state.hideName) return "";
  return displayableName(state.preferredName) || displayableName(profileName);
}

function askPreferredName(defaultName = "") {
  const dialog = $("#nameDialog");
  const input = $("#preferredNameInput");
  if (!dialog || !input) return Promise.resolve("");
  input.value = "";
  dialog.hidden = false;
  window.setTimeout(() => input.focus(), 50);
  return new Promise((resolve) => {
    state.pendingNameDialog = resolve;
  });
}

function closePreferredNameDialog(value) {
  const dialog = $("#nameDialog");
  if (dialog) dialog.hidden = true;
  const resolve = state.pendingNameDialog;
  state.pendingNameDialog = null;
  if (resolve) resolve(displayableName(value));
}

function extractLinks(text) {
  const links = text.match(/https?:\/\/[^\s，。)）]+/g) || [];
  const qrHint = /二维码|qr|code/i.test(text) ? ["检测到二维码提示：Demo 中会交给后端二维码识别服务解析"] : [];
  return [...links, ...qrHint];
}

function readTextFile(file, callback) {
  const reader = new FileReader();
  reader.onload = () => callback(String(reader.result || ""));
  reader.onerror = () => callback("");
  reader.readAsText(file);
}

async function uploadToBackend(kind, file, text = "") {
  const form = new FormData();
  form.append("kind", kind);
  form.append("text", text || "");
  if (file) form.append("file", file);
  return api("/api/upload", { method: "POST", body: form });
}

function resetProfileView() {
  state.profile = null;
  state.selectedJob = null;
  state.downloadUrl = null;
  $("#candidateName").textContent = "待生成画像";
  $("#candidateSummary").textContent = "已收到新的简历材料。请点击“下一步：生成画像”，Mary 会基于当前简历重新生成画像。";
  $("#profileCompleteness").textContent = "0";
  $("#confidenceGrid").innerHTML = "";
  $("#optimizedPreview").textContent = "选择一个岗位后点击“一键优化并预览”。系统会保留真实经历，只优化表达，并标记需要用户补充的数据。";
  $("#downloadDoc").disabled = true;
}

async function handleResumeFile(file) {
  if (!file) return;
  state.preferredName = "";
  state.hideName = false;
  if ($("#resumeText").value.trim()) {
    $("#resumeText").value = "";
    state.loadedSample = false;
  }
  const ext = file.name.split(".").pop().toLowerCase();
  const supported = ["doc", "docx", "pdf", "jpg", "jpeg", "png", "txt", "md"];
  if (!supported.includes(ext)) {
    setStatus("resumeStatus", "这个格式暂时无法识别。请上传 Word、PDF、图片简历，或直接粘贴简历文本。", "bad");
    return;
  }
  state.isUploadingResume = true;
  $("#goProfile").disabled = true;
  setStatus("resumeStatus", `正在上传并解析 ${file.name}，请稍候。`, "");
  try {
    const data = await uploadToBackend("resume", file, $("#resumeText").value);
    state.resume = {
      name: data.record.originalName || data.record.id,
      type: data.record.fileType || "text",
      text: data.record.text || $("#resumeText").value || file.name,
      kind: data.record.contentKind,
      links: data.record.links || []
    };
    resetProfileView();
    setStatus("resumeStatus", `已完成 ${file.name} 的上传与解析。解析器：${data.record.parser || "文本兜底"}。`, "good");
    if (!data.record.text || data.record.text.trim().length < 30) {
      status("resumeStatus", "这份文件的可提取文本较少。你仍然可以生成待确认画像，但建议在下方文本框粘贴简历正文，让画像更准确。", "warn");
    }
    (data.record.warnings || []).forEach((item) => status("resumeStatus", item, "warn"));
    (data.record.qrHints || []).forEach((item) => status("resumeStatus", item, "warn"));
    askPreferredName().then(setPreferredName);
    return;
  } catch (error) {
    setStatus("resumeStatus", `后端暂不可用，已切换前端兜底识别：${error.message}`, "warn");
  } finally {
    state.isUploadingResume = false;
    $("#goProfile").disabled = false;
  }
  const finish = (fileText = "") => {
    const baseText = `${file.name} ${fileText} ${$("#resumeText").value}`;
    const kind = detectResumeLike(baseText, file.name);
    state.resume = {
      name: file.name,
      type: ext,
      text: baseText,
      kind,
      links: extractLinks(baseText)
    };
    resetProfileView();
    if (["pdf", "jpg", "jpeg", "png"].includes(ext)) {
      setStatus("resumeStatus", `已接收 ${file.name}。正式版会自动 OCR 识别扫描件/图片文字；如识别不完整，可在文本框粘贴简历内容增强准确度。`, "good");
    } else if (["txt", "md"].includes(ext)) {
      setStatus("resumeStatus", `已读取 ${file.name} 的文本内容，可以进入下一步生成画像。`, "good");
    } else {
      setStatus("resumeStatus", `已接收 ${file.name}。正式版会解析 Word 结构；Demo 中也支持你粘贴文本来增强画像准确度。`, "good");
    }
    if (kind === "supplement") {
      status("resumeStatus", "我识别到它更像补充材料，不像完整简历。你仍可继续，但建议再上传简历或粘贴简历文本。", "warn");
    }
    askPreferredName().then(setPreferredName);
  };
  if (["txt", "md"].includes(ext)) {
    readTextFile(file, finish);
  } else {
    finish();
  }
}

async function handlePortfolioFiles(files) {
  state.portfolio = [];
  for (const file of Array.from(files || [])) {
    const ext = file.name.split(".").pop().toLowerCase();
    try {
      const data = await uploadToBackend("portfolio", file, $("#portfolioText").value);
      state.portfolio.push({
        name: data.record.originalName || file.name,
        type: data.record.fileType || ext,
        links: data.record.links || [],
        text: data.record.text || ""
      });
      status("portfolioStatus", `后端已保存作品集材料 ${file.name}。${(data.record.links || []).length ? `识别到链接：${data.record.links.join("、")}` : "作品集为选填，不影响下一步。"}`, "good");
      (data.record.warnings || []).forEach((item) => status("portfolioStatus", item, "warn"));
      (data.record.qrHints || []).forEach((item) => status("portfolioStatus", item, "warn"));
      continue;
    } catch (error) {
      status("portfolioStatus", `后端暂不可用，已切换前端兜底保存：${error.message}`, "warn");
    }
    const addPortfolio = (text = "") => {
      const links = extractLinks(`${file.name} ${text}`);
      state.portfolio.push({ name: file.name, type: ext, links });
      if (["jpg", "jpeg", "png", "pdf"].includes(ext)) {
        status("portfolioStatus", `已保存作品集材料 ${file.name}。图片/扫描件中的二维码会在正式版交由二维码识别服务解析。`, "good");
      } else {
        status("portfolioStatus", `已保存作品集材料 ${file.name}${links.length ? `，识别到链接：${links.join("、")}` : ""}，会作为匹配参考。`, "good");
      }
    };
    if (["txt", "md"].includes(ext)) {
      readTextFile(file, addPortfolio);
    } else {
      addPortfolio();
    }
  }
}

function getSelected(group) {
  return $$(`[data-group="${group}"] button.selected`).map((button) => button.textContent.trim());
}

function getPreferences() {
  return {
    preferredName: state.preferredName,
    hideName: state.hideName,
    mbti: $("#mbti").value.trim(),
    traits: [...getSelected("traits"), $("#traitCustom").value.trim()].filter(Boolean),
    cities: [...getSelected("cities"), $("#cityCustom").value.trim()].filter(Boolean),
    intensity: [...getSelected("intensity"), $("#intensityCustom").value.trim()].filter(Boolean),
    roles: [...getSelected("roles"), $("#roleCustom").value.trim()].filter(Boolean),
    goalMode: $("#goalMode").value
  };
}

function applyProfileToUI(profile) {
  const hasPortfolio = (profile.portfolio_links || profile.portfolio || []).length > 0;
  const strengths = profile.strengths || profile.skills || [];
  const preferred = activeDisplayName(profile.name);
  $("#candidateName").textContent = preferred || "学生画像";
  $("#candidateSummary").textContent = `目标方向：${profile.target || "待探索"}。核心优势：${strengths.join("、") || "待补充"}。${hasPortfolio ? "已识别到作品集/链接，将作为加分参考。" : "未上传作品集，不影响岗位匹配。"}`;
  $("#profileCompleteness").textContent = profile.completeness || 70;
  const confidence = profile.confidence || {};
  $("#confidenceGrid").innerHTML = [
    ["教育背景", confidence.education || "中", confidence.education === "高" ? "high" : "mid"],
    ["实习/项目经历", confidence.experience || "中", "mid"],
    ["技能关键词", confidence.skills || "中", confidence.skills === "高" ? "high" : "mid"],
    ["作品集材料", confidence.portfolio || (hasPortfolio ? "中" : "未提供"), hasPortfolio ? "mid" : "low"],
    ["简历格式", state.resume?.kind === "resume" ? "高" : "待确认", state.resume?.kind === "resume" ? "high" : "mid"],
    ["AI 结论", confidence.ai_conclusion || "中", "mid"]
  ].map(([label, value, cls]) => `<div class="confidence"><strong>${label}</strong><span class="${cls}">${value}</span></div>`).join("");
}

async function generateProfile() {
  if (state.isUploadingResume) {
    status("resumeStatus", "简历还在上传解析中，请稍等几秒后再生成画像。", "warn");
    return false;
  }
  const pasted = $("#resumeText").value.trim();
  if (!state.resume && pasted) {
    try {
      const data = await uploadToBackend("resume", null, pasted);
      state.resume = {
        name: "粘贴文本简历",
        type: "text",
        text: data.record.text || pasted,
        kind: data.record.contentKind,
        links: data.record.links || []
      };
      status("resumeStatus", "后端已使用粘贴文本生成简历解析。", "good");
    } catch (error) {
      state.resume = {
        name: "粘贴文本简历",
        type: "text",
        text: pasted,
        kind: detectResumeLike(pasted),
        links: extractLinks(pasted)
      };
      status("resumeStatus", "已使用粘贴文本生成简历解析。", "good");
    }
  }
  if (!state.resume) {
    status("resumeStatus", "还没有可解析的简历。你可以上传文件、粘贴文本，或使用示例简历体验。", "warn");
    return false;
  }
  try {
    const data = await api("/api/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferences: getPreferences(), resumeText: $("#resumeText").value.trim() })
    });
    state.profile = {
      ...data.profile,
      name: activeDisplayName(data.profile.name),
      portfolio: data.profile.portfolio_links || [],
      strengths: data.profile.strengths || data.profile.skills || []
    };
    applyProfileToUI(state.profile);
    return true;
  } catch (error) {
    status("resumeStatus", `后端画像暂不可用，已使用前端兜底画像：${error.message}`, "warn");
  }
  const text = `${state.resume.text} ${$("#portfolioText").value}`;
  const prefs = getPreferences();
  const links = extractLinks(text);
  const hasPortfolio = state.portfolio.length > 0 || links.length > 0;
  const preferredTarget = prefs.roles.length
    ? prefs.roles.slice(0, 3).join(" / ")
    : text.includes("数据")
      ? "运营 / 数据分析 / 产品运营"
      : "用户运营 / 内容运营 / 产品运营";
  const detectedStrengths = [
    text.includes("社群") ? "社群运营" : "",
    text.includes("活动") ? "活动策划" : "",
    text.includes("用户") ? "用户反馈整理" : "",
    text.includes("内容") ? "内容表达" : "",
    text.includes("数据") || text.includes("Excel") ? "基础数据分析" : "",
    ...prefs.roles,
    ...prefs.traits
  ].filter(Boolean);
  state.profile = {
    name: state.hideName ? "" : (displayableName(state.preferredName) || inferClientName(text)),
    target: preferredTarget,
    strengths: [...new Set(detectedStrengths)].slice(0, 8),
    risks: ["部分经历缺少量化结果", "技能深度需要结合目标岗位确认", "如 OCR 识别不完整需手动补充"],
    portfolio: hasPortfolio ? links : [],
    preferences: prefs,
    completeness: Math.min(96, (hasPortfolio ? 80 : 70) + Math.min(prefs.roles.length + prefs.cities.length + prefs.intensity.length + prefs.traits.length, 8))
  };
  applyProfileToUI(state.profile);
  return true;
}

function scoreJob(job) {
  const prefs = getPreferences();
  const resumeText = `${state.resume?.text || ""} ${$("#resumeText").value}`.toLowerCase();
  const profileText = `${state.profile?.target || ""} ${(state.profile?.strengths || []).join(" ")} ${(state.profile?.skills || []).join(" ")}`.toLowerCase();
  let score = 48;
  const matchedKeywords = job.keywords.filter((key) => resumeText.includes(key.toLowerCase()) || profileText.includes(key.toLowerCase()) || state.profile?.strengths?.some((s) => key.includes(s) || s.includes(key)));
  score += matchedKeywords.length * 7;
  const targetTokens = `${state.profile?.target || ""}`.split(/[ /、]+/).filter(Boolean);
  if (targetTokens.some((token) => job.title.includes(token) || job.jd.includes(token))) score += 10;
  if (prefs.cities.some((city) => job.city.includes(city) || city.includes(job.city) || city.includes("全国"))) score += 10;
  if (prefs.roles.some((role) => job.title.includes(role) || job.jd.includes(role) || job.keywords.some((key) => key.includes(role) || role.includes(key)))) score += 14;
  if (prefs.intensity.some((item) => job.intensity.includes(item) || item.includes(job.intensity))) score += 6;
  if (prefs.traits.some((trait) => job.jd.includes(trait) || job.title.includes(trait))) score += 3;
  if ((prefs.mbti || "").toUpperCase().startsWith("E") && /沟通|用户|社群|活动/.test(job.jd)) score += 3;
  if ((prefs.mbti || "").toUpperCase().startsWith("I") && /数据|分析|流程|研究/.test(job.jd)) score += 3;
  if (state.profile?.portfolio?.length) score += 3;
  if (job.trust === "高") score += 4;
  return Math.min(96, Math.max(48, score));
}

function trustClass(trust) {
  if (trust === "高") return "high";
  if (trust === "中") return "mid";
  return "low";
}

async function renderJobs() {
  const query = $("#jobSearch").value.trim().toLowerCase();
  const source = $("#sourceFilter").value;
  const trust = $("#trustFilter").value;
  let jobs;
  try {
    const params = new URLSearchParams({ query, source, trust });
    const data = await api(`/api/jobs?${params.toString()}`);
    jobs = data.jobs;
    state.jobs = jobs;
  } catch (error) {
    jobs = [...sampleJobs, ...state.customJobs]
      .map((job) => ({ ...job, score: scoreJob(job) }))
      .filter((job) => !source || job.source === source)
      .filter((job) => !trust || job.trust === trust)
      .filter((job) => !query || `${job.title}${job.company}${job.city}${job.keywords.join("")}`.toLowerCase().includes(query))
      .sort((a, b) => b.score - a.score);
    state.jobs = jobs;
  }

  $("#jobGrid").innerHTML = jobs.map((job) => `
    <article class="job-card ${state.selectedJob?.id === job.id ? "selected" : ""}" data-id="${job.id}">
      <div class="job-top">
        <div>
          <h4>${job.company} · ${job.title}</h4>
          <p>${job.city} · ${job.intensity}</p>
        </div>
        <div class="match-score">${job.score}</div>
      </div>
      <div class="meta-row">
        <span class="tag ${trustClass(job.trust)}">可信度：${job.trust}</span>
        <span class="tag">${job.source}</span>
        <span class="tag">更新：${job.updatedAt}</span>
      </div>
      <p>${job.jd}</p>
      <div class="card-actions">
        <button class="small-btn dark" data-action="detail" data-id="${job.id}">查看匹配解释</button>
        <button class="small-btn" data-action="save" data-id="${job.id}">收藏到投递清单</button>
      </div>
    </article>
  `).join("");
}

function findJob(id) {
  const saved = state.savedJobs.map(normalizeBoardItem).map((item) => item.job);
  return [...state.jobs, ...saved, ...sampleJobs, ...state.customJobs].find((job) => job && job.id === id);
}

function renderJobDetail(job) {
  state.selectedJob = { ...job, score: job.score || scoreJob(job) };
  const prefs = getPreferences();
  const matched = job.matchedKeywords || job.keywords.filter((key) => state.profile?.strengths?.some((s) => key.includes(s) || s.includes(key)));
  const evidence = job.evidence || {};
  const why = evidence.why || [
    `命中关键词：${(matched.length ? matched : job.keywords.slice(0, 3)).join("、")}`,
    prefs.cities.length ? `城市偏好已考虑：${prefs.cities.join("、")}` : "你暂未填写城市偏好，因此未按城市强筛。",
    prefs.intensity.length ? `工作强度偏好已考虑：${prefs.intensity.join("、")}` : "你暂未填写强度偏好，本次以岗位能力匹配为主。"
  ];
  const risks = evidence.risks || [
    "简历中建议补充更明确的数据结果，例如人数、转化率、阅读量。",
    job.trust === "高" ? "岗位来自企业官网/公开页面，仍建议投递前打开原链接确认。" : "岗位来自平台或第三方服务，建议跳转原平台确认状态。",
    "AI 不会自动编造经历，不确定字段会标记为待补充。"
  ];
  $("#jobDetail").innerHTML = `
    <h4>${job.company} · ${job.title}</h4>
    <p class="hero-copy">匹配度 ${state.selectedJob.score} 分。AI 置信度：${job.aiConfidence || (state.resume ? "中高" : "中")}；岗位数据可信度：${job.trust}。</p>
    <div class="detail-grid">
      <div class="detail-block">
        <h5>为什么推荐</h5>
        <ul>${why.map((item) => `<li>${item}</li>`).join("")}</ul>
      </div>
      <div class="detail-block">
        <h5>风险提醒</h5>
        <ul>${risks.map((item) => `<li>${item}</li>`).join("")}</ul>
      </div>
      <div class="detail-block">
        <h5>数据来源</h5>
        <ul>
          <li>来源：${job.source}</li>
          <li>方式：${job.method}</li>
          <li>状态：${job.status}</li>
          <li>原始链接：<a href="${job.url}" target="_blank" rel="noreferrer">${job.url}</a></li>
        </ul>
      </div>
      <div class="detail-block">
        <h5>建议投递优先级</h5>
        <ul>
          <li>${job.recommendation || (state.selectedJob.score >= 85 ? "强烈建议优先投递" : state.selectedJob.score >= 72 ? "建议投递" : "可作为备选")}</li>
          <li>简历优化重点：${job.keywords.slice(0, 4).join("、")}</li>
        </ul>
      </div>
    </div>
  `;
  renderAdvice();
  $("#jobDetail").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderAdvice() {
  const job = state.selectedJob || sampleJobs[0];
  const missing = job.missingKeywords || [];
  const matched = job.matchedKeywords || [];
  $("#resumeAdvice").innerHTML = [
    `把经历标题改得更贴近「${job.title}」，突出 ${job.keywords.slice(0, 3).join("、")}。`,
    `当前命中关键词：${matched.length ? matched.join("、") : "暂未明显命中"}；建议补强：${missing.length ? missing.join("、") : "暂无明显缺口"}。`,
    "将“负责/参与”改为“负责什么对象、用了什么方法、产生什么结果”的表达。",
    "补充真实数据：社群人数、活动参与率、内容阅读量、反馈处理数量等。没有数据时标记为待补充，不自动编造。",
    `把作品集链接放在简历顶部或项目经历后，方便 HR 快速验证能力。`
  ].map((item) => `<div class="advice-item">${item}</div>`).join("");
}

async function optimizeResume() {
  if (!state.selectedJob) {
    renderJobDetail({ ...sampleJobs[0] });
  }
  const job = state.selectedJob;
  try {
    const data = await api("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: job.id })
    });
    $("#optimizedPreview").innerHTML = data.html;
    if (data.advice) {
      $("#resumeAdvice").innerHTML = data.advice.map((item) => `<div class="advice-item">${item}</div>`).join("");
    }
    state.downloadUrl = data.download;
    $("#downloadDoc").disabled = false;
    return;
  } catch (error) {
    status("resumeStatus", `后端优化暂不可用，已使用前端兜底预览：${error.message}`, "warn");
  }
  const portfolioLine = state.profile?.portfolio?.length ? `<li>作品集：${state.profile.portfolio[0]}</li>` : `<li>作品集：未提供，可后续补充链接。</li>`;
  const candidateName = activeDisplayName(state.profile?.name);
  $("#optimizedPreview").innerHTML = `
    <div class="resume-doc">
      ${candidateName ? `<h1>${candidateName}</h1>` : ""}
      <p>求职目标：${job.company} · ${job.title}</p>
      <p>岗位关键词：${job.keywords.slice(0, 5).join("、")}</p>
    <ul>
      <li>求职方向：${job.title} / ${job.company}</li>
      <li>核心能力：${job.keywords.slice(0, 5).join("、")}</li>
      ${portfolioLine}
      <li>项目经历优化：负责校园社群与内容运营，围绕用户反馈设计活动方案，沉淀复盘报告，支持后续运营策略迭代。</li>
      <li>建议补充数据：社群规模、活动参与人数、内容曝光量、用户反馈处理数量。</li>
      <li>真实性保护：以上内容仅基于原简历表达优化，未虚构学校、公司、证书或结果数据。</li>
    </ul>
    </div>
  `;
  $("#downloadDoc").disabled = false;
}

function downloadDoc() {
  if (state.downloadUrl) {
    window.location.href = state.downloadUrl;
    return;
  }
  const html = `
    <html><head><meta charset="UTF-8"><title>优化版简历</title></head>
    <body>${$("#optimizedPreview").innerHTML}</body></html>
  `;
  const blob = new Blob([html], { type: "application/msword;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "Mary-优化版简历.doc";
  link.click();
  URL.revokeObjectURL(link.href);
}

function renderKanban() {
  const lanes = ["感兴趣", "已投递", "面试中", "等待结果"];
  const items = state.savedJobs.map(normalizeBoardItem);
  $("#kanban").innerHTML = lanes.map((lane, index) => `
    <div class="lane" data-status="${lane}">
      <div class="lane-head">
        <h4>${lane}</h4>
        <span class="lane-count">${items.filter((item) => item.status === lane).length}</span>
      </div>
      <div class="lane-list">
        ${items.filter((item) => item.status === lane).map((item) => renderMiniCard(item)).join("") || `<div class="mini-card mini-meta">暂无岗位</div>`}
      </div>
      <button class="lane-open" data-action="open-lane" data-status="${lane}">展开查看</button>
    </div>
  `).join("");
  renderInterviewJobOptions();
}

function normalizeBoardStatus(status) {
  if (status === "准备投递") return "感兴趣";
  if (status === "等待反馈") return "等待结果";
  return ["感兴趣", "已投递", "面试中", "等待结果"].includes(status) ? status : "感兴趣";
}

function normalizeBoardItem(item) {
  const normalized = item.job ? item : { job: item, jobId: item.id, status: "感兴趣", savedAt: "" };
  return { ...normalized, status: normalizeBoardStatus(normalized.status) };
}

function renderInterviewJobOptions() {
  const select = $("#interviewJobSelect");
  if (!select) return;
  const items = state.savedJobs.map(normalizeBoardItem);
  if (!items.length) {
    select.innerHTML = `<option value="">请先收藏一个岗位</option>`;
    return;
  }
  select.innerHTML = items.map((item) => {
    const job = item.job;
    return `<option value="${job.id}">${item.status} · ${job.company} · ${job.title}</option>`;
  }).join("");
}

function renderMiniCard(item) {
  const job = item.job || item;
  const score = job.score || scoreJob(job);
  const statuses = ["感兴趣", "已投递", "面试中", "等待结果"];
  return `
    <div class="mini-card" data-id="${job.id}">
      <strong>${job.company} · ${job.title}</strong>
      <div class="mini-meta">匹配度 ${score} · ${job.city} · ${job.source || "未知来源"}</div>
      <div class="mini-actions">
        <select data-action="move-saved" data-id="${job.id}">
          ${statuses.map((status) => `<option value="${status}" ${item.status === status ? "selected" : ""}>${status}</option>`).join("")}
        </select>
        <button class="text-btn" data-action="detail-saved" data-id="${job.id}">详情</button>
        <button class="text-btn danger" data-action="delete-saved" data-id="${job.id}">删除</button>
      </div>
    </div>
  `;
}

function renderBoardDetail(status) {
  const items = state.savedJobs
    .map(normalizeBoardItem)
    .filter((item) => item.status === status);
  const box = $("#boardDetail");
  box.hidden = false;
  box.innerHTML = `
    <div class="board-detail-head">
      <h4>${status} · ${items.length} 个岗位</h4>
      <button class="text-btn" data-action="close-board">收起</button>
    </div>
    <div class="board-list">
      ${items.map((item) => renderMiniCard(item)).join("") || `<div class="mini-card mini-meta">这个阶段还没有岗位。</div>`}
    </div>
  `;
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function addCustomJob() {
  const text = $("#customJd").value.trim();
  if (!text) return;
  try {
    await api("/api/custom-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    $("#customJd").value = "";
    await renderJobs();
    return;
  } catch (error) {
    status("resumeStatus", `后端添加岗位暂不可用，已使用前端兜底：${error.message}`, "warn");
  }
  const isLink = /^https?:\/\//.test(text);
  state.customJobs.push({
    id: `custom-${Date.now()}`,
    title: isLink ? "用户提供链接岗位" : "用户粘贴 JD 岗位",
    company: "待确认公司",
    city: "待确认",
    source: "用户主动提供",
    method: "用户粘贴岗位链接或 JD",
    url: isLink ? text : "#",
    updatedAt: new Date().toLocaleString("zh-CN", { hour12: false }),
    postedAt: "待确认",
    trust: isLink ? "中" : "待确认",
    status: isLink ? "需后端访问原链接校验" : "JD 文本完整性待确认",
    intensity: "待确认",
    keywords: ["岗位要求", "项目经历", "技能匹配", "简历优化"],
    jd: text.slice(0, 180)
  });
  $("#customJd").value = "";
  renderJobs();
}

async function loadSample() {
  state.preferredName = "";
  state.hideName = false;
  $("#resumeText").value = sampleResume;
  $("#resumeFile").value = "";
  try {
    await api("/api/use-sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: sampleResume })
    });
  } catch (error) {
    status("resumeStatus", `后端暂不可用，已在前端加载示例简历：${error.message}`, "warn");
  }
  state.resume = { name: "示例简历", type: "text", text: sampleResume, kind: "resume", links: extractLinks(sampleResume) };
  state.loadedSample = true;
  resetProfileView();
  status("resumeStatus", "已加载示例简历，可以直接进入下一步。", "good");
}

async function saveJob(job) {
  try {
    const data = await api("/api/save-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: job.id })
    });
    state.savedJobs = data.savedJobs || state.savedJobs;
  } catch (error) {
    if (!state.savedJobs.some((saved) => saved.id === job.id)) state.savedJobs.push(job);
  }
  renderKanban();
  handleSaveJumpPreference();
}

function handleSaveJumpPreference() {
  state.saveJumpCount += 1;
  localStorage.setItem("marySaveJumpCount", String(state.saveJumpCount));
  if (state.saveJumpPreference === "jump") {
    showStep("tracker");
    return;
  }
  if (state.saveJumpPreference === "stay") {
    showToast("已收藏到投递清单，可在第 5 步查看");
    return;
  }
  if (state.saveJumpCount === 1) {
    showStep("tracker");
    return;
  }
  const shouldJump = window.confirm("已收藏到投递清单。是否现在跳转到第 5 步看板？");
  const remember = window.confirm("是否记住本次选择，后续不再提醒？");
  if (remember) {
    state.saveJumpPreference = shouldJump ? "jump" : "stay";
    localStorage.setItem("marySaveJumpPreference", state.saveJumpPreference);
  }
  if (shouldJump) {
    showStep("tracker");
  } else {
    showToast("已收藏到投递清单，可在第 5 步查看");
  }
}

async function moveSavedJob(jobId, status) {
  try {
    const data = await api("/api/update-job-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId, status })
    });
    state.savedJobs = data.savedJobs || state.savedJobs;
  } catch (error) {
    state.savedJobs = state.savedJobs.map((item) => {
      const job = item.job || item;
      if (job.id !== jobId) return item;
      return item.job ? { ...item, status } : { job: item, jobId, status, savedAt: "" };
    });
  }
  renderKanban();
}

async function deleteSavedJob(jobId) {
  try {
    const data = await api("/api/delete-saved-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId })
    });
    state.savedJobs = data.savedJobs || [];
  } catch (error) {
    state.savedJobs = state.savedJobs.filter((item) => (item.job || item).id !== jobId);
  }
  renderKanban();
  $("#boardDetail").hidden = true;
}

async function generateInterviewPack() {
  const selectedId = $("#interviewJobSelect")?.value;
  if (!selectedId) {
    $("#interviewBox").innerHTML = "请先在岗位匹配中收藏一个岗位，然后在上方下拉框选择要准备面试的岗位。";
    return;
  }
  const selectedItem = state.savedJobs.map(normalizeBoardItem).find((item) => item.job.id === selectedId);
  const job = selectedItem && selectedItem.job;
  if (!job) {
    $("#interviewBox").innerHTML = "没有找到这个岗位，请刷新看板或重新收藏岗位后再生成。";
    return;
  }
  try {
    const data = await api("/api/interview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: job.id })
    });
    const pack = data.pack;
    $("#interviewBox").innerHTML = `
      <strong>${pack.title}</strong>
      <ul>
        <li>自我介绍：${pack.selfIntro}</li>
        ${(pack.questions || []).map((q) => `<li>高频问题：${q}</li>`).join("")}
        <li>开场语：${pack.opening}</li>
      </ul>
    `;
    return;
  } catch (error) {
    const candidateName = activeDisplayName(state.profile?.name);
    const intro = candidateName
      ? `你好，我是${candidateName}，关注${job.title}方向，具备校园社群、内容策划、用户反馈和数据复盘经历，希望结合岗位需求进一步沟通。`
      : `你好，我关注${job.title}方向，具备校园社群、内容策划、用户反馈和数据复盘经历，希望结合岗位需求进一步沟通。`;
    $("#interviewBox").innerHTML = `
      <strong>${job.company} · ${job.title} 面试准备包</strong>
      <ul>
        <li>自我介绍：${intro}</li>
        <li>高频问题：你如何判断一次活动是否成功？如何处理用户反馈？如何做内容选题？</li>
        <li>项目追问：活动目标、执行过程、数据结果、复盘改进。</li>
        <li>开场语：你好，我对贵公司的 ${job.title} 很感兴趣，我有社群运营和内容策划经验，希望有机会进一步沟通。</li>
      </ul>
    `;
  }
}

async function loadBackendState() {
  try {
    const data = await api("/api/state");
    state.savedJobs = data.data.saved_jobs || [];
    renderKanban();
  } catch (error) {
    renderKanban();
  }
}

function bindEvents() {
  $$(".step").forEach((button) => button.addEventListener("click", () => showStep(button.dataset.step)));
  $$(".chips button").forEach((button) => button.addEventListener("click", () => button.classList.toggle("selected")));
  $("#resumeFile").addEventListener("change", (event) => handleResumeFile(event.target.files[0]));
  $("#portfolioFile").addEventListener("change", (event) => handlePortfolioFiles(event.target.files));
  $("#loadSample").addEventListener("click", loadSample);
  $("#goProfile").addEventListener("click", async () => {
    if (await generateProfile()) showStep("profile");
  });
  $("#analyzeProfile").addEventListener("click", generateProfile);
  $("#goJobsFromProfile").addEventListener("click", async () => {
    if (!state.profile && !(await generateProfile())) return;
    await renderJobs();
    showStep("jobs");
  });
  $("#matchJobs").addEventListener("click", async () => {
    if (!state.profile && !(await generateProfile())) return;
    await renderJobs();
    showStep("jobs");
  });
  ["jobSearch", "sourceFilter", "trustFilter"].forEach((id) => $(`#${id}`).addEventListener("input", renderJobs));
  $("#addCustomJob").addEventListener("click", addCustomJob);
  $("#jobGrid").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const job = findJob(button.dataset.id);
    if (!job) return;
    if (button.dataset.action === "detail") renderJobDetail(job);
    if (button.dataset.action === "save") {
      saveJob(job);
    }
  });
  $("#kanban").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.action === "open-lane") renderBoardDetail(button.dataset.status);
    if (button.dataset.action === "delete-saved") deleteSavedJob(button.dataset.id);
    if (button.dataset.action === "detail-saved") {
      const job = findJob(button.dataset.id) || (state.savedJobs.find((item) => (item.job || item).id === button.dataset.id) || {}).job;
      if (job) {
        renderJobDetail(job);
        showStep("jobs");
      }
    }
  });
  $("#kanban").addEventListener("change", (event) => {
    if (event.target.dataset.action === "move-saved") {
      moveSavedJob(event.target.dataset.id, event.target.value);
    }
  });
  $("#boardDetail").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.action === "close-board") $("#boardDetail").hidden = true;
    if (button.dataset.action === "delete-saved") deleteSavedJob(button.dataset.id);
    if (button.dataset.action === "detail-saved") {
      const job = findJob(button.dataset.id) || (state.savedJobs.find((item) => (item.job || item).id === button.dataset.id) || {}).job;
      if (job) {
        renderJobDetail(job);
        showStep("jobs");
      }
    }
  });
  $("#boardDetail").addEventListener("change", (event) => {
    if (event.target.dataset.action === "move-saved") {
      moveSavedJob(event.target.dataset.id, event.target.value);
    }
  });
  $("#optimizeResume").addEventListener("click", optimizeResume);
  $("#downloadDoc").addEventListener("click", downloadDoc);
  $("#generateInterview").addEventListener("click", generateInterviewPack);
  $("#savePreferredName").addEventListener("click", () => closePreferredNameDialog($("#preferredNameInput").value));
  $("#skipPreferredName").addEventListener("click", () => closePreferredNameDialog(""));
  $("#preferredNameInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") closePreferredNameDialog(event.target.value);
    if (event.key === "Escape") closePreferredNameDialog("");
  });
}

bindEvents();
renderAdvice();
renderJobs();
loadBackendState();
