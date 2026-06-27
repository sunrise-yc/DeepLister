import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).parent
HOST_IMAGE = ROOT / "assets" / "survey-host.png"

THEME = {
    "sage": "#DCEBDD",
    "forest": "#2F6B4F",
    "olive": "#708238",
    "mist": "#F7FFF9",
}

ROUTES = {"home", "import", "invite", "mbti", "sample", "chat", "complete"}

MBTI_QUESTIONS = [
    {
        "text": "周末突然没人找你，你的第一反应是？",
        "dimension": "社交充电方式",
        "axis": "EI",
        "options": [
            {"text": "太好了，我终于可以安静回血了", "scores": {"I": 2}},
            {"text": "有点慌，世界是不是把我忘了", "scores": {"E": 2}},
            {"text": "看情况，有意思的局我会立刻出现", "scores": {"E": 1, "P": 1}},
            {"text": "我已经开始安排下一场见面了", "scores": {"E": 2, "J": 1}},
        ],
        "quip": "收到，你不是简单地爱不爱热闹，你是在挑“值不值得消耗电量”。",
    },
    {
        "text": "朋友说有个新计划，但细节还没想好，你会？",
        "dimension": "理解世界的方式",
        "axis": "SN",
        "options": [
            {"text": "先问预算、时间、谁负责，别给我画饼", "scores": {"S": 2, "J": 1}},
            {"text": "脑子里已经展开三个版本的可能性", "scores": {"N": 2}},
            {"text": "先试一下，边走边修", "scores": {"S": 1, "P": 1}},
            {"text": "我想听它背后的意义和想象空间", "scores": {"N": 2, "F": 1}},
        ],
        "quip": "有意思，你对“计划”两个字的忍耐度，基本暴露了你的思维操作系统。",
    },
    {
        "text": "朋友深夜发来一大段崩溃小作文，你第一步通常是？",
        "dimension": "做判断的依据",
        "axis": "TF",
        "options": [
            {"text": "先安慰，他现在需要的是被接住", "scores": {"F": 2}},
            {"text": "先帮他拆问题，不然越聊越乱", "scores": {"T": 2}},
            {"text": "先陪他骂两句，再慢慢分析", "scores": {"F": 1, "T": 1}},
            {"text": "问一句：你想被安慰，还是想要方案？", "scores": {"T": 1, "F": 1, "J": 1}},
        ],
        "quip": "这题很关键：你是先递纸巾，还是先递流程图。",
    },
    {
        "text": "明天要出门，你今晚会怎么处理准备工作？",
        "dimension": "行动节奏",
        "axis": "JP",
        "options": [
            {"text": "路线、物品、时间表都提前摆好", "scores": {"J": 2}},
            {"text": "明天再说，我相信现场发挥", "scores": {"P": 2}},
            {"text": "大件先准备，小事随缘", "scores": {"J": 1, "P": 1}},
            {"text": "我会准备，但不妨碍我最后五分钟乱一下", "scores": {"J": 1, "P": 1}},
        ],
        "quip": "明白了，你和截止时间的关系，很像一场彼此试探的拉扯。",
    },
]

SAMPLE_QUESTIONS = [
    {
        "text": "最近一周睡眠怎么样？有没有入睡困难、早醒，或者白天明显没精神？",
        "dimension": "睡眠质量",
        "options": [
            {"text": "入睡有点慢，白天也容易困"},
            {"text": "还可以，但偶尔会醒"},
            {"text": "最近睡得比较差"},
        ],
        "quip": "我先把睡眠这块记下来，再追一下影响范围。",
    },
    {
        "text": "如果用 1 到 10 分表示最近的压力，10 分最强，你大概在几分？主要来自哪里？",
        "dimension": "压力来源",
        "options": [
            {"text": "7 分左右，主要是工作"},
            {"text": "5 分，事情多但还能扛"},
            {"text": "8 分以上，已经影响状态"},
        ],
        "quip": "收到，压力不是抽象的云，我会把它落到具体场景里。",
    },
    {
        "text": "这种状态对你的学习、工作、社交或日常安排有什么影响？",
        "dimension": "生活影响",
        "options": [
            {"text": "效率下降，容易拖延"},
            {"text": "社交变少，更想一个人待着"},
            {"text": "影响不大，但有点消耗"},
        ],
        "quip": "这部分很重要，问卷里真正有价值的往往是“影响到了哪里”。",
    },
    {
        "text": "你希望接下来一周最先改善的一件小事是什么？",
        "dimension": "改善目标",
        "options": [
            {"text": "先把睡眠调回来"},
            {"text": "减少拖延，把事情排清楚"},
            {"text": "想让情绪更稳定一点"},
        ],
        "quip": "好，我会把这个目标整理成最后的可执行结论。",
    },
]

AGENT_TEMPLATES = {
    "mbti": {
        "kind": "mbti",
        "title": "趣味人格测试",
        "subtitle": "一个不太正经但很会追问的 MBTI Agent",
        "invite_code": "MBTI-DEMO",
        "opening": "欢迎入座。我会用几道生活题判断你的人格倾向，尽量准，也尽量不端着。",
        "questions": MBTI_QUESTIONS,
    },
    "sample": {
        "kind": "sample",
        "title": "快速体验样例",
        "subtitle": "用一个轻量调研快速展示 DeepLister 的追问和整理能力",
        "invite_code": "SCL90-DEMO",
        "opening": "这是一个快速样例。我会像调研 Agent 一样追问，并把回答整理成可导出的问卷。",
        "questions": SAMPLE_QUESTIONS,
    },
}

RESULT_TITLES = {
    "INTJ": "冷静施工中的人生建筑师",
    "INTP": "脑内开会型逻辑工程师",
    "ENTJ": "目标压路机型总指挥",
    "ENTP": "观点蹦迪型辩手",
    "INFJ": "温柔预言型观察家",
    "INFP": "情绪收藏型理想派",
    "ENFJ": "气氛照明型组织者",
    "ENFP": "灵感喷泉型选手",
    "ISTJ": "表格护城河型执行者",
    "ISFJ": "默默兜底但想下班的人",
    "ESTJ": "任务清仓型负责人",
    "ESFJ": "人情雷达型照顾者",
    "ISTP": "冷静拆解型问题处理器",
    "ISFP": "审美在线型自由人",
    "ESTP": "现场开麦型行动派",
    "ESFP": "快乐外放型氛围发动机",
}


def apply_style() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --sage: {THEME["sage"]};
            --forest: {THEME["forest"]};
            --olive: {THEME["olive"]};
            --mist: {THEME["mist"]};
        }}
        .stApp {{
            background:
                linear-gradient(180deg, rgba(247,255,249,0.72), rgba(220,235,221,0.96)),
                var(--sage);
            color: #183d2e;
        }}
        .block-container {{
            max-width: 760px;
            padding: 1.1rem 1.05rem 5.2rem;
        }}
        h1, h2, h3 {{
            color: var(--forest);
            letter-spacing: 0;
        }}
        h1 {{
            font-size: 2.1rem;
            line-height: 1.15;
            margin-bottom: 0.35rem;
        }}
        p {{
            line-height: 1.7;
        }}
        [data-testid="stSidebar"] {{
            background: var(--mist);
        }}
        .hero {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.9rem;
            align-items: center;
            margin-bottom: 1rem;
        }}
        .eyebrow {{
            color: var(--olive);
            font-weight: 800;
            margin: 0 0 0.25rem;
        }}
        .lead {{
            color: #5b796b;
            margin: 0;
        }}
        .stImage img {{
            width: min(100%, 380px) !important;
            max-width: 380px !important;
            display: block;
            margin: 0 auto;
            border-radius: 8px;
            border: 1px solid rgba(247,255,249,0.82);
            box-shadow: 0 18px 48px rgba(47,107,79,0.16);
            animation: hostFloat 5s ease-in-out infinite;
        }}
        @keyframes hostFloat {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-5px); }}
        }}
        .home-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1rem;
        }}
        .home-card {{
            min-height: 148px;
            aspect-ratio: 1 / 1;
            border-radius: 8px;
            border: 1px solid rgba(247,255,249,0.95);
            background: rgba(247,255,249,0.74);
            box-shadow: 0 16px 38px rgba(47,107,79,0.12);
            padding: 1rem;
            color: var(--forest) !important;
            text-decoration: none !important;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
        }}
        .home-card:hover {{
            transform: translateY(-2px);
            background: var(--mist);
            box-shadow: 0 20px 46px rgba(47,107,79,0.18);
        }}
        .home-card strong {{
            display: block;
            font-size: 1.15rem;
            line-height: 1.25;
        }}
        .home-card small {{
            display: block;
            color: #63806f;
            line-height: 1.45;
        }}
        .home-card.primary {{
            background: var(--forest);
            color: var(--mist) !important;
        }}
        .home-card.primary small {{
            color: rgba(247,255,249,0.82);
        }}
        .home-card.center {{
            grid-column: 1 / span 2;
            width: min(52%, 230px);
            justify-self: center;
        }}
        .sample-row {{
            display: flex;
            justify-content: flex-end;
            margin-top: 0.75rem;
        }}
        .sample-pill, .back-link {{
            border: 1px solid rgba(112,130,56,0.34);
            border-radius: 999px;
            color: var(--forest) !important;
            background: rgba(247,255,249,0.72);
            padding: 0.55rem 0.8rem;
            text-decoration: none !important;
            font-weight: 700;
        }}
        .panel {{
            border: 1px solid rgba(247,255,249,0.92);
            border-radius: 8px;
            background: rgba(247,255,249,0.72);
            padding: 1rem;
            box-shadow: 0 16px 42px rgba(47,107,79,0.12);
            margin: 0.8rem 0 1rem;
        }}
        .code-box {{
            border: 1px dashed rgba(112,130,56,0.58);
            border-radius: 8px;
            padding: 0.85rem;
            background: rgba(247,255,249,0.82);
            color: var(--forest);
            font-size: 1.2rem;
            font-weight: 800;
            text-align: center;
            letter-spacing: 0;
        }}
        div.stButton > button,
        div.stDownloadButton > button {{
            border-radius: 8px;
            border: 1px solid var(--forest);
            background: var(--forest);
            color: var(--mist);
            min-height: 3rem;
            font-weight: 800;
        }}
        div.stButton > button:hover,
        div.stDownloadButton > button:hover {{
            border-color: var(--olive);
            background: var(--olive);
            color: var(--mist);
        }}
        [data-testid="stChatMessage"] {{
            background: rgba(247,255,249,0.62);
            border-radius: 8px;
            border: 1px solid rgba(247,255,249,0.88);
        }}
        .metric-strip {{
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin: 0.5rem 0 0.9rem;
        }}
        .metric-strip span {{
            border-radius: 999px;
            background: rgba(247,255,249,0.76);
            border: 1px solid rgba(112,130,56,0.22);
            color: #4f6e60;
            padding: 0.34rem 0.58rem;
            font-size: 0.86rem;
            font-weight: 700;
        }}
        .result-card {{
            border-radius: 8px;
            background: var(--forest);
            color: var(--mist);
            padding: 1rem;
            margin: 0.8rem 0;
        }}
        .result-card h2 {{
            color: var(--mist);
            margin-top: 0;
        }}
        .result-card p {{
            color: rgba(247,255,249,0.86);
        }}
        @media (max-width: 560px) {{
            .block-container {{
                padding-left: 0.9rem;
                padding-right: 0.9rem;
            }}
            h1 {{
                font-size: 1.58rem;
            }}
            .home-grid {{
                gap: 0.65rem;
            }}
            .home-card {{
                min-height: 132px;
                padding: 0.82rem;
            }}
            .home-card.center {{
                width: min(62%, 210px);
            }}
            .stImage img {{
                width: min(100%, 260px) !important;
                max-width: 260px !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sync_page_from_query() -> None:
    page = st.query_params.get("page", "home")
    if page not in ROUTES:
        page = "home"
    st.session_state.page = page


def go_to(page: str) -> None:
    st.session_state.page = page
    st.query_params["page"] = page
    st.rerun()


def reset_agent_state() -> None:
    for key in [
        "agent",
        "messages",
        "answers",
        "step",
        "mbti_scores",
        "completed_at",
        "uploaded_name",
        "import_code",
    ]:
        st.session_state.pop(key, None)


def build_import_agent(file_name: str) -> dict:
    return {
        "kind": "imported",
        "title": "导入问卷 Agent",
        "subtitle": f"已根据《{file_name}》生成追问式调研",
        "invite_code": st.session_state.get("import_code", "DL-2026"),
        "opening": "问卷已经导入。我会先用聊天方式完成调研，再帮你整理成已填写问卷。",
        "questions": [
            {
                "text": "这份问卷最想了解的核心问题是什么？你可以用一句话说说。",
                "dimension": "调研目标",
                "options": [
                    {"text": "想了解用户真实需求"},
                    {"text": "想评估体验满意度"},
                    {"text": "想判断某个方案是否可行"},
                ],
                "quip": "好的，我会把目标先钉住，后面追问才不会飘。",
            },
            {
                "text": "被调研者最典型的一个使用场景是什么？",
                "dimension": "使用场景",
                "options": [
                    {"text": "第一次接触产品"},
                    {"text": "完成一次具体任务后"},
                    {"text": "遇到问题需要反馈时"},
                ],
                "quip": "场景越具体，Agent 填出来的问卷越像真的理解过人。",
            },
            {
                "text": "你最希望 Agent 追问清楚哪类细节？",
                "dimension": "追问重点",
                "options": [
                    {"text": "原因和动机"},
                    {"text": "具体例子"},
                    {"text": "改进建议"},
                ],
                "quip": "收到，我会把追问重点放在这类信息上。",
            },
            {
                "text": "如果最后只能导出三条最有用的信息，你希望是哪三类？",
                "dimension": "导出偏好",
                "options": [
                    {"text": "痛点、原因、建议"},
                    {"text": "评分、解释、案例"},
                    {"text": "人群、场景、结论"},
                ],
                "quip": "明白，最后的问卷结果会按这个方向整理。",
            },
        ],
    }


def build_invite_agent(code: str) -> dict:
    agent = deepcopy(AGENT_TEMPLATES["sample"])
    agent["kind"] = "invite"
    agent["title"] = "他人制作的调研 Agent"
    agent["subtitle"] = f"邀请码：{code}"
    agent["invite_code"] = code
    agent["opening"] = "你已经进入他人制作好的调研 Agent。我会完成追问，并整理出可导出的问卷。"
    return agent


def start_agent(kind: str, *, file_name: str | None = None, invite_code: str | None = None) -> None:
    if kind == "imported":
        agent = build_import_agent(file_name or "导入问卷")
    elif kind == "invite":
        code = (invite_code or "SCL90-DEMO").strip().upper()
        if code == "MBTI-DEMO":
            agent = deepcopy(AGENT_TEMPLATES["mbti"])
        elif code == "SCL90-DEMO":
            agent = deepcopy(AGENT_TEMPLATES["sample"])
        else:
            agent = build_invite_agent(code)
    else:
        agent = deepcopy(AGENT_TEMPLATES[kind])

    st.session_state.agent = agent
    st.session_state.messages = [
        {"role": "assistant", "content": f"{agent['opening']}\n\n{agent['questions'][0]['text']}"}
    ]
    st.session_state.answers = []
    st.session_state.step = 0
    st.session_state.mbti_scores = {letter: 0 for letter in "EISNTFJP"}
    st.session_state.completed_at = None


def current_agent() -> dict:
    if "agent" not in st.session_state:
        start_agent("sample")
    return st.session_state.agent


def current_question() -> dict | None:
    agent = current_agent()
    step = st.session_state.get("step", 0)
    if step >= len(agent["questions"]):
        return None
    return agent["questions"][step]


def add_scores(scores: dict[str, int] | None) -> None:
    if not scores:
        return
    for key, value in scores.items():
        st.session_state.mbti_scores[key] = st.session_state.mbti_scores.get(key, 0) + value


def infer_scores_from_text(text: str, question: dict) -> dict[str, int]:
    if "axis" not in question:
        return {}

    normalized = text.lower()
    scores: dict[str, int] = {}
    keyword_map = {
        "I": ["安静", "独处", "一个人", "宅", "休息", "不想出门"],
        "E": ["聚会", "朋友", "热闹", "聊天", "见面", "组织"],
        "S": ["具体", "细节", "预算", "时间", "实际", "先试"],
        "N": ["可能", "想象", "意义", "灵感", "未来", "版本"],
        "T": ["分析", "问题", "方案", "逻辑", "拆", "解决"],
        "F": ["安慰", "感受", "陪", "情绪", "理解", "接住"],
        "J": ["计划", "提前", "安排", "清单", "准备", "确定"],
        "P": ["随缘", "现场", "明天再说", "临时", "自由", "边走边"],
    }
    for letter, words in keyword_map.items():
        if any(word in normalized for word in words):
            scores[letter] = scores.get(letter, 0) + 1
    return scores


def submit_answer(text: str, scores: dict[str, int] | None = None) -> None:
    text = text.strip()
    if not text:
        return

    agent = current_agent()
    question = current_question()
    if question is None:
        go_to("complete")

    final_scores = scores or infer_scores_from_text(text, question)
    add_scores(final_scores)

    st.session_state.messages.append({"role": "user", "content": text})
    st.session_state.answers.append(
        {
            "question": question["text"],
            "dimension": question["dimension"],
            "answer": text,
            "scores": final_scores,
        }
    )

    next_step = st.session_state.step + 1
    if next_step >= len(agent["questions"]):
        st.session_state.step = next_step
        st.session_state.completed_at = datetime.now().isoformat(timespec="seconds")
        go_to("complete")

    st.session_state.step = next_step
    next_question = agent["questions"][next_step]
    reply = f"{question['quip']}\n\n{next_question['text']}"
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


def mbti_type() -> str:
    scores = st.session_state.get("mbti_scores", {})
    return "".join(
        [
            "E" if scores.get("E", 0) >= scores.get("I", 0) else "I",
            "N" if scores.get("N", 0) >= scores.get("S", 0) else "S",
            "F" if scores.get("F", 0) >= scores.get("T", 0) else "T",
            "P" if scores.get("P", 0) >= scores.get("J", 0) else "J",
        ]
    )


def result_summary() -> dict:
    agent = current_agent()
    if agent["kind"] == "mbti":
        persona = mbti_type()
        title = RESULT_TITLES.get(persona, "清醒发电型选手")
        return {
            "headline": f"经过测试，你的人格是：{persona}",
            "title": title,
            "description": (
                f"你像是“{title}”：做决定时有自己的节奏，既会被新鲜感点亮，"
                "也会在关键问题上突然认真。DeepLister 已经把你的回答整理成问卷结果。"
            ),
        }

    if agent["kind"] == "imported":
        return {
            "headline": "恭喜你完成调研",
            "title": "导入问卷已由 Agent 填写完成",
            "description": "DeepLister 根据你的回答，整理出了目标、场景、追问重点和导出偏好。",
        }

    return {
        "headline": "恭喜你完成调研",
        "title": "调研 Agent 已完成问卷整理",
        "description": "DeepLister 已把你的聊天回答整理成一份可导出的已填写问卷。",
    }


def build_export_payload() -> str:
    agent = current_agent()
    summary = result_summary()
    payload = {
        "product": "DeepLister",
        "agent_title": agent["title"],
        "invite_code": agent.get("invite_code"),
        "completed_at": st.session_state.get("completed_at"),
        "result": summary,
        "filled_questionnaire": [
            {
                "dimension": item["dimension"],
                "question": item["question"],
                "user_answer": item["answer"],
                "agent_filled_answer": f"Agent 整理：{item['answer']}",
            }
            for item in st.session_state.get("answers", [])
        ],
    }
    if agent["kind"] == "mbti":
        payload["mbti_type"] = mbti_type()
        payload["mbti_scores"] = st.session_state.get("mbti_scores", {})
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_sidebar() -> None:
    st.sidebar.title("DeepLister")
    st.sidebar.caption("追问式问卷 Agent Demo")
    if st.sidebar.button("回到首页", use_container_width=True):
        reset_agent_state()
        go_to("home")
    st.sidebar.markdown("邀请码")
    st.sidebar.code("MBTI-DEMO\nSCL90-DEMO")


def render_home() -> None:
    reset_agent_state()
    st.markdown(
        """
        <div class="hero">
          <div>
            <p class="eyebrow">DeepLister</p>
            <h1>让问卷变成会追问的调研 Agent</h1>
            <p class="lead">上传问卷、输入邀请码，或直接进入一个更有趣的人格测试。</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if HOST_IMAGE.exists():
        st.image(str(HOST_IMAGE), use_container_width=True)
    st.markdown(
        """
        <div class="home-grid">
          <a class="home-card primary" href="?page=import">
            <strong>导入测试</strong>
            <small>上传已有问卷，生成一个可追问的调研 Agent</small>
          </a>
          <a class="home-card" href="?page=invite">
            <strong>输入邀请码</strong>
            <small>进入别人制作好的调研 Agent</small>
          </a>
          <a class="home-card center" href="?page=mbti">
            <strong>MBTI测试</strong>
            <small>轻松一点，但不是随便测测</small>
          </a>
        </div>
        <div class="sample-row">
          <a class="sample-pill" href="?page=sample">快速体验样例</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_import() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("请导入你的调查问卷")
    st.markdown(
        """
        <div class="panel">
          <b>上传后会生成一个调研 Agent。</b>
          <p>你可以自己开始作答，也可以复制邀请码让别人进入。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "上传问卷文件",
        type=["txt", "json", "csv", "docx", "pdf", "xlsx"],
        label_visibility="collapsed",
    )

    if uploaded is None:
        return

    st.session_state.uploaded_name = uploaded.name
    st.session_state.import_code = f"DL-{abs(hash(uploaded.name)) % 9000 + 1000}"
    st.markdown(
        f"""
        <div class="panel">
          <b>已生成调研 Agent</b>
          <p>{uploaded.name}</p>
          <div class="code-box">{st.session_state.import_code}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("开始作答", use_container_width=True):
        start_agent("imported", file_name=uploaded.name)
        go_to("chat")


def render_invite() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("请输入邀请码")
    code = st.text_input("邀请码", placeholder="例如 MBTI-DEMO 或 SCL90-DEMO", label_visibility="collapsed")
    if st.button("进入调研 Agent", use_container_width=True):
        start_agent("invite", invite_code=code or "SCL90-DEMO")
        go_to("chat")


def render_chat() -> None:
    agent = current_agent()
    question = current_question()
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title(agent["title"])
    st.caption(agent["subtitle"])
    st.markdown(
        f"""
        <div class="metric-strip">
          <span>{st.session_state.get("step", 0)} / {len(agent["questions"])} 已完成</span>
          <span>邀请码 {agent.get("invite_code", "DL-DEMO")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if question and question.get("options"):
        st.markdown("###### 快速选择")
        columns = st.columns(2)
        for index, option in enumerate(question["options"]):
            with columns[index % 2]:
                if st.button(option["text"], key=f"option_{st.session_state.step}_{index}", use_container_width=True):
                    submit_answer(option["text"], option.get("scores"))

    prompt = st.chat_input("输入回答")
    if prompt:
        submit_answer(prompt)


def render_complete() -> None:
    agent = current_agent()
    summary = result_summary()
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="result-card">
          <h2>{summary["headline"]}</h2>
          <h3>{summary["title"]}</h3>
          <p>{summary["description"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if HOST_IMAGE.exists():
        st.image(str(HOST_IMAGE), use_container_width=True)
    st.download_button(
        "导出已填写问卷",
        data=build_export_payload(),
        file_name=f"deeplister-{agent['kind']}-filled-questionnaire.json",
        mime="application/json",
        use_container_width=True,
    )
    if st.button("再体验一次", use_container_width=True):
        reset_agent_state()
        go_to("home")


def handle_direct_routes() -> None:
    page = st.session_state.page
    if page == "mbti":
        start_agent("mbti")
        go_to("chat")
    if page == "sample":
        start_agent("sample")
        go_to("chat")


def main() -> None:
    st.set_page_config(page_title="DeepLister Demo", layout="centered")
    apply_style()
    sync_page_from_query()
    handle_direct_routes()
    render_sidebar()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "import":
        render_import()
    elif page == "invite":
        render_invite()
    elif page == "chat":
        render_chat()
    elif page == "complete":
        render_complete()
    else:
        render_home()


if __name__ == "__main__":
    main()
