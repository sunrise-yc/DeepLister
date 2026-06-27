import base64
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).parent
HOST_IMAGE = ROOT / "assets" / "hero-listener.png"
AMBIENT_IMAGE = ROOT / "assets" / "hero-ambient.png"

ROUTES = {"home", "import", "invite", "mbti", "sample", "agent", "complete"}

MBTI_QUESTIONS = [
    {
        "dimension": "社交充电方式",
        "question": "周末突然没人找你，你的第一反应是？",
        "why": "这题用来判断你更像从独处里回血，还是从互动里获得能量。",
        "followup": "能举一个最近的周末例子吗？你当时是真的放松，还是有一点被落下的感觉？",
        "options": [
            "太好了，我终于可以安静回血了",
            "有点慌，世界是不是把我忘了",
            "看情况，有意思的局我会出现",
            "我已经开始安排下一场见面了",
        ],
        "scores": [{"I": 2}, {"E": 2}, {"E": 1, "P": 1}, {"E": 2, "J": 1}],
    },
    {
        "dimension": "理解世界的方式",
        "question": "朋友说有个新计划，但细节还没想好，你会先关注什么？",
        "why": "这题观察你更先抓具体条件，还是先看可能性和想象空间。",
        "followup": "如果这个计划听起来很有趣，但细节很散，你会先补细节，还是先让它跑起来？",
        "options": [
            "预算、时间、谁负责，先说清楚",
            "我已经想到三个可能版本",
            "先试一下，边走边修",
            "我更关心它背后的意义",
        ],
        "scores": [{"S": 2, "J": 1}, {"N": 2}, {"S": 1, "P": 1}, {"N": 2, "F": 1}],
    },
    {
        "dimension": "判断依据",
        "question": "朋友深夜发来一大段崩溃小作文，你第一步通常是？",
        "why": "这题判断你遇到问题时，是先接住情绪，还是先拆解问题。",
        "followup": "如果对方一直绕在情绪里，你会继续陪着，还是开始帮他整理解决方案？",
        "options": [
            "先安慰，他现在需要被接住",
            "先帮他拆问题，不然越聊越乱",
            "先陪他骂两句，再慢慢分析",
            "问他想被安慰，还是想要方案",
        ],
        "scores": [{"F": 2}, {"T": 2}, {"F": 1, "T": 1}, {"T": 1, "F": 1, "J": 1}],
    },
    {
        "dimension": "行动节奏",
        "question": "明天要出门，你今晚会怎么处理准备工作？",
        "why": "这题观察你更偏提前安排，还是更相信现场发挥。",
        "followup": "如果临时出现变化，你会觉得计划被破坏，还是觉得终于有点意思了？",
        "options": [
            "路线、物品、时间表都提前摆好",
            "明天再说，我相信现场发挥",
            "大件先准备，小事随缘",
            "会准备，但最后五分钟还是会乱一下",
        ],
        "scores": [{"J": 2}, {"P": 2}, {"J": 1, "P": 1}, {"J": 1, "P": 1}],
    },
]

SAMPLE_QUESTIONS = [
    {
        "dimension": "睡眠质量",
        "question": "最近一周睡眠怎么样？有没有入睡困难、早醒，或者白天明显没精神？",
        "why": "这是样例调研的起点，用来判断状态是否已经影响日常精力。",
        "followup": "能说一个最近睡不好的晚上吗？大概几点睡、几点醒、醒来后什么感觉？",
        "options": ["入睡有点慢，白天容易困", "还可以，但偶尔会醒", "最近睡得比较差"],
    },
    {
        "dimension": "压力来源",
        "question": "如果用 1 到 10 分表示最近的压力，10 分最强，你大概在几分？主要来自哪里？",
        "why": "这题把模糊压力转成可比较的信息，方便 Agent 后面填问卷。",
        "followup": "这个分数背后最典型的一件事是什么？",
        "options": ["7 分左右，主要是工作", "5 分，事情多但还能扛", "8 分以上，已经影响状态"],
    },
    {
        "dimension": "生活影响",
        "question": "这种状态对你的学习、工作、社交或日常安排有什么影响？",
        "why": "问卷里真正有价值的部分，往往是状态具体影响到了哪里。",
        "followup": "如果只选一个影响最大的地方，会是效率、情绪、人际，还是身体状态？",
        "options": ["效率下降，容易拖延", "社交变少，更想一个人待着", "影响不大，但有点消耗"],
    },
    {
        "dimension": "改善目标",
        "question": "接下来一周，你最希望先改善的一件小事是什么？",
        "why": "这题用来把调研结果收束成可导出的结论和建议。",
        "followup": "这个目标如果变成一个很小的行动，第一步会是什么？",
        "options": ["先把睡眠调回来", "减少拖延，把事情排清楚", "想让情绪更稳定一点"],
    },
]

TEMPLATES = {
    "mbti": {
        "kind": "mbti",
        "title": "趣味人格测试",
        "subtitle": "轻松一点，但不随便。每一题只问当前该问的事。",
        "invite_code": "MBTI-DEMO",
        "questions": MBTI_QUESTIONS,
    },
    "sample": {
        "kind": "sample",
        "title": "快速体验样例",
        "subtitle": "用四个问题展示 DeepLister 的追问和整理能力。",
        "invite_code": "SCL90-DEMO",
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
    "ISFJ": "默默兜底但偶尔想下班的人",
    "ESTJ": "任务清仓型负责人",
    "ESFJ": "人情雷达型照顾者",
    "ISTP": "冷静拆解型问题处理器",
    "ISFP": "审美在线型自由人",
    "ESTP": "现场开麦型行动派",
    "ESFP": "快乐外放型氛围发动机",
}


def apply_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --sage: #DCEBDD;
            --forest: #2F6B4F;
            --olive: #708238;
            --mist: #F7FFF9;
            --ink: #183D2E;
        }
        .stApp {
            background:
                radial-gradient(circle at 50% 0%, rgba(247,255,249,0.92), rgba(220,235,221,0.94) 42%, #DCEBDD 100%);
            color: var(--ink);
            overflow-x: hidden;
        }
        body {
            overflow-x: hidden;
        }
        .block-container {
            max-width: 760px;
            padding: 1rem 1rem 5rem;
        }
        h1, h2, h3 {
            color: var(--forest);
            letter-spacing: 0;
        }
        h1 {
            font-size: clamp(1.9rem, 7vw, 3.2rem);
            line-height: 1.1;
        }
        [data-testid="stSidebar"] {
            background: rgba(247,255,249,0.92);
        }
        .home-hero {
            position: relative;
            padding: 0.15rem 0 0.15rem;
            overflow: hidden;
        }
        .title-lockup {
            position: relative;
            z-index: 6;
            display: flex;
            align-items: baseline;
            justify-content: center;
            gap: 0.24rem;
            margin: 0 auto -0.55rem;
        }
        .brand-title {
            margin: 0;
            font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
            font-size: clamp(1.72rem, 7.1vw, 2.58rem);
            font-weight: 850;
            line-height: 1;
            letter-spacing: 0;
            color: var(--forest);
            text-shadow: 0 5px 16px rgba(47,107,79,0.12);
        }
        .brand-subtitle {
            margin: 0;
            color: rgba(47,107,79,0.66);
            font-family: Inter, Arial, sans-serif;
            font-size: 0.78rem;
            font-weight: 650;
            letter-spacing: 0.04em;
        }
        .hero-stage {
            position: relative;
            display: grid;
            place-items: center;
            min-height: clamp(236px, 68vw, 460px);
            margin: -0.2rem auto -0.5rem;
            overflow: visible;
            isolation: isolate;
        }
        .hero-stage::before {
            content: "";
            position: absolute;
            inset: 4% -4% 5%;
            z-index: 0;
            opacity: 0.5;
            background:
                radial-gradient(ellipse at 23% 63%, rgba(255,255,255,0.72) 0 8%, transparent 34%),
                radial-gradient(ellipse at 71% 47%, rgba(255,255,255,0.58) 0 7%, transparent 30%),
                linear-gradient(126deg, transparent 0 52%, rgba(112,130,56,0.16) 52% 53%, transparent 53% 100%);
            filter: blur(0.2px);
        }
        .hero-stage::after {
            content: "";
            position: absolute;
            inset: 10% 0 2%;
            z-index: 3;
            pointer-events: none;
            opacity: 0.32;
            background:
                radial-gradient(ellipse at 10% 72%, rgba(247,255,249,0.88) 0 8%, transparent 36%),
                radial-gradient(ellipse at 83% 38%, rgba(247,255,249,0.82) 0 7%, transparent 32%);
        }
        .moon-orb {
            position: absolute;
            z-index: 1;
            top: 7%;
            right: 14%;
            width: clamp(54px, 16vw, 92px);
            aspect-ratio: 1;
            border-radius: 50%;
            background:
                radial-gradient(circle at 38% 34%, rgba(255,255,255,0.96), rgba(248,251,230,0.76) 48%, rgba(208,222,189,0.38) 76%, transparent 78%);
            box-shadow: 0 0 34px rgba(247,255,249,0.92);
            opacity: 0.72;
            animation: moonDrift 11s ease-in-out infinite;
        }
        .mist-ribbon {
            position: absolute;
            left: -8%;
            z-index: 3;
            width: 116%;
            height: 54px;
            border-radius: 999px;
            background:
                radial-gradient(ellipse at 20% 50%, rgba(247,255,249,0.58), transparent 54%),
                radial-gradient(ellipse at 58% 52%, rgba(247,255,249,0.46), transparent 48%),
                radial-gradient(ellipse at 86% 46%, rgba(247,255,249,0.42), transparent 42%);
            filter: blur(8px);
            opacity: 0.48;
            pointer-events: none;
            animation: mistFlow 14s ease-in-out infinite;
        }
        .mist-one {
            top: 42%;
        }
        .mist-two {
            top: 63%;
            animation-duration: 18s;
            animation-delay: -5s;
            opacity: 0.34;
        }
        .bamboo-grove {
            position: absolute;
            z-index: 2;
            bottom: 2%;
            width: 78px;
            height: 78%;
            pointer-events: none;
            opacity: 0.58;
            transform-origin: bottom center;
            animation: bambooSway 8.6s ease-in-out infinite;
        }
        .bamboo-left {
            left: -0.45rem;
        }
        .bamboo-right {
            right: -0.5rem;
            animation-delay: -1.9s;
        }
        .bamboo-stalk {
            position: absolute;
            bottom: 0;
            width: 7px;
            border-radius: 999px;
            background:
                repeating-linear-gradient(
                    180deg,
                    rgba(81,121,78,0.72) 0 24px,
                    rgba(229,241,215,0.82) 25px 27px,
                    rgba(81,121,78,0.72) 28px 46px
                );
            box-shadow: inset -1px 0 0 rgba(247,255,249,0.48);
        }
        .bamboo-stalk::before,
        .bamboo-stalk::after {
            content: "";
            position: absolute;
            top: 13%;
            width: 42px;
            height: 9px;
            border-radius: 100% 0 100% 0;
            background: rgba(112,130,56,0.5);
        }
        .bamboo-stalk::before {
            left: 4px;
            transform: rotate(-18deg);
        }
        .bamboo-stalk::after {
            right: 3px;
            top: 31%;
            transform: rotate(202deg);
        }
        .bamboo-stalk.one {
            left: 8px;
            height: 96%;
            transform: rotate(-5deg);
        }
        .bamboo-stalk.two {
            left: 36px;
            height: 88%;
            transform: rotate(4deg);
            opacity: 0.8;
        }
        .bamboo-stalk.three {
            left: 58px;
            height: 74%;
            transform: rotate(-2deg);
            opacity: 0.62;
        }
        .hero-figure {
            position: relative;
            z-index: 4;
            display: block;
            width: min(66vw, 450px);
            max-width: 100%;
            margin: -0.25rem auto -0.85rem;
            transform: translateX(-1.8%);
            filter: drop-shadow(0 24px 28px rgba(47,107,79,0.18));
        }
        .ambient-figure {
            position: absolute;
            z-index: 2;
            width: min(108vw, 610px);
            max-width: none;
            opacity: 0.12;
            transform: translateY(-1.2%);
            mix-blend-mode: multiply;
            pointer-events: none;
        }
        @keyframes moonDrift {
            0%, 100% { transform: translate3d(0, 0, 0); opacity: 0.7; }
            50% { transform: translate3d(-6px, 5px, 0); opacity: 0.84; }
        }
        @keyframes mistFlow {
            0%, 100% { transform: translateX(-10px); }
            50% { transform: translateX(12px); }
        }
        @keyframes bambooSway {
            0%, 100% { transform: rotate(-1.2deg); }
            50% { transform: rotate(1.8deg); }
        }
        @keyframes cardShadowFlow {
            0%, 100% { transform: translateX(-4%) rotate(0deg); }
            50% { transform: translateX(4%) rotate(1deg); }
        }
        .stImage img {
            width: min(72vw, 320px) !important;
            display: block;
            margin: 0 auto 0.4rem;
            border: 0;
            border-radius: 0;
            filter: drop-shadow(0 22px 30px rgba(47,107,79,0.18));
        }
        .home-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.35rem;
        }
        .home-card {
            position: relative;
            overflow: hidden;
            min-height: 132px;
            aspect-ratio: 1 / 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            gap: 0.7rem;
            border-radius: 8px;
            border: 1px solid rgba(247,255,249,0.95);
            background: rgba(247,255,249,0.78);
            color: var(--forest) !important;
            text-decoration: none !important;
            padding: 0.9rem;
            box-shadow: 0 14px 34px rgba(47,107,79,0.12);
        }
        .home-card::before {
            content: "";
            position: absolute;
            inset: -18%;
            z-index: 0;
            background:
                repeating-linear-gradient(
                    104deg,
                    transparent 0 36px,
                    rgba(112,130,56,0.13) 37px 39px,
                    transparent 40px 78px
                ),
                radial-gradient(ellipse at 78% 22%, rgba(112,130,56,0.12), transparent 42%);
            opacity: 0.46;
            transform: translateX(-2%);
            animation: cardShadowFlow 12s ease-in-out infinite;
            pointer-events: none;
        }
        .home-card.primary {
            background: var(--forest);
            color: var(--mist) !important;
        }
        .home-card.primary::before {
            background:
                repeating-linear-gradient(
                    104deg,
                    transparent 0 36px,
                    rgba(247,255,249,0.16) 37px 39px,
                    transparent 40px 78px
                ),
                radial-gradient(ellipse at 78% 22%, rgba(247,255,249,0.14), transparent 42%);
            opacity: 0.58;
        }
        .home-card strong {
            position: relative;
            z-index: 1;
            font-size: clamp(1.08rem, 4.6vw, 1.42rem);
            line-height: 1.18;
        }
        .home-card small {
            position: relative;
            z-index: 1;
            color: #617E70;
            line-height: 1.45;
        }
        .home-card.primary small {
            color: rgba(247,255,249,0.84);
        }
        .home-card.center {
            grid-column: 1 / span 2;
            justify-self: center;
            width: min(58%, 220px);
        }
        .sample-row {
            display: flex;
            justify-content: flex-end;
            margin-top: 0.75rem;
        }
        .sample-pill, .back-link {
            display: inline-block;
            border: 1px solid rgba(112,130,56,0.34);
            border-radius: 999px;
            color: var(--forest) !important;
            background: rgba(247,255,249,0.74);
            padding: 0.52rem 0.75rem;
            text-decoration: none !important;
            font-weight: 700;
        }
        .sample-pill {
            font-size: 0.82rem;
            padding: 0.38rem 0.58rem;
        }
        .panel, .question-card, .trace-card {
            border: 1px solid rgba(247,255,249,0.95);
            border-radius: 8px;
            background: rgba(247,255,249,0.76);
            padding: 1rem;
            box-shadow: 0 14px 36px rgba(47,107,79,0.1);
            margin: 0.75rem 0;
        }
        .question-meta {
            color: var(--olive);
            font-size: 0.88rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }
        .question-main {
            color: var(--forest);
            font-size: 1.22rem;
            font-weight: 850;
            line-height: 1.45;
        }
        .question-why {
            color: #5D7A6D;
            border-top: 1px solid rgba(112,130,56,0.18);
            margin-top: 0.8rem;
            padding-top: 0.7rem;
            line-height: 1.65;
        }
        .progress-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.5rem 0;
        }
        .progress-strip span {
            border-radius: 999px;
            background: rgba(247,255,249,0.78);
            border: 1px solid rgba(112,130,56,0.24);
            color: #4F6E60;
            padding: 0.32rem 0.56rem;
            font-size: 0.84rem;
            font-weight: 750;
        }
        div[data-testid="stTextArea"] textarea {
            min-height: 138px;
            border: 2px solid rgba(47,107,79,0.42);
            background: rgba(247,255,249,0.98);
            color: var(--ink);
            font-size: 1rem;
            border-radius: 8px;
        }
        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 8px;
            min-height: 3rem;
            font-weight: 850;
            border: 1px solid var(--forest);
            background: var(--forest);
            color: var(--mist);
        }
        div.stButton > button:hover,
        div.stDownloadButton > button:hover {
            border-color: var(--olive);
            background: var(--olive);
            color: var(--mist);
        }
        .trace-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.55rem;
        }
        .trace-card {
            margin: 0;
            box-shadow: none;
            background: rgba(247,255,249,0.66);
        }
        .trace-card b {
            display: block;
            color: var(--forest);
            margin-bottom: 0.24rem;
        }
        .trace-card span {
            color: #365D4A;
            line-height: 1.55;
        }
        .result-card {
            border-radius: 8px;
            background: var(--forest);
            color: var(--mist);
            padding: 1rem;
            margin: 0.8rem 0;
        }
        .result-card h2,
        .result-card h3 {
            color: var(--mist);
        }
        .result-card p {
            color: rgba(247,255,249,0.88);
            line-height: 1.7;
        }
        @media (min-width: 720px) {
            .trace-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 560px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }
            .home-card {
                min-height: 126px;
                padding: 0.8rem;
            }
            .home-card.center {
                width: min(64%, 210px);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sync_page() -> None:
    page = st.query_params.get("page", "home")
    st.session_state.page = page if page in ROUTES else "home"


def go_to(page: str) -> None:
    st.session_state.page = page
    st.query_params["page"] = page
    st.rerun()


def reset_agent() -> None:
    for key in ["agent", "step", "answers", "traces", "pending_followup", "mbti_scores", "completed_at"]:
        st.session_state.pop(key, None)


def image_data_url(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def make_import_agent(file_name: str) -> dict:
    return {
        "kind": "imported",
        "title": "导入问卷 Agent",
        "subtitle": f"已根据《{file_name}》生成演示 Agent。",
        "invite_code": st.session_state.get("import_code", "DL-2026"),
        "questions": [
            {
                "dimension": "调研目标",
                "question": "这份问卷最想了解的核心问题是什么？",
                "why": "先锁定调研目标，后续追问才不会跑偏。",
                "followup": "如果只能把目标写成一句问卷说明，你会怎么写？",
                "options": ["了解用户真实需求", "评估体验满意度", "判断方案是否可行"],
            },
            {
                "dimension": "使用场景",
                "question": "被调研者最典型的一个使用场景是什么？",
                "why": "场景越具体，Agent 最后填出的问卷越像真实访谈结果。",
                "followup": "这个场景通常发生在什么时候、什么地点、用户正在做什么？",
                "options": ["第一次接触产品", "完成一次任务后", "遇到问题反馈时"],
            },
            {
                "dimension": "追问重点",
                "question": "你最希望 Agent 追问清楚哪类细节？",
                "why": "这决定了 Agent 后续是追原因、追例子，还是追建议。",
                "followup": "为什么这类细节对你的问卷最重要？",
                "options": ["原因和动机", "具体例子", "改进建议"],
            },
        ],
    }


def make_invite_agent(code: str) -> dict:
    if code == "MBTI-DEMO":
        return deepcopy(TEMPLATES["mbti"])
    if code == "SCL90-DEMO":
        return deepcopy(TEMPLATES["sample"])
    agent = deepcopy(TEMPLATES["sample"])
    agent["kind"] = "invite"
    agent["title"] = "他人制作的调研 Agent"
    agent["subtitle"] = f"邀请码：{code}"
    agent["invite_code"] = code
    return agent


def start_agent(kind: str, *, file_name: str | None = None, invite_code: str | None = None) -> None:
    if kind == "imported":
        agent = make_import_agent(file_name or "导入问卷")
    elif kind == "invite":
        agent = make_invite_agent((invite_code or "SCL90-DEMO").strip().upper())
    else:
        agent = deepcopy(TEMPLATES[kind])

    st.session_state.agent = agent
    st.session_state.step = 0
    st.session_state.answers = []
    st.session_state.traces = []
    st.session_state.pending_followup = False
    st.session_state.mbti_scores = {letter: 0 for letter in "EISNTFJP"}
    st.session_state.completed_at = None


def current_agent() -> dict:
    if "agent" not in st.session_state:
        start_agent("sample")
    return st.session_state.agent


def current_question() -> dict:
    agent = current_agent()
    step = min(st.session_state.get("step", 0), len(agent["questions"]) - 1)
    return agent["questions"][step]


def is_vague(text: str) -> bool:
    text = text.strip()
    vague_words = ["还行", "一般", "还好", "不知道", "差不多", "随便"]
    return len(text) <= 8 or any(word in text for word in vague_words)


def add_scores(scores: dict | None) -> None:
    if not scores:
        return
    for letter, value in scores.items():
        st.session_state.mbti_scores[letter] = st.session_state.mbti_scores.get(letter, 0) + value


def make_trace(question: dict, answer: str, action: str, generated: str) -> dict:
    vague = is_vague(answer)
    return {
        "dimension": question["dimension"],
        "question": question["question"],
        "answer": answer,
        "detection": "回答偏短，需要补一个具体场景。" if vague else "回答包含可整理信息，可以进入结构化提取。",
        "arbitration": "提出一次追问" if action == "followup" else "进入下一题",
        "generation": generated,
        "verification": "已校验：只生成当前问题相关内容，不添加额外闲聊或转场。",
    }


def submit_answer(answer: str, scores: dict | None = None) -> None:
    answer = answer.strip()
    if not answer:
        return

    agent = current_agent()
    step = st.session_state.get("step", 0)
    question = current_question()
    was_followup = st.session_state.get("pending_followup", False)

    if agent["kind"] == "mbti":
        add_scores(scores)

    if (not was_followup) and is_vague(answer):
        st.session_state.pending_followup = True
        st.session_state.traces.append(make_trace(question, answer, "followup", question["followup"]))
        st.rerun()

    st.session_state.answers.append(
        {
            "dimension": question["dimension"],
            "question": question["question"],
            "answer": answer,
            "was_followup": was_followup,
        }
    )
    st.session_state.traces.append(make_trace(question, answer, "proceed", "整理本题回答，并进入下一题。"))
    st.session_state.pending_followup = False
    st.session_state.step = step + 1

    if st.session_state.step >= len(agent["questions"]):
        st.session_state.completed_at = datetime.now().isoformat(timespec="seconds")
        go_to("complete")
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
        code = mbti_type()
        title = RESULT_TITLES.get(code, "清醒发电型选手")
        return {
            "headline": f"经过测试，你的人格是：{code}",
            "title": title,
            "description": f"你像是“{title}”。DeepLister 已经把你的回答整理成可导出的已填写问卷。",
        }
    return {
        "headline": "恭喜你完成调研",
        "title": "Agent 已整理出已填写问卷",
        "description": "下面可以导出结果，也可以逐题查看 DeepLister 的四层处理过程。",
    }


def export_payload() -> str:
    agent = current_agent()
    payload = {
        "product": "DeepLister",
        "agent": agent["title"],
        "invite_code": agent.get("invite_code"),
        "completed_at": st.session_state.get("completed_at"),
        "result": result_summary(),
        "filled_questionnaire": [
            {
                "dimension": item["dimension"],
                "question": item["question"],
                "agent_filled_answer": item["answer"],
            }
            for item in st.session_state.get("answers", [])
        ],
        "four_layer_trace": st.session_state.get("traces", []),
    }
    if agent["kind"] == "mbti":
        payload["mbti_type"] = mbti_type()
        payload["mbti_scores"] = st.session_state.get("mbti_scores", {})
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_sidebar() -> None:
    st.sidebar.title("DeepLister")
    st.sidebar.caption("追问式问卷 Agent Demo")
    if st.sidebar.button("回到首页", use_container_width=True):
        reset_agent()
        go_to("home")
    st.sidebar.markdown("演示邀请码")
    st.sidebar.code("MBTI-DEMO\nSCL90-DEMO")


def render_trace(trace: dict) -> None:
    st.markdown(
        f"""
        <div class="trace-grid">
          <div class="trace-card"><b>1. 检测层</b><span>{trace["detection"]}</span></div>
          <div class="trace-card"><b>2. 仲裁层</b><span>{trace["arbitration"]}</span></div>
          <div class="trace-card"><b>3. 生成层</b><span>{trace["generation"]}</span></div>
          <div class="trace-card"><b>4. 校验层</b><span>{trace["verification"]}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    reset_agent()
    hero_src = image_data_url(HOST_IMAGE)
    ambient_src = image_data_url(AMBIENT_IMAGE)
    ambient_img = f'<img class="ambient-figure" src="{ambient_src}" alt="">' if ambient_src else ""
    hero_img = f'<img class="hero-figure" src="{hero_src}" alt="聆听者首页主视觉">' if hero_src else ""
    st.markdown(
        f"""
        <div class="home-hero">
          <div class="title-lockup">
            <h1 class="brand-title">聆听者</h1>
            <p class="brand-subtitle">DeepLister</p>
          </div>
          <div class="hero-stage">
            <div class="moon-orb"></div>
            <div class="bamboo-grove bamboo-left">
              <span class="bamboo-stalk one"></span>
              <span class="bamboo-stalk two"></span>
              <span class="bamboo-stalk three"></span>
            </div>
            <div class="bamboo-grove bamboo-right">
              <span class="bamboo-stalk one"></span>
              <span class="bamboo-stalk two"></span>
              <span class="bamboo-stalk three"></span>
            </div>
            <div class="mist-ribbon mist-one"></div>
            <div class="mist-ribbon mist-two"></div>
            {ambient_img}
            {hero_img}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="home-grid">
          <a class="home-card primary" href="?page=import">
            <strong>导入测试</strong>
            <small>上传问卷，生成调研 Agent 和邀请码</small>
          </a>
          <a class="home-card" href="?page=invite">
            <strong>输入邀请码</strong>
            <small>进入别人制作好的调研 Agent</small>
          </a>
          <a class="home-card center" href="?page=mbti">
            <strong>MBTI测试</strong>
            <small>趣味人格测试样例</small>
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

    st.session_state.import_code = f"DL-{abs(hash(uploaded.name)) % 9000 + 1000}"
    st.markdown(
        f"""
        <div class="panel">
          <b>已生成调研 Agent</b>
          <p>{uploaded.name}</p>
          <p>邀请码：<b>{st.session_state.import_code}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("开始作答", use_container_width=True):
        start_agent("imported", file_name=uploaded.name)
        go_to("agent")


def render_invite() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("请输入邀请码")
    code = st.text_input("邀请码", placeholder="例如 MBTI-DEMO 或 SCL90-DEMO", label_visibility="collapsed")
    if st.button("进入调研 Agent", use_container_width=True):
        start_agent("invite", invite_code=code or "SCL90-DEMO")
        go_to("agent")


def render_agent() -> None:
    agent = current_agent()
    step = st.session_state.get("step", 0)
    question = current_question()
    total = len(agent["questions"])
    is_followup = st.session_state.get("pending_followup", False)
    prompt = question["followup"] if is_followup else question["question"]

    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title(agent["title"])
    st.caption(agent["subtitle"])
    st.markdown(
        f"""
        <div class="progress-strip">
          <span>{min(step + 1, total)} / {total}</span>
          <span>{question["dimension"]}</span>
          <span>邀请码 {agent.get("invite_code", "DL-DEMO")}</span>
        </div>
        <div class="question-card">
          <div class="question-meta">{'追问' if is_followup else '问题'} · {question["dimension"]}</div>
          <div class="question-main">{prompt}</div>
          <div class="question-why">{question["why"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    answer = st.text_area("输入回答", placeholder="请在这里写你的回答。这个输入区是主要操作。", key=f"answer_{step}_{is_followup}")
    if st.button("提交回答", use_container_width=True):
        submit_answer(answer)

    with st.expander("没有思路？展开快速选择", expanded=False):
        st.caption("快速选择只是辅助，建议优先自己输入。")
        for index, option in enumerate(question.get("options", [])):
            score = None
            if agent["kind"] == "mbti":
                score = question.get("scores", [{}])[index]
            if st.button(option, key=f"quick_{step}_{is_followup}_{index}", use_container_width=True):
                submit_answer(option, score)

    if st.session_state.get("traces"):
        with st.expander("开箱上一题四层架构", expanded=False):
            render_trace(st.session_state.traces[-1])


def render_complete() -> None:
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
        st.image(str(HOST_IMAGE), use_container_width=False)
    st.download_button(
        "导出已填写问卷",
        data=export_payload(),
        file_name=f"deeplister-filled-questionnaire.json",
        mime="application/json",
        use_container_width=True,
    )
    for index, trace in enumerate(st.session_state.get("traces", []), start=1):
        with st.expander(f"第 {index} 次处理 · 四层架构开箱", expanded=False):
            render_trace(trace)


def handle_direct_routes() -> None:
    if st.session_state.page == "mbti":
        start_agent("mbti")
        go_to("agent")
    if st.session_state.page == "sample":
        start_agent("sample")
        go_to("agent")


def main() -> None:
    st.set_page_config(page_title="DeepLister Demo", layout="centered")
    apply_style()
    sync_page()
    handle_direct_routes()
    render_sidebar()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "import":
        render_import()
    elif page == "invite":
        render_invite()
    elif page == "agent":
        render_agent()
    elif page == "complete":
        render_complete()
    else:
        render_home()


if __name__ == "__main__":
    main()
