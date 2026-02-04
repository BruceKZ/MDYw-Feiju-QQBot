# -*- coding: utf-8 -*-
"""
混合 NLP 引擎
Hybrid NLP engine for CJK + EN multilingual text processing
"""
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import Counter

import jieba

from .config import STOPWORDS_DIR, FONT_PATH, USER_DICT_PATH

# 懒加载标志
_initialized = False
_stopwords: Set[str] = set()
_spacy_nlp = None
_sudachi_tokenizer = None


def _load_stopwords() -> Set[str]:
    """加载所有停用词表"""
    stopwords = set()
    
    if STOPWORDS_DIR.exists():
        for file in STOPWORDS_DIR.glob("*.txt"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            stopwords.add(word)
            except Exception as e:
                print(f"[WordCloud] Failed to load stopwords from {file}: {e}")
    
    return stopwords


def _init_nlp_engines():
    """延迟初始化 NLP 引擎"""
    global _initialized, _stopwords, _spacy_nlp, _sudachi_tokenizer
    
    if _initialized:
        return
    
    # 加载用户自定义词典
    if USER_DICT_PATH.exists():
        jieba.load_userdict(str(USER_DICT_PATH))
        print(f"[WordCloud] Loaded user dictionary from {USER_DICT_PATH}")
    
    # 加载停用词
    _stopwords = _load_stopwords()
    print(f"[WordCloud] Loaded {len(_stopwords)} stopwords")
    
    # 初始化 Spacy (英文词形还原)
    try:
        import spacy
        _spacy_nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        print("[WordCloud] Spacy en_core_web_sm loaded")
    except Exception as e:
        print(f"[WordCloud] Spacy not available: {e}")
        _spacy_nlp = None
    
    # 初始化 Sudachi (日文分词)
    try:
        from sudachipy import tokenizer as sud_tokenizer
        from sudachipy import dictionary
        _sudachi_tokenizer = dictionary.Dictionary().create()
        print("[WordCloud] SudachiPy loaded")
    except Exception as e:
        print(f"[WordCloud] SudachiPy not available: {e}")
        _sudachi_tokenizer = None
    
    _initialized = True


# ============== 预处理管道 ==============

# 正则表达式 (按顺序执行)
CQ_CODE_PATTERN = re.compile(r'\[CQ:[^\]]+\]')                    # CQ码
URL_PATTERN = re.compile(r'(https?://\S+|www\.\S+)', re.IGNORECASE)  # URL
SPECIAL_CHARS_PATTERN = re.compile(r'[^\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff\uac00-\ud7afa-zA-Z0-9\s]')  # 保留CJK+EN+数字
FULLWIDTH_SPACE = '\u3000'  # 全角空格


def preprocess_text(text: str) -> str:
    """
    文本预处理管道
    1. 移除 CQ 码
    2. 移除 URL
    3. 移除特殊符号 (仅保留中日韩+英文+数字)
    4. 全角空格转半角
    5. 多空格合并
    """
    if not text:
        return ""
    
    # Step 1: 移除 CQ 码
    text = CQ_CODE_PATTERN.sub('', text)
    
    # Step 2: 移除 URL
    text = URL_PATTERN.sub('', text)
    
    # Step 3: 移除特殊符号
    text = SPECIAL_CHARS_PATTERN.sub(' ', text)
    
    # Step 4: 全角空格转半角
    text = text.replace(FULLWIDTH_SPACE, ' ')
    
    # Step 5: 多空格合并
    text = ' '.join(text.split())
    
    return text.strip()


# ============== 分词引擎 ==============

ENGLISH_WORD_PATTERN = re.compile(r'[a-zA-Z]+')


def _lemmatize_english(words: List[str]) -> List[str]:
    """
    英文词形还原
    将 running/ran/runs 统一为 run
    """
    global _spacy_nlp
    
    if not _spacy_nlp or not words:
        return [w.lower() for w in words]
    
    try:
        text = ' '.join(words)
        doc = _spacy_nlp(text)
        return [token.lemma_.lower() for token in doc if token.is_alpha]
    except Exception:
        return [w.lower() for w in words]


def _tokenize_cjk(text: str) -> List[str]:
    """
    中日文分词
    使用 Jieba 为主，对结果进行过滤
    """
    words = jieba.lcut(text)
    
    filtered = []
    for word in words:
        word = word.strip()
        
        # 跳过空白
        if not word:
            continue
        
        # 跳过纯数字
        if word.isdigit():
            continue
        
        # 跳过长度 < 2 的非英文词
        if len(word) < 2 and not word.isascii():
            continue
        
        # 跳过停用词
        if word in _stopwords or word.lower() in _stopwords:
            continue
        
        filtered.append(word)
    
    return filtered


def tokenize(text: str) -> Dict[str, int]:
    """
    混合分词主函数
    返回词频字典
    
    流程:
    1. 预处理清洗
    2. 提取英文单词 -> Spacy 词形还原
    3. 剩余文本 -> Jieba 分词
    4. 合并结果并统计词频
    """
    _init_nlp_engines()
    
    # 预处理
    cleaned = preprocess_text(text)
    if not cleaned:
        return {}
    
    all_words = []
    
    # 提取并处理英文
    english_words = ENGLISH_WORD_PATTERN.findall(cleaned)
    if english_words:
        lemmatized = _lemmatize_english(english_words)
        # 过滤停用词和短词
        english_filtered = [
            w for w in lemmatized 
            if len(w) >= 2 and w not in _stopwords
        ]
        all_words.extend(english_filtered)
    
    # 移除英文后处理中日文
    cjk_text = ENGLISH_WORD_PATTERN.sub(' ', cleaned)
    cjk_words = _tokenize_cjk(cjk_text)
    all_words.extend(cjk_words)
    
    # 统计词频
    return dict(Counter(all_words))


def tokenize_texts(texts: List[str]) -> Dict[str, int]:
    """
    批量处理多条消息
    合并所有消息后进行分词统计
    """
    combined = ' '.join(texts)
    return tokenize(combined)
