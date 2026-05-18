from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.providers.staticdata.models import (
    AscensionTier,
    CharacterData,
    CharacterStats,
    ConstellationInfo,
    PassiveInfo,
    SkillInfo,
    TalentInfo,
    TalentTier,
)

# ── cost templates ─────────────────────────────────────────────────

GEMS = {
    "火": "燃愿玛瑙", "水": "涤净青金", "冰": "哀叙冰玉",
    "雷": "最胜紫晶", "风": "自在松石", "岩": "坚牢黄玉", "草": "生长碧翡",
}
GEM_SUFFIX = ["碎屑", "断片", "块", ""]  # index 0..3

DOMAINS = {
    "自由": ("忘却之峡", ["周一", "周四", "周日"]),
    "抗争": ("忘却之峡", ["周二", "周五", "周日"]),
    "诗文": ("忘却之峡", ["周三", "周六", "周日"]),
    "繁荣": ("太山府", ["周一", "周四", "周日"]),
    "勤劳": ("太山府", ["周二", "周五", "周日"]),
    "黄金": ("太山府", ["周三", "周六", "周日"]),
    "浮世": ("堇色之庭", ["周一", "周四", "周日"]),
    "风雅": ("堇色之庭", ["周二", "周五", "周日"]),
    "天光": ("堇色之庭", ["周三", "周六", "周日"]),
    "诤言": ("昏识塔", ["周一", "周四", "周日"]),
    "巧思": ("昏识塔", ["周二", "周五", "周日"]),
    "笃行": ("昏识塔", ["周三", "周六", "周日"]),
    "公平": ("苍白的遗迹", ["周一", "周四", "周日"]),
    "正义": ("苍白的遗迹", ["周二", "周五", "周日"]),
    "秩序": ("苍白的遗迹", ["周三", "周六", "周日"]),
    "焚燔": ("燃愿的圣境", ["周一", "周四", "周日"]),
    "角逐": ("燃愿的圣境", ["周二", "周五", "周日"]),
    "贡祭": ("燃愿的圣境", ["周三", "周六", "周日"]),
}

DROPS = {
    "史莱姆": ("史莱姆凝液", "史莱姆清", "史莱姆原浆"),
    "面具": ("破损的面具", "污秽的面具", "不祥的面具"),
    "箭簇": ("牢固的箭簇", "锐利的箭簇", "历战的箭簇"),
    "绘卷": ("导能绘卷", "封魔绘卷", "禁咒绘卷"),
    "徽记": ("新兵的徽记", "士官的徽记", "尉官的徽记"),
    "骨片": ("脆弱的骨片", "结实的骨片", "石化的骨片"),
    "混沌": ("混沌装置", "混沌回路", "混沌炉心"),
    "棱镜": ("黯淡棱镜", "水晶棱镜", "偏光棱镜"),
    "花蜜": ("骗骗花蜜", "微光花蜜", "原素花蜜"),
    "鸦印": ("寻宝鸦印", "藏银鸦印", "攫金鸦印"),
    "菌核": ("失活菌核", "休眠菌核", "茁壮菌核"),
    "红绸": ("褪色红绸", "镶边红绸", "织金红绸"),
    "齿轮": ("啮合齿轮", "正齿轮", "机关正齿轮"),
}

# Ascension cost template — mora / gem index / counts are fixed for all characters.
_ASC = [
    ("20→40",  20_000,  0, 3, 0, False),
    ("40→50",  40_000,  1, 10, 0, True, 2),
    ("50→60",  60_000,  1, 20, 1, True, 4),
    ("60→70",  80_000,  2, 30, 1, True, 8),
    ("70→80",  100_000, 2, 45, 2, True, 12),
    ("80→90",  120_000, 3, 60, 2, True, 20),
]
#  level     mora     gem_idx spec drop_idx has_boss boss_cnt

_TAL = [
    ("2→3",   12_500,  0, 0, 6, False),
    ("3→4",   17_500,  1, 1, 3, False),
    ("4→5",   25_000,  1, 1, 4, False),
    ("5→6",   30_000,  1, 1, 6, False),
    ("6→7",   37_500,  1, 1, 9, False),
    ("7→8",   45_000,  2, 2, 4, True, 1),
    ("8→9",   55_000,  2, 2, 8, True, 1),
    ("9→10",  65_000,  2, 2, 12, True, 2),
]
#  level     mora     book_idx drop_idx cnt has_weekly wk_cnt

# ── alias map ───────────────────────────────────────────────────────

_ALIASES: dict[str, str] = {
    "hutao": "胡桃", "ht": "胡桃", "ganyu": "甘雨",
    "ayaka": "神里绫华", "kamisato ayaka": "神里绫华",
    "raiden": "雷电将军", "raiden shogun": "雷电将军", "ei": "雷电将军",
    "zhongli": "钟离", "venti": "温迪", "xiao": "魈",
    "kazuha": "枫原万叶", "kaedehara kazuha": "枫原万叶",
    "yelan": "夜兰", "furina": "芙宁娜", "focalors": "芙宁娜",
    "neuvillette": "那维莱特", "navia": "娜维娅",
    "arle": "阿蕾奇诺", "arlecchino": "阿蕾奇诺", "father": "阿蕾奇诺",
    "mavuika": "玛薇卡", "citlali": "茜特菈莉", "xilonen": "希诺宁",
    "kinich": "基尼奇", "mualani": "玛拉妮",
    "clorinde": "克洛琳德", "sigewinne": "希格雯",
    "alhaitham": "艾尔海森", "nahida": "纳西妲",
    "lesser lord kusanali": "纳西妲", "nilou": "妮露", "cyno": "赛诺",
    "dehya": "迪希雅", "tighnari": "提纳里",
    "itto": "荒泷一斗", "arataki itto": "荒泷一斗",
    "ayato": "神里绫人", "kamisato ayato": "神里绫人",
    "yoimiya": "宵宫", "kokomi": "珊瑚宫心海",
    "sangonomiya kokomi": "珊瑚宫心海", "shenhe": "申鹤",
    "eula": "优菈", "albedo": "阿贝多", "klee": "可莉",
    "diluc": "迪卢克", "jean": "琴", "mona": "莫娜",
    "keqing": "刻晴", "qiqi": "七七", "bennett": "班尼特",
    "xiangling": "香菱", "xingqiu": "行秋", "fischl": "菲谢尔",
    "beidou": "北斗", "ningguang": "凝光", "noelle": "诺艾尔",
    "sucrose": "砂糖", "razor": "雷泽", "chongyun": "重云",
    "xinyan": "辛焱", "diona": "迪奥娜", "lisa": "丽莎",
    "kaeya": "凯亚", "amber": "安柏",
    "traveler": "旅行者", "lumine": "旅行者", "aether": "旅行者",
    # Common Chinese nicknames / titles
    "影": "雷电将军",
    "心海": "珊瑚宫心海",
    "绫华": "神里绫华",
    "绫人": "神里绫人",
    "万叶": "枫原万叶",
    "一斗": "荒泷一斗",
    "八重": "八重神子",
    "神子": "八重神子",
    "阿散": "流浪者",
    "那维": "那维莱特",
    "芙芙": "芙宁娜",
    "娜维": "娜维娅",
    "仆人": "阿蕾奇诺",
    "克洛琳德": "克洛琳德",
    "希格雯": "希格雯",
    "艾梅莉埃": "艾梅莉埃",
    "调香师": "艾梅莉埃",
    "莱欧": "莱欧斯利",
    "莱欧斯利": "莱欧斯利",
    "千织": "娜维娅",
    "舞狮": "嘉明",
    # Archon titles
    "火神": "玛薇卡",
    "水神": "芙宁娜",
    "草神": "纳西妲",
    "风神": "温迪",
    "岩神": "钟离",
    "雷神": "雷电将军", "将军": "雷电将军",
    "帝君": "钟离",
    "老爷子": "钟离",
    "钟离": "钟离",
    "狼王": "安德留斯", "北风狼": "安德留斯", "北风狼王": "安德留斯",
    "andrius": "安德留斯", "boreas": "安德留斯", "风狼": "安德留斯",
    "风魔龙": "特瓦林", "dvalin": "特瓦林",
    "azhdaha": "若陀龙王", "signora": "「女士」",
    "tartaglia": "「公子」", "childe": "「公子」", "达达利亚": "「公子」",
    "散兵": "正机之神", "流浪者": "正机之神",
    "scaramouche": "正机之神", "wanderer": "正机之神",
    "草龙": "阿佩普的绿洲守望者", "apep": "阿佩普的绿洲守望者",
    "阿佩普": "阿佩普的绿洲守望者",
    "鲸鱼": "吞星之鲸", "巨鲸": "吞星之鲸",
    "仆人": "「仆人」", "阿蕾奇诺": "「仆人」",
    "风无相": "无相之风", "雷无相": "无相之雷",
    "岩无相": "无相之岩", "水无相": "无相之水",
    "火无相": "无相之火", "冰无相": "无相之冰",
    "冰树": "急冻树", "火树": "爆炎树",
    "纯水": "纯水精灵", "oceanid": "纯水精灵",
    "古岩龙蜥": "古岩龙蜥", "primo geovishap": "古岩龙蜥", "龙蜥": "古岩龙蜥",
    "剑鬼": "魔偶剑鬼", "maguu kenki": "魔偶剑鬼",
    "无相铁": "恒常机关阵列", "机关阵列": "恒常机关阵列", "pma": "恒常机关阵列",
    "雷音权现": "雷音权现", "thunder manifestation": "雷音权现",
    "鸡哥": "翠翎恐蕈", "蘑菇鸡": "翠翎恐蕈", "terrorshroom": "翠翎恐蕈",
    "矩阵": "半永恒统辖矩阵", "沙虫": "风蚀沙虫", "wenut": "风蚀沙虫",
    "setekh wenut": "风蚀沙虫", "浸礼者": "深罪浸礼者", "baptist": "深罪浸礼者",
    "螃蟹": "铁甲熔火帝皇", "帝皇": "铁甲熔火帝皇",
    "冰风": "冰风组曲", "力场发生器": "实验性力场发生器",
    "火龙": "金焰绒翼龙首领", "绒翼龙": "金焰绒翼龙首领",
    "灵视": "灵视之主", "wayob": "灵视之主", "摹结株": "深邃摹结株",
}

# ── compact character mapping ──────────────────────────────────────
# (name, element, weapon, rarity, specialty, drop_series, boss_mat,
#  talent_book, weekly_mat)
# Cost amounts are universal — only these 9 fields differ per character.

_CHARACTERS: list[tuple[str, str, str, int, str, str, str, str, str]] = [
    # ── Mondstadt ★５ ──
    ("迪卢克", "火", "双手剑", 5, "小灯草", "徽记", "常燃火种", "抗争", "东风的翎羽"),
    ("琴", "风", "单手剑", 5, "蒲公英籽", "骨片", "飓风之种", "抗争", "东风的吐息"),
    ("温迪", "风", "弓", 5, "塞西莉亚花", "史莱姆", "飓风之种", "诗文", "东风的尾羽"),
    ("可莉", "火", "法器", 5, "慕风蘑菇", "绘卷", "常燃火种", "自由", "东风的吐息"),
    ("莫娜", "水", "法器", 5, "慕风蘑菇", "史莱姆", "纯净之水", "诗文", "北风之环"),
    ("七七", "冰", "单手剑", 5, "琉璃袋", "绘卷", "极寒之核", "抗争", "北风之尾"),
    ("优菈", "冰", "双手剑", 5, "蒲公英籽", "骨片", "晶凝之华", "抗争", "龙王之冕"),
    ("阿贝多", "岩", "单手剑", 5, "塞西莉亚花", "骨片", "玄岩之塔", "诗文", "吞天之鲸·只角"),
    ("埃洛伊", "冰", "弓", 5, "晶化骨髓", "混沌", "极寒之核", "自由", "熔毁之刻"),
    # ── Mondstadt ★４ ──
    ("安柏", "火", "弓", 4, "小灯草", "箭簇", "常燃火种", "自由", "东风的吐息"),
    ("凯亚", "冰", "单手剑", 4, "塞西莉亚花", "徽记", "极寒之核", "诗文", "北风之环"),
    ("丽莎", "雷", "法器", 4, "慕风蘑菇", "绘卷", "雷光棱镜", "诗文", "北风之环"),
    ("班尼特", "火", "单手剑", 4, "风车菊", "面具", "常燃火种", "抗争", "东风的尾羽"),
    ("香菱", "火", "长柄武器", 4, "绝云椒椒", "史莱姆", "常燃火种", "勤劳", "东风的吐息"),
    ("雷泽", "雷", "双手剑", 4, "钩钩果", "面具", "雷光棱镜", "抗争", "东风的翎羽"),
    ("菲谢尔", "雷", "弓", 4, "小灯草", "箭簇", "雷光棱镜", "诗文", "北风之环"),
    ("芭芭拉", "水", "法器", 4, "慕风蘑菇", "绘卷", "纯净之水", "自由", "北风之环"),
    ("重云", "冰", "双手剑", 4, "石珀", "面具", "极寒之核", "抗争", "东风的翎羽"),
    ("诺艾尔", "岩", "双手剑", 4, "石珀", "骨片", "玄岩之塔", "抗争", "北风之尾"),
    ("砂糖", "风", "法器", 4, "风车菊", "花蜜", "飓风之种", "自由", "东风的吐息"),
    ("迪奥娜", "冰", "弓", 4, "钩钩果", "箭簇", "极寒之核", "自由", "北风之环"),
    ("辛焱", "火", "双手剑", 4, "琉璃百合", "面具", "常燃火种", "诗文", "东风的尾羽"),
    ("罗莎莉亚", "冰", "长柄武器", 4, "钩钩果", "徽记", "极寒之核", "诗文", "北风之尾"),
    # ── Liyue ★５ ──
    ("胡桃", "火", "长柄武器", 5, "霓裳花", "花蜜", "常燃火种", "繁荣", "魔王之刃·残片"),
    ("甘雨", "冰", "弓", 5, "清心", "骨片", "极寒之核", "勤劳", "龙王之冕"),
    ("魈", "风", "长柄武器", 5, "清心", "史莱姆", "飓风之种", "勤劳", "北风之尾"),
    ("钟离", "岩", "长柄武器", 5, "石珀", "史莱姆", "玄岩之塔", "黄金", "吞天之鲸·只角"),
    ("刻晴", "雷", "单手剑", 5, "霓裳花", "骨片", "雷光棱镜", "繁荣", "北风之尾"),
    ("申鹤", "冰", "长柄武器", 5, "清心", "徽记", "晶凝之华", "繁荣", "熔毁之刻"),
    ("夜兰", "水", "弓", 5, "星螺", "徽记", "排异之露", "繁荣", "凶将之手眼"),
    ("白术", "草", "法器", 5, "琉璃袋", "骨片", "苍砾蕊羽", "黄金", "凶将之手眼"),
    ("闲云", "风", "法器", 5, "清心", "骨片", "苍砾蕊羽", "勤劳", "原初绿洲之初绽"),
    # ── Liyue ★４ ──
    ("行秋", "水", "单手剑", 4, "霓裳花", "骨片", "纯净之水", "黄金", "魔王之刃·残片"),
    ("北斗", "雷", "双手剑", 4, "夜泊石", "骨片", "雷光棱镜", "黄金", "北风之尾"),
    ("凝光", "岩", "法器", 4, "夜泊石", "徽记", "玄岩之塔", "繁荣", "北风之环"),
    ("烟绯", "火", "法器", 4, "霓裳花", "鸦印", "常燃火种", "黄金", "魔王之刃·残片"),
    ("云堇", "岩", "长柄武器", 4, "星螺", "面具", "玄岩之塔", "勤劳", "凶将之手眼"),
    ("瑶瑶", "草", "长柄武器", 4, "绝云椒椒", "骨片", "生长的苍砾", "勤劳", "原初绿洲之初绽"),
    ("嘉明", "火", "双手剑", 4, "星螺", "骨片", "常燃火种", "繁荣", "原初绿洲之初绽"),
    # ── Inazuma ★５ ──
    ("神里绫华", "冰", "单手剑", 5, "绯樱绣球", "徽记", "恒常机关之心", "风雅", "凶将之手眼"),
    ("雷电将军", "雷", "长柄武器", 5, "天云草实", "绘卷", "雷霆数珠", "天光", "熔毁之刻"),
    ("枫原万叶", "风", "单手剑", 5, "海灵芝", "面具", "魔偶机心", "风雅", "魔王之刃·残片"),
    ("珊瑚宫心海", "水", "法器", 5, "珊瑚真珠", "史莱姆", "排异之露", "浮世", "熔毁之刻"),
    ("荒泷一斗", "岩", "双手剑", 5, "鬼兜虫", "史莱姆", "玄岩之塔", "风雅", "凶将之手眼"),
    ("神里绫人", "水", "单手剑", 5, "绯樱绣球", "徽记", "排异之露", "风雅", "凶将之手眼"),
    ("宵宫", "火", "弓", 5, "鸣草", "绘卷", "阴燃之珠", "浮世", "魔王之刃·残片"),
    ("八重神子", "雷", "法器", 5, "海灵芝", "红绸", "雷霆数珠", "天光", "熔毁之刻"),
    ("绮良良", "草", "单手剑", 4, "天云草实", "绘卷", "常暗圆环", "浮世", "无光丝线"),
    # ── Inazuma ★４ ──
    ("托马", "火", "长柄武器", 4, "海灵芝", "徽记", "阴燃之珠", "浮世", "熔毁之刻"),
    ("早柚", "风", "双手剑", 4, "鸣草", "花蜜", "魔偶机心", "浮世", "东风的吐息"),
    ("鹿野院平藏", "风", "法器", 4, "鬼兜虫", "徽记", "雷霆数珠", "天光", "凶将之手眼"),
    ("久岐忍", "雷", "单手剑", 4, "鸣草", "面具", "雷霆数珠", "风雅", "凶将之手眼"),
    ("九条裟罗", "雷", "弓", 4, "鬼兜虫", "箭簇", "雷光棱镜", "风雅", "北风之尾"),
    ("五郎", "岩", "弓", 4, "珊瑚真珠", "徽记", "排异之露", "天光", "魔王之刃·残片"),
    # ── Sumeru ★５ ──
    ("纳西妲", "草", "法器", 5, "劫波莲", "菌核", "苍砾蕊羽", "诤言", "空行的虚铃"),
    ("妮露", "水", "单手剑", 5, "帕蒂沙兰", "菌核", "排异之露", "笃行", "凶将之手眼"),
    ("赛诺", "雷", "长柄武器", 5, "圣金虫", "骨片", "雷霆数珠", "诤言", "凶将之手眼"),
    ("艾尔海森", "草", "单手剑", 5, "沙脂蛹", "红绸", "苍砾蕊羽", "巧思", "空行的虚铃"),
    ("提纳里", "草", "弓", 5, "月莲", "菌核", "苍砾蕊羽", "诤言", "空行的虚铃"),
    ("迪希雅", "火", "双手剑", 5, "沙脂蛹", "红绸", "阴燃之珠", "笃行", "原初绿洲之初绽"),
    ("流浪者", "风", "法器", 5, "树王圣体菇", "骨片", "永续机芯", "笃行", "空行的虚铃"),
    # ── Sumeru ★４ ──
    ("柯莱", "草", "弓", 4, "月莲", "箭簇", "苍砾蕊羽", "诤言", "空行的虚铃"),
    ("多莉", "雷", "双手剑", 4, "红刺", "红绸", "雷霆数珠", "巧思", "凶将之手眼"),
    ("珐露珊", "风", "弓", 4, "红刺", "红绸", "永续机芯", "诤言", "空行的虚铃"),
    ("莱依拉", "冰", "单手剑", 4, "月莲", "红绸", "永续机芯", "巧思", "空行的虚铃"),
    ("卡维", "草", "双手剑", 4, "月莲", "菌核", "苍砾蕊羽", "巧思", "原初绿洲之初绽"),
    ("坎蒂丝", "水", "长柄武器", 4, "红刺", "红绸", "排异之露", "笃行", "凶将之手眼"),
    # ── Fontaine ★５ ──
    ("芙宁娜", "水", "单手剑", 5, "湖光铃兰", "花蜜", "排异之露", "正义", "无光丝线"),
    ("那维莱特", "水", "法器", 5, "苍晶螺", "齿轮", "排异之露", "正义", "原初大海的浪花"),
    ("娜维娅", "岩", "双手剑", 5, "苍晶螺", "混沌", "玄岩之塔", "公平", "无光运动之核"),
    ("克洛琳德", "雷", "单手剑", 5, "虹彩蔷薇", "齿轮", "雷光棱镜", "正义", "原初大海的浪花"),
    ("希格雯", "水", "弓", 5, "虹彩蔷薇", "齿轮", "排异之露", "公平", "原初大海的浪花"),
    ("阿蕾奇诺", "火", "长柄武器", 5, "虹彩蔷薇", "徽记", "阴燃之珠", "秩序", "原初大海的浪花"),
    ("莱欧斯利", "冰", "法器", 5, "苍晶螺", "齿轮", "极寒之核", "秩序", "原初大海的浪花"),
    ("林尼", "火", "弓", 5, "虹彩蔷薇", "徽记", "常燃火种", "正义", "原初大海的浪花"),
    ("艾梅莉埃", "草", "长柄武器", 5, "虹彩蔷薇", "齿轮", "苍砾蕊羽", "秩序", "原初大海的浪花"),
    # ── Fontaine ★４ ──
    ("琳妮特", "风", "单手剑", 4, "虹彩蔷薇", "混沌", "永续机芯", "公平", "原初大海的浪花"),
    ("菲米尼", "冰", "双手剑", 4, "苍晶螺", "齿轮", "极寒之核", "正义", "原初大海的浪花"),
    ("夏洛蒂", "冰", "法器", 4, "虹彩蔷薇", "齿轮", "永续机芯", "公平", "原初大海的浪花"),
    ("夏沃蕾", "火", "长柄武器", 4, "虹彩蔷薇", "齿轮", "常燃火种", "秩序", "原初大海的浪花"),
    # ── Natlan ★５ ──
    ("玛薇卡", "火", "双手剑", 5, "燃愿花", "齿轮", "常燃火种", "焚燔", "无光丝线"),
    ("茜特菈莉", "冰", "法器", 5, "燃愿花", "齿轮", "极寒之核", "角逐", "无光丝线"),
    ("希诺宁", "岩", "单手剑", 5, "青蜜莓", "混沌", "玄岩之塔", "焚燔", "无光丝线"),
    ("基尼奇", "草", "双手剑", 5, "青蜜莓", "混沌", "苍砾蕊羽", "角逐", "无光丝线"),
    ("玛拉妮", "水", "法器", 5, "燃愿花", "混沌", "排异之露", "焚燔", "无光丝线"),
    ("恰斯卡", "风", "弓", 5, "青蜜莓", "齿轮", "飓风之种", "角逐", "无光丝线"),
    # ── Natlan ★４ ──
    ("卡齐娜", "岩", "长柄武器", 4, "青蜜莓", "混沌", "玄岩之塔", "焚燔", "无光丝线"),
    ("伊安珊", "雷", "长柄武器", 4, "燃愿花", "混沌", "雷光棱镜", "角逐", "无光丝线"),
    ("欧洛伦", "雷", "弓", 4, "青蜜莓", "齿轮", "雷光棱镜", "焚燔", "无光丝线"),
    ("蓝砚", "风", "法器", 4, "青蜜莓", "混沌", "飓风之种", "角逐", "无光丝线"),
]

# Index constants for the tuple above
_C_IDX = {
    "name": 0, "element": 1, "weapon": 2, "rarity": 3,
    "specialty": 4, "drop_series": 5, "boss_mat": 6,
    "talent_book": 7, "weekly_mat": 8,
}


# ── provider ────────────────────────────────────────────────────────

class StaticDataProvider:
    """Queries Genshin static data from compact mapping + cost templates.

    Character data is expanded from a ~9-field mapping table using
    fixed game formulas — no runtime network or large JSON files needed.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        self._bosses: dict[str, dict[str, Any]] = {}
        self._characters_extra: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        if self._loaded:
            return
        import json

        boss_path = self._data_dir / "bosses.json"
        if boss_path.exists():
            with open(boss_path, encoding="utf-8") as f:
                self._bosses = json.load(f)

        chars_path = self._data_dir / "characters.json"
        if chars_path.exists():
            with open(chars_path, encoding="utf-8") as f:
                self._characters_extra = json.load(f)

        self._loaded = True

    # ── matching ────────────────────────────────────────────────

    def _normalize(self, name: str) -> str:
        key = name.strip().lower().replace(" ", "")
        return _ALIASES.get(key, name.strip())

    def _find_character(self, name: str) -> tuple | None:
        normalized = self._normalize(name)
        for entry in _CHARACTERS:
            if entry[_C_IDX["name"]] == normalized:
                return entry
        nl = normalized.lower()
        for entry in _CHARACTERS:
            if entry[_C_IDX["name"]].lower() == nl:
                return entry
        for entry in _CHARACTERS:
            en = entry[_C_IDX["name"]]
            if nl in en.lower() or en.lower() in nl:
                return entry
        return None

    def _find_boss(self, name: str) -> tuple[str, dict] | None:
        if not self._bosses:
            return None
        normalized = self._normalize(name)
        if normalized in self._bosses:
            return normalized, self._bosses[normalized]
        nl = normalized.lower()
        for key in self._bosses:
            if key.lower() == nl:
                return key, self._bosses[key]
        for key in self._bosses:
            if nl in key.lower() or key.lower() in nl:
                return key, self._bosses[key]
        return None

    # ── public API ──────────────────────────────────────────────

    def search_character(self, name: str) -> CharacterData | None:
        entry = self._find_character(name)
        if entry is None:
            return None
        return self._expand_character(entry)

    def search_boss(self, name: str) -> dict | None:
        self.load()
        match = self._find_boss(name)
        if match is None:
            return None
        key, raw = match
        return {"name": key, **raw}

    def list_characters(self) -> list[str]:
        return [c[_C_IDX["name"]] for c in _CHARACTERS]

    def list_bosses(self) -> list[str]:
        self.load()
        return list(self._bosses.keys())

    # ── extra data (skills/stats from JSON) ──────────────────────

    def _get_extra(self, name: str) -> dict[str, Any] | None:
        self.load()
        return self._characters_extra.get(name)

    # ── template expansion ──────────────────────────────────────

    def _expand_character(self, entry: tuple) -> CharacterData:
        name = entry[_C_IDX["name"]]
        element = entry[_C_IDX["element"]]
        weapon = entry[_C_IDX["weapon"]]
        rarity = entry[_C_IDX["rarity"]]
        specialty = entry[_C_IDX["specialty"]]
        drop_series = entry[_C_IDX["drop_series"]]
        boss_mat = entry[_C_IDX["boss_mat"]]
        talent_book = entry[_C_IDX["talent_book"]]
        weekly_mat = entry[_C_IDX["weekly_mat"]]

        gem_base = GEMS[element]
        d1, d2, d3 = DROPS[drop_series]
        domain, schedule = DOMAINS[talent_book]

        asc_gem_cnt = [1, 3, 6, 3, 6, 6]
        asc_drop_cnt = [3, 15, 12, 18, 12, 24]
        tal_book_cnt = [3, 2, 4, 6, 9, 4, 6, 12]

        asc_items: list[AscensionTier] = []
        for i, (lvl, mora, gidx, sc, didx, has_boss, *rest) in enumerate(_ASC):
            mats: list[dict] = [
                {"name": gem_base + GEM_SUFFIX[gidx], "count": asc_gem_cnt[i]},
                {"name": specialty, "count": sc},
                {"name": [d1, d2, d3][didx], "count": asc_drop_cnt[i]},
            ]
            if has_boss:
                mats.insert(1, {"name": boss_mat, "count": rest[0]})
            asc_items.append(AscensionTier(level=lvl, mora=mora, materials=mats))

        total_mora = sum(t[1] for t in _ASC)
        asc_total = {
            "mora": total_mora,
            "materials": [
                {"name": gem_base + "系列", "count": "1碎屑+9断片+9块+6"},
                {"name": boss_mat, "count": 46},
                {"name": specialty, "count": 168},
                {"name": drop_series + "系列", "count": "18+30+36"},
            ],
        }

        talent_info = TalentInfo(books_type=talent_book, domain=domain, schedule=schedule)

        talent_items: list[TalentTier] = []
        for i, (lvl, mora, bidx, didx, dc, has_weekly, *rest) in enumerate(_TAL):
            mats: list[dict] = [
                {"name": talent_book + "的" + ["教导", "指引", "哲学"][bidx], "count": tal_book_cnt[i]},
                {"name": [d1, d2, d3][didx], "count": dc},
            ]
            if has_weekly:
                mats.insert(1, {"name": weekly_mat, "count": rest[0]})
            if i == len(_TAL) - 1:  # last tier → crown
                mats.append({"name": "智识之冕", "count": 1})
            talent_items.append(TalentTier(level=lvl, mora=mora, materials=mats))

        triple_crown = {
            "mora": sum(t[1] for t in _TAL),
            "books": {
                talent_book + "的教导": 9,
                talent_book + "的指引": 63,
                talent_book + "的哲学": 114,
            },
            "weekly": {weekly_mat: 18},
            "crown": 3,
        }

        extra = self._get_extra(name)

        # Skills, passives, and constellations from extra data
        skills: list[SkillInfo] = []
        passives: list[PassiveInfo] = []
        constellations: list[ConstellationInfo] = []
        if extra:
            for s in extra.get("skills", []):
                skills.append(SkillInfo(
                    name=s.get("name", ""),
                    description=_clean_desc(s.get("desc", "")),
                    cd=s.get("cd", 0),
                    energy=s.get("cost", 0),
                    stamina=s.get("stamina", 0),
                ))
            for p in extra.get("passives", []):
                passives.append(PassiveInfo(
                    name=p.get("name", ""),
                    description=_clean_desc(p.get("desc", "")),
                    unlock=p.get("unlock", ""),
                ))
            for c in extra.get("constellations", []):
                constellations.append(ConstellationInfo(
                    name=c.get("name", ""),
                    description=_clean_desc(c.get("desc", "")),
                ))

        # Stats from extra data
        stats_obj: CharacterStats | None = None
        if extra:
            st = extra.get("stats", {})
            stats_obj = CharacterStats(
                hp_90=st.get("hp_90", 0),
                atk_90=st.get("atk_90", 0),
                def_90=st.get("def_90", 0),
                crit_rate=st.get("crit_rate", 0),
                crit_dmg=st.get("crit_dmg", 0),
                er=st.get("er", 0),
            )

        return CharacterData(
            name=name,
            rarity=rarity,
            element=element,
            weapon=weapon,
            ascension_items=asc_items,
            ascension_total_1_90=asc_total,
            talent=talent_info,
            talent_items=talent_items,
            talent_triple_crown=triple_crown,
            skills=skills,
            passives=passives,
            constellations=constellations,
            stats=stats_obj,
        )


def _clean_desc(desc: str) -> str:
    """Strip color tags, convert literal \\n to separators for IM display."""

    text = desc.replace("\\n", "\n")
    text = re.sub(r"<color=#[A-Fa-f0-9]+>", "", text)
    text = text.replace("</color>", "")
    # Compact: section breaks → │, line breaks → space
    text = re.sub(r"\n{2,}", "  │  ", text)
    text = re.sub(r"\n", " ", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text).strip()
    # Keep first ~400 chars, break at last sentence boundary within limit
    if len(text) > 400:
        for sep in ("。", "！", "？"):
            idx = text.rfind(sep, 0, 400)
            if idx > 100:
                return text[: idx + 1]
    return text[:400]
