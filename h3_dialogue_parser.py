"""把 MiniMax H3 分镜提示词中的显式对白转为 IndexTTS 2.5 批量 JSON。
纯 Python 标准库实现。只分析显式对白，不擅自写台词；情绪按邻近文本规则提取。
"""
from __future__ import annotations
import json
import re
from typing import Optional

LANG_MAP = {'Chinese':'ZH','中文':'ZH','Mandarin':'ZH','ZH':'ZH',
            'English':'EN','EN':'EN','Japanese':'JA','JA':'JA','日语':'JA',
            'Korean':'KO','KO':'KO','韩语':'KO','粤语':'YUE','YUE':'YUE'}
ROLE_RE = re.compile(r'(?:角色\s*([ABC])|<Subject\s*([123])>|(?<![a-zA-Z0-9])S([123])(?![a-zA-Z0-9]))', re.I)
D_TAG_RE = re.compile(r'<d(?:\s+[^>]*)?>\s*(?:\[([^\]]+)\])?\s*(.*?)\s*</d>', re.I | re.S)
QUOTES = re.compile(r'(?P<start>[『「“])(?P<speech>[^』」”\n]{1,400})(?P<end>[』」”])')
QUOTEP = {'『':'』','「':'」','“':'”'}
SPEECH_VERBS = re.compile(r'(?:说|道|喊|吼|叫|问|答|回答|质问|命令|喝令|怒斥|轻声|说道|喊道|反问|嘀咕|开口|念道|says?|replies?|commands?|speaks?|shouts?|asks?)', re.I)
EMO_CUES = (
    (r'(?:怒吼|暴怒|愤怒|生气|恼火|气愤|咆哮|怒斥|质问|angrily|furious|furiously)', '愤怒、质问', .82),
    (r'(?:焦急|着急|紧张|急促|慌张|急切|anxious|urgently|worried)', '焦急、急切', .75),
    (r'(?:悲伤|难过|哽咽|哭泣|抽泣|心痛|sobbing|sadly)', '悲伤、哽咽', .77),
    (r'(?:惊讶|震惊|惊呼|不敢相信|surprised|shocked)', '惊讶、错愕', .76),
    (r'(?:冷静|平静|镇定|从容|淡淡地|calm|calmly)', '冷静、平稳', .62),
    (r'(?:坚定|坚决|认真|郑重|严肃|firmly|sternly|determined)', '坚定、认真', .70),
    (r'(?:开心|高兴|兴奋|激动|欢快|大笑|嬉笑|happy|cheerful)', '开心、兴奋', .74),
    (r'(?:低声|轻声|温柔|柔声|耳语|whisper|softly|gently)', '轻声、温柔', .61),
    (r'(?:讽刺|嘲笑|轻蔑|不屑|冷笑|讥讽|mock|sarcastic|contempt)', '轻蔑、讥讽', .76),
)


def _aliases(aliases_json: str) -> dict[str, str]:
    if not (aliases_json or '').strip():
        return {}
    aliases = json.loads(aliases_json)
    if not isinstance(aliases, dict):
        raise ValueError('角色别名必须是 JSON 对象，例如 {"七七":"角色A"}')
    legal = {'角色A','角色B','角色C'}
    out = {}
    for alias, role in aliases.items():
        if not isinstance(alias, str) or not isinstance(role, str) or role not in legal:
            raise ValueError('角色别名映射的值必须是角色A、角色B或角色C')
        if alias.strip():
            out[alias.strip()] = role
    return out


def _pick_role(prompt: str, start: int, end: int, default_role: str, aliases: dict[str, str]):
    left = prompt[max(0,start-230):start]
    right = prompt[end:min(len(prompt),end+45)]
    choices=[]
    for m in ROLE_RE.finditer(left):
        ix = m.group(1) or m.group(2) or m.group(3)
        role = '角色'+('ABC'[int(ix)-1] if ix.isdigit() else ix.upper())
        choices.append((m.end(),role))
    for alias,role in aliases.items():
        for m in re.finditer(re.escape(alias),left):
            choices.append((m.end(),role))
    if choices:
        return max(choices)[1], '左侧人物标记'
    # 只有在后接发言动词时才接受引号后说话人的标记
    for alias,role in aliases.items():
        if re.search(r'\b'+re.escape(alias)+r'\s*(?:说|道|问|喊)',right):
            return role,'对白后人物别名'
    return default_role, '默认角色'


def _pick_emotion(prompt: str, start: int, end: int, content: str):
    # 不跨前一条对白取情绪；优先靠近本句的文本
    left = prompt[max(0,start-150):start]
    left = re.split(r'</d>|[』」”]|\[Shot\s*\d+\]|【镜头\d+】', left)[-1]
    right = prompt[end:min(len(prompt),end+30)]
    tags = list(re.finditer(r'(?:【|\[)(?:情绪|Emotion)\s*[:：]\s*([^】\]]{1,55})(?:】|\])',left,re.I))
    if tags:
        return tags[-1].group(1).strip(), .75, '情绪显式标签'
    patterns=[
        r'(?:用|以|带着|带有)([^，。；：\n]{1,32}?)(?:的)?(?:语气|口吻|声音)(?:说|喊|问|回答|命令|喝令)?',
        r'([^，。；：\n]{1,26}?)地(?:说|回答|命令|喊|质问|喝令|问|道)',
    ]
    for rg in patterns:
        matches=list(re.finditer(rg,left))
        if matches:
            v=matches[-1].group(1).strip(' ：，、。')
            # 提取过长上下文容易污染情绪，截取词尾的短描述
            if len(v)>20:
                v=re.split('[，、。]',v)[-1][-20:]
            v=re.sub(r'^角色\s*[ABC]', '', v)
            v=re.split(r'(?:之后|随后|然后|后)(?=[^后]*$)', v)[-1]
            v=v.strip(' ：，、。')
            if v:
                strength=.72
                powers=[power for rx,_,power in EMO_CUES if re.search(rx,v,re.I)]
                if powers: strength=max(powers)
                return v,strength,'语气描述'
    window=left[-90:]+right[:20]
    hits=[]
    for rx,mood,power in EMO_CUES:
        m=list(re.finditer(rx,window,re.I))
        if m:
            hits.append((m[-1].start(),mood,power))
    if hits:
        _,mood,power=max(hits)
        return mood,power,'表演/语言关键词'
    # 最后仅从标点推断最低限度语气，不捏造人物心理
    if '！' in content or '!' in content:
        return '有力、清晰',.62,'感叹号启发式'
    if '？' in content or '?' in content:
        return '疑问、自然',.58,'问号启发式'
    return '自然、平稳',.57,'默认中性'


def _clean_dialogue(txt: str) -> str:
    txt = re.sub(r'^\s*\[(?:Chinese|中文|Mandarin|English|ZH|EN|Japanese|JA)\]\s*','',txt,flags=re.I)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def extract_h3_dialogue(prompt: str, default_role: str='角色A', aliases_json: str='', strict: bool=True, allow_multi_role: bool=False):
    """Returns (T8 DialogueScript JSON string, human-readable report JSON)."""
    if default_role not in {'角色A','角色B','角色C'}:
        raise ValueError('default_role 必须是角色A、角色B、角色C')
    prompt = (prompt or '').replace('\r\n','\n')
    aliases=_aliases(aliases_json)
    found=[]
    spans=[]
    for m in D_TAG_RE.finditer(prompt):
        content=_clean_dialogue(m.group(2))
        if content:
            lang=LANG_MAP.get((m.group(1) or '').strip(), 'ZH')
            found.append((m.start(),m.end(),content,lang,'<d>'))
            spans.append((m.start(),m.end()))
    for m in QUOTES.finditer(prompt):
        if QUOTEP.get(m.group('start')) != m.group('end'):
            continue
        if any(a<=m.start()<b for a,b in spans): continue
        context=prompt[max(0,m.start()-90):min(len(prompt),m.end()+25)]
        # 显式对白动词是识别条件，防止把剧名/摄影参数当台词
        if not SPEECH_VERBS.search(context): continue
        content=_clean_dialogue(m.group('speech'))
        if content:
            found.append((m.start(),m.end(),content,'ZH','引号'))
    found.sort(key=lambda x:x[0])
    rows=[]; details=[]
    for start,end,content,lang,kind in found:
        role,how=_pick_role(prompt,start,end,default_role,aliases)
        emotion,strength,emode=_pick_emotion(prompt,start,end,content)
        row={'role':role,'text':content,'language':lang,'duration_factor':1.0,
             'emotion':{'mode':'text','text':emotion,'strength':strength}}
        rows.append(row)
        details.append({'role':role,'text':content,'source':kind,'speaker_source':how,'emotion_source':emode,'emotion':emotion})
    if strict and not rows:
        raise ValueError('H3 提示词中未发现明确对白。请使用 角色A说：「台词」 或 <d>[Chinese] 台词</d>。')
    distinct=sorted({r['role'] for r in rows})
    if not allow_multi_role and len(distinct)>1:
        raise ValueError('同一H3镜头提取到多个说话角色：'+','.join(distinct)+'。请拆分镜头，或启用allow_multi_role并接受嘴型同步风险。')
    report={'count':len(rows),'roles':distinct,'details':details,
            'note':'情绪是规则提取，并非AI语义理解；TTS长度和H3时长仍须匹配。'}
    return json.dumps(rows,ensure_ascii=False,indent=2),json.dumps(report,ensure_ascii=False,indent=2)
